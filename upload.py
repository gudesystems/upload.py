#!/usr/bin/python3

from configparser import ConfigParser
from argparse import ArgumentParser, Namespace
import os
import ipaddress
from socket import gaierror
from requests import get as req_get
from requests.exceptions import Timeout, HTTPError, RequestException
from typing import Tuple, Optional, List
from dataclasses import dataclass

from gude.deployDev import DeployDev
from gude.gblib import Gblib
import json
import re

from gude import file_search

import logging
logging.basicConfig(format='%(asctime)s %(name)-18s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)  # custom logger name can be set
log.setLevel(logging.getLevelName('DEBUG'))

BASE_URL = "https://files.gude-systems.com/fw"
def fetch_latest_fw_infos(base_url: str   = BASE_URL) -> ConfigParser:
    """
    Return a ready-to-use ConfigParser whose layout matches

        [url]
        basepath = https://files.gude-systems.com/fw

        [enc2111]
        subpath      = gude
        json         = firmware-enc2111.json
        version      = 1.7.1
        filename     = firmware-enc2111_v{version}.bin
        date         = 14.01.2025
        size         = 1.1 MB
        version_list = 1.7.1, 1.7.0, 1.6.1, …

    The `version_list` is stored as a single comma-separated string, because
    the INI format has no native list type.
    """
    # --- download & decode --------------------------------------------------
    log.debug(f"Reading {base_url} ...")
    payload: list[dict] = req_get(base_url, timeout=30).json()

    # --- build config -------------------------------------------------------
    cfg = ConfigParser()
    cfg["url"] = {"basepath": base_url}

    for entry in payload:
        if entry["rev"] and entry["rev"] == 2:
            section = f"{entry['model']}R{entry["rev"]}"  # e.g. "8031R2"
        else:
            section = f"{entry['model']}"  # e.g. "2111"
        cfg[section] = {
            "subpath":  entry["subpath"],
            "json":     entry["json"],
            "filename": entry["filename"],
            "type":     entry["type"],
            "model":    entry["model"],
            "rev":      entry["rev"],
            "version":  entry["version"],
            "date":     entry["date"],
            "size":     entry["size"],
            # keep the list – flattened into one string
            "version_list": ", ".join(entry["version_list"]),
        }

    return cfg


def add_devices_to_config(_args: Namespace, _config: ConfigParser) -> ConfigParser:
    """
    Add devices from command line args to the config parser object
    
    :param _args: Parsed command line arguments
    :param _config: Configuration parser object
    :return: Modified configuration parser object
    """
    if _args.devices is not None:
        log.debug(f"Adding devices to config: {_args.devices}")
        for section, settings in _args.devices.items():
            set_config_defaults(_config, section, settings, overwrite=True)
    return _config


def set_config_defaults(_config: ConfigParser, section: str, settings: dict, overwrite: bool = False) -> None:
    """
    Function to set default configuration values for a section.
    
    :param _config: Configuration parser object to be edited
    :param section: Section name to apply settings to
    :param settings: Dictionary of default settings to apply
    :param overwrite: Whether to overwrite existing values (default: False)
    """
    if not _config.has_section(section):
        _config[section] = {}
    
    for key, value in settings.items():
        if overwrite or not _config.has_option(section, key):
            _config[section][key] = str(value)

# Default settings dictionaries
DEFAULT_SETTINGS = {
    'defaults': {
        'httpTimeout': '3.0',
        'gblTimeout': '1.0',
        'fwdir': 'fw'
    },
    'httpDefaults': {
        'port': '80',
        'ssl': '0',
        'auth': '0',
        'username': '',
        'password': ''
    },
    'hosts': {}
}


def parse_args() -> Tuple[Namespace, ConfigParser, ConfigParser, str]:
    """
    Function to parse all necessary parameters

    :returns:
        - _args - parsed args
        - _config - parsed upload.ini
        - _firmware - parsed version.ini
        - _my_ip - parsed own IP
    :rtype: Tuple[Namespace, ConfigParser, ConfigParser, str]
    """
    log.debug("Parsing args ...")
    parser = ArgumentParser()
    parser.add_argument('-c', '--configip', help='ip address to select config')
    parser.add_argument('-f', '--forcefw', help='upload fw even if already up to date', action="store_true")
    parser.add_argument('-u', '--upload_ini', help='upload.ini paramater set', default='upload.ini')
    parser.add_argument('-v', '--version_ini', help='fw version defs', default='version.ini')
    parser.add_argument('-o', '--onlineupdate', help='use online update files', action="store_true", default=False)
    parser.add_argument('-i', '--iprange', nargs="+",  help='range of ip address to manage')
    parser.add_argument('-sf', '--search_folder', help='folder to search for binary')
    parser.add_argument('-r', '--repl_prod_id', help='product ids to replace', default={'2110': '2111'}) # , '8221': '822x', '8226': '822x'
    parser.add_argument('-d', '--devices', help="overwrites upload.ini like {'httpDefaults': {'port'=80, 'ssl'=0, 'auth'=0, 'username'='','password'=''} }", default=None, type=json.loads)
    # -d "{\"httpDefaults\":{\"username\":\"admin\",\"password\":\"admin\"}}"
    parser.add_argument('-H', '--header', help='Setting custom http header like \'{"Connection": "close"}\'', default=None, type=json.loads)
    parser.add_argument('-S', '--status', help='Only fetch device status without making any changes', action="store_true", default=False)
    parser.add_argument('-G', '--gbl', help='Use GBL broadcast', action="store_true", default=True)
    _args = parser.parse_args()

    log.debug(f"Reading {_args.upload_ini} ...")
    _config = ConfigParser(strict=False)
    _config.read(_args.upload_ini)

    if _args.gbl:
        log.debug(f"Detected GBL search flag, adding to config ...")
        if not _args.devices:
            _args.devices = {}
        if not 'hosts' in _args.devices:
            _args.devices['hosts'] = {}
        _args.devices['hosts'].update({'gbl':'search'})

    _config = add_devices_to_config(_args, _config)

    configure_auth_settings(_config)

    # Apply default settings using the generalized function
    for section, settings in DEFAULT_SETTINGS.items():
        set_config_defaults(_config, section, settings)

    _firmware = ConfigParser(strict=False)
    if _args.search_folder is not None and os.path.isdir(_args.search_folder):
         log.debug(f"Searching for binaries in {_args.search_folder} ...")
         bin_infos = file_search.rekursive_search(_args.search_folder)
         log.debug(f"Found {len(bin_infos)} binaries in {_args.search_folder} ...")
         unique_bin_infos = file_search.get_unique_devices(bin_infos)
         _firmware = file_search.get_config(unique_bin_infos, config=_firmware)
    elif _args.onlineupdate:
        _firmware = fetch_latest_fw_infos()
    else:
        log.debug(f"Reading {os.path.join(_config['defaults']['fwdir'], _args.version_ini)} ...")
        _firmware.read(os.path.join(_config['defaults']['fwdir'], _args.version_ini))
    log.debug("Getting my IP (for GBL/UDP search) ...")
    _my_ip = _config['defaults']['myIp'] if 'myIp' in _config['defaults'] else '0.0.0.0'

    return _args, _config, _firmware, _my_ip


def add_iprange_to_config(_iprange: Optional[List[str]], _config: ConfigParser): # Type hint for _iprange
    """
    Function that adds hosts from args to hosts in _config (parsed hosts from upload.ini)
    :param str _iprange: ip, ip-sub-net OR hostname
    :param ConfigParser _config: local properties parsed from upload.ini
    """
    # add cmd line arg to ip list
    if _iprange is not None:
        for i, ip_val in enumerate(_iprange): # Renamed ip to ip_val to avoid conflict
            log.debug(f"Adding iprange: {ip_val}")
            # Ensure 'hosts' section exists
            if 'hosts' not in _config:
                _config['hosts'] = {}
            if ':' in ip_val and '/' not in ip_val:
                if (']' in ip_val and ':' in ip_val.rpartition(']')[2]) or ']' not in ip_val:
                    _config[ip_val] = {} # This creates a section with the IP:Port as name
                    _config[ip_val]['port'] = ip_val.rpartition(':')[2]

            _config['hosts'][f'iprange_{i}'] = ip_val # Store in 'hosts' section
    else:
        if 'hosts' not in _config or not _config['hosts']: # Check if 'hosts' section is empty or not present
            log.error("no EPC/PDU device IP address(es) given.\n"
                      "\tPlease try to enable 'gbl=search' or 'ip1=192.168.0.1' in your upload.ini,\n"
                      "\tand/or give an IP address or subnet by --iprange parameter\n")
            raise KeyError("Missing required args, could not determine device!")


def generate_ip_list(_hosts_config: ConfigParser, _my_ip: str, _gbl_timeout: float) -> list: # Changed _hosts to _hosts_config
    """
    Function that adds hosts from args to hosts in _config (parsed hosts from upload.ini)
    :param ConfigParser _hosts_config: ConfigParser section for hosts
    :param str _my_ip: this is the broadcaster/client ip, require for GBL/UDP search
    :param float _gbl_timeout: timeout in seconds to wait after sending broadcast

    :returns:
    - _ip_list - parsed args
    :rtype: list
    """
    _ip_list = []
    # Iterate over items in the 'hosts' section of the ConfigParser object
    log.debug(f"Getting all IPs for hosts defined in config section: hosts")
    for key, target in _hosts_config.items('hosts'): # Iterate over 'hosts' section
        log.debug(f"Checking host entry {key}: {target}")
        if target == "search":
            log.info("Searching devices by GBL UDP broadcast...")
            try:
                device_lst = Gblib.recv_bc(_my_ip, _gbl_timeout)
                for dev_info_bytes in device_lst: # dev is bytes
                    dev_info_dict = Gblib.get_dev_info(dev_info_bytes) # parse bytes to dict
                    if 'ip' in dev_info_dict:
                         _ip_list.append(dev_info_dict['ip'])
                    else:
                        log.warning(f"Device found via GBL without IP information: {dev_info_dict}")
            except Exception as e:
                log.error(f"Error during GBL search: {e}")
        else:
            num_hosts = 0
            try:
                # ipaddress.ip_network can handle single IPs as well if they are valid strings
                # It will create a network with a single host.
                # For hostnames, this will fail, and we'll fall into the ValueError.
                ip_network = ipaddress.ip_network(target, strict=False) # strict=False allows single IPs
                for ip_addr_obj in ip_network.hosts():
                    _ip_list.append(str(ip_addr_obj)) # Store as string
                    num_hosts += 1
                if num_hosts == 0 and ip_network.num_addresses == 1: # Single IP case
                     _ip_list.append(str(ip_network.network_address))
                     num_hosts = 1

            except ValueError: # Handles hostnames or invalid IP/network strings
                log.warning(f"{target} could not be parsed as IPAddress or IP-Network by 'ipaddress' library, "
                            f"treating as a single host identifier (e.g., hostname or IP string).")
                _ip_list.append(target) # Add as is (could be hostname or IP string)
                num_hosts = 1

            if num_hosts == 0 and '/' not in target : # If still no hosts, and it wasn't a network string, add target itself
                 _ip_list.append(target)


    # Remove duplicates that might have occurred
    _ip_list = sorted(list(set(_ip_list)))
    return _ip_list


@dataclass
class DeviceResult:
    ip: str
    product_name: str
    mac: str
    initial_firmware: str
    latest_known_firmware: Optional[str] = None
    final_firmware: Optional[str] = None
    firmware_status: str = "not attempted"
    firmware_upload_notes: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None


def iterate_list(_ip_list: list, _firmware: ConfigParser, _config: ConfigParser, _args: object) -> list[DeviceResult]:
    """
    Function that iterates over all hosts from _ip_list hosts,
    matching corresponding firmware in _firmware,
    using http config given by _config,
    considering additional options from _args
    :param list _ip_list: list of ips, ip-sub-nets OR hostnames
    :param ConfigParser _firmware: containing firmware information
    :param ConfigParser _config: containing http config
    :param Namespace _args: additional options
    Returns a list of DeviceResult objects containing the processing status of each device.
    """

    # TODO: Is GBL in this context necessary?
    gbl = Gblib()

    results: List[DeviceResult] = [] # Type hint for results
    log.debug(f"trying {len(_ip_list)} devices")
    for ip_str_or_obj in _ip_list: # ip can be str or IPv4Address/IPv6Address from older generate_ip_list
        ip = str(ip_str_or_obj) # Ensure ip is a string for consistency
        result = DeviceResult(ip=ip, product_name="unknown", mac="unknown", initial_firmware="unknown")
        
        try:
            log.debug(f"Processing device: {ip}")
            dev_ip_for_conn = ip # Default
            # Handle potential port in IP string (though generate_ip_list should give clean IPs)
            if isinstance(ip, str) and ':' in ip:
                parts = ip.split(':')
                dev_ip_for_conn = parts[0]
                # Check if we're dealing with a hostname or IP
                try:
                    # Only validate if it looks like an IP address
                    if re.match(r'^[\d\.]+$', dev_ip_for_conn):
                        ipaddress.ip_address(dev_ip_for_conn)
                except ValueError:
                    # This is likely a hostname with port, which is fine
                    log.debug(f"Treating {dev_ip_for_conn} as hostname with port {parts[1]}")

            dev = DeployDev(dev_ip_for_conn, req_headers=_args.header)

            # Determine config_key: if ip (e.g. "192.168.1.10:8080") is a section name, use it.
            # Otherwise, use dev_ip_for_conn (e.g. "192.168.1.10") if it's a section.
            # Fallback to 'httpDefaults'.
            config_key_options = [ip, dev_ip_for_conn, 'httpDefaults']
            config_key = 'httpDefaults' # Default fallback
            for key_option in config_key_options:
                if _config.has_section(key_option):
                    config_key = key_option
                    break

            log.debug(f"Using config-key '{config_key}' for device {ip}")

            # Apply HTTP defaults using the generalized function
            set_config_defaults(_config, config_key, DEFAULT_SETTINGS['httpDefaults'])
            # Now apply specific settings from the chosen config_key section
            dev.set_http_port(int(_config.get(config_key, 'port', fallback=80)),
                              _config.getboolean(config_key, 'ssl', fallback=False))
            dev.set_basic_auth(_config.getboolean(config_key, 'auth', fallback=False),
                               _config.get(config_key, 'username', fallback=''),
                               _config.get(config_key, 'password', fallback=''))
            dev.set_http_timeout(float(_config.get('defaults', 'httpTimeout', fallback=3.0)))
            dev.set_http_retries(0)
            
            try:
                device_data = dev.http_get_status_json(DeployDev.JSON_STATUS_MISC)['misc']
            except HTTPError as e:
                if e.response.status_code == 401:
                    log.error(f"Authentication Error on defined port/protocol for {ip}: {e}")
                    result.error_message = f"Authentication Error: {e}"
                    results.append(result)
                    continue
                else:
                    log.error(f"HTTPError for {ip}: {e}")
                    result.error_message = f"HTTPError: {e}"
                    results.append(result)
                    continue # Re-raise if you want to stop all processing
            except (Timeout, ConnectionError) as ce: # Catch Timeout and ConnectionError
                log.error(f"Could not reach device on defined port/protocol for {ip}: {ce}")
                result.error_message = f"Connection/Timeout Error: {ce}"
                results.append(result)
                continue
            except Exception as e_misc: # Catch other potential errors during initial status fetch
                log.error(f"Unexpected error fetching initial status for {ip}: {e_misc}")
                result.error_message = f"Unexpected initial status error: {e_misc}"
                results.append(result)
                continue

            result.product_name = device_data['product_name']
            result.initial_firmware = device_data['firm_v']

            gbl_error = False
            mac = "unknown-mac"
            try:
                log.info(f"Attempting to get MAC for {ip} via GBL/UDP...")
                if not gbl.check_mac(str(dev_ip_for_conn)): # Use dev_ip_for_conn which should be clean IP
                    log.warning(f"GBL Timeout (UDP port 50123) for {dev_ip_for_conn}")
                    gbl_error = True
                else:
                    # extract mac (bytes longer than 255 result in two hex values so b'\x192' results in 1*16+9 and 2*16+0)
                    # this dec values need to be converted back to hex ('x') as string with the length 2 ('02')
                    mac = '_'.join(f'{c:02x}' for c in gbl.dstMAC)
                    log.info(f"Got MAC {mac} for {dev_ip_for_conn} via GBL.")
            except (gaierror, ConnectionResetError, OSError) as e_gbl: # OSError for network unreachable
                log.warning(f"GBL MAC retrieval failed for {dev_ip_for_conn}: {e_gbl}")
                gbl_error = True
                
            if gbl_error:
                log.info(f"Falling back to HTTP(S) to get MAC for {dev_ip_for_conn}...")
                try:
                    mac_http = dev.http_get_status_json(DeployDev.JSON_STATUS_ETHERNET, req_headers=None)['ethernet']['mac']
                    mac = mac_http.replace(':', '_')
                    log.info(f"Got MAC {mac} for {dev_ip_for_conn} via HTTP(S).")
                except (RequestException, ValueError, TimeoutError) as e_http_mac:
                    log.error(f"Could not get MAC via HTTP(S) for {dev_ip_for_conn}: {e_http_mac}")
                    # Keep mac as "unknown-mac" or previous GBL error value

            result.mac = mac

            log.debug(f"Getting config filename for MAC {mac}, IP {ip}...")
            cfg_filename = DeployDev.get_config_filename('config', 'config', 'txt', mac, ip, _args.configip)
            log.debug(f"Getting ssl-cert filename for MAC {mac}, IP {ip}...")
            ssl_cert_filename = DeployDev.get_config_filename('ssl', 'cert', 'pem', mac, ip, _args.configip)

            # --- before logging/deploy ---
            actual_prod_id = device_data['prodid']
            selected_prod_id = None
            # 1) Try exact match on the original prodid
            if actual_prod_id in _firmware:
                selected_prod_id = actual_prod_id
            # 2) If no match yet, apply your replacement map
            if not selected_prod_id:
                repl_map_str_any = _args.repl_prod_id # This is already a dict due to type=json.loads
                repl_map = repl_map_str_any if isinstance(repl_map_str_any, dict) else {}

                if actual_prod_id in repl_map:
                    candidate = repl_map[actual_prod_id]
                    if candidate in _firmware:
                        selected_prod_id = candidate
            # 3) If still nothing, and prodid contains "xx", inject the real number from product_name
            if not selected_prod_id and "xx" in actual_prod_id:
                m = re.search(r"(\d+)-", device_data["product_name"])
                if m:
                    # take the last 2 digits of the number you found to fill "xx"
                    real_digits = m.group(1)[-2:]
                    candidate = actual_prod_id.replace("xx", real_digits)
                    if candidate in _firmware:
                        selected_prod_id = candidate
            # 4) Finally, if still nothing and prodid contains "xx", do a regex wildcard match
            if not selected_prod_id and "xx" in actual_prod_id:
                # build a pattern like "^80\d\dR2?$" or "^21\d\ddi?$" etc.
                pat = "^" + re.escape(actual_prod_id).replace("xx", r"\d\d") + "$"
                for fw_id in _firmware:
                    if re.match(pat, fw_id):
                        selected_prod_id = fw_id
                        break
            # update device_data and log
            if selected_prod_id:
                device_data["prodid"] = selected_prod_id # Update prodid for update_firmware call
                if selected_prod_id in _firmware:
                    result.latest_known_firmware = f"{_firmware[selected_prod_id]['version']} ({_firmware[selected_prod_id]['date']}, {_firmware[selected_prod_id]['size']})"
                else:
                    result.latest_known_firmware = "unknown"
                log.info(
                    f"{device_data['product_name']} "
                    f"({actual_prod_id} -> {selected_prod_id}, {mac}) at {ip}\n"
                    + " " * (len(f"{device_data['product_name']} ({actual_prod_id} -> {selected_prod_id}, {mac}) at {ip}") - len(f"running Firmware v{device_data['firm_v']}")) # Align logging
                    + f"running Firmware v{device_data['firm_v']}, latest known: {result.latest_known_firmware}"
                )
            else:
                log.warning(f"No firmware entry found for product '{actual_prod_id}' (original) or suitable replacement.")
                result.firmware_status = f"No firmware definition for {actual_prod_id}"

            # continue here for status
            if _args.status:
                result.firmware_status = "status only, no changes made"
                result.success = False
                results.append(result)
                continue

            # deploy Firmware
            if selected_prod_id and selected_prod_id in _firmware: # Check if selected_prod_id is valid for _firmware
                try:
                    fw_update_result = dev.update_firmware(device_data, _firmware,
                                                           _config.get('defaults', 'fwdir', fallback='fw'),
                                                           forced=_args.forcefw,
                                                           online_update=_args.onlineupdate)

                    result.final_firmware = fw_update_result.get("final_version", result.initial_firmware)
                    result.firmware_status = fw_update_result.get("status_message", "firmware update status unknown")
                    result.firmware_upload_notes = fw_update_result.get("upload_notes")
                except ValueError as ve_fw: # Catches firmware file not found etc. from update_firmware
                    result.firmware_status = f"failed: {str(ve_fw)}"
                    log.warning(f"Skipped firmware update for {ip}: {ve_fw}")
                except Exception as e_fw_update: # Catch any other unexpected error during update_firmware
                    result.firmware_status = f"failed: unexpected error during update ({str(e_fw_update)})"
                    log.error(f"Unexpected error during firmware update for {ip}: {e_fw_update}", exc_info=True)

            # Deploy Configuration
            if cfg_filename is not None:
                log.debug(f"Attempting to upload configuration {cfg_filename} to {ip}...")
                try:
                    dev.upload_config(cfg_filename, _args.configip)
                    log.info(f"Successfully uploaded configuration {cfg_filename} to {ip}.")
                except Exception as e_cfg:
                    log.error(f"Failed to upload configuration {cfg_filename} to {ip}: {e_cfg}")
                    if result.error_message: result.error_message += f"; Config upload error: {e_cfg}"
                    else: result.error_message = f"Config upload error: {e_cfg}"


            # Deploy SSL certificate
            if ssl_cert_filename is not None:
                log.debug(f"Attempting to upload SSL certificate {ssl_cert_filename} to {ip}...")
                try:
                    dev.upload_ssl_certificate(ssl_cert_filename)
                    log.info(f"Successfully uploaded SSL certificate {ssl_cert_filename} to {ip}.")
                except Exception as e_ssl:
                    log.error(f"Failed to upload SSL certificate {ssl_cert_filename} to {ip}: {e_ssl}")
                    if result.error_message: result.error_message += f"; SSL cert upload error: {e_ssl}"
                    else: result.error_message = f"SSL cert upload error: {e_ssl}"

            # Print FW Version and configured Hostname (final check)
            try:
                final_ipv4_config = dev.http_get_config_json(dev.JSON_CONFIG_IP)['ipv4']
                final_misc_status = dev.http_get_status_json(DeployDev.JSON_STATUS_MISC)['misc']
                log.info(f"Device {dev.host} (final check) has hostname '{final_ipv4_config['hostname']}' and FW Version {final_misc_status['firm_v']}")
                # Update final_firmware if it changed due to config/ssl reboot and wasn't from fw update
                if result.final_firmware == result.initial_firmware or result.final_firmware is None: # only if not set by fw update
                    if final_misc_status['firm_v'] != result.initial_firmware:
                        result.final_firmware = final_misc_status['firm_v']
                        # Potentially update firmware_status if it implies no update was done but version changed
                        if "not attempted" in result.firmware_status or "up to date" in result.firmware_status:
                             result.firmware_status = f"version changed to {result.final_firmware} (possibly due to other uploads)"


            except Exception as e_final_check:
                log.warning(f"Could not perform final status check for {dev.host}: {e_final_check}")

            # Overall success for the device if no major error message was set earlier
            if not result.error_message:
                 result.success = True # Mark as success if no critical errors were logged to result.error_message

        except Exception as e: # Catch-all for the processing of a single device
            log.error(f"Major error processing device {ip}: {e}", exc_info=True)
            result.error_message = str(e)
            result.success = False # Ensure success is false on major error

        results.append(result)
    
    return results


def configure_auth_settings(_config: ConfigParser) -> None:
    """
    Configure authentication settings for sections that have username and password but no auth flag set.

    :param _config: Configuration parser object to be edited
    """
    for section in _config.sections():
        # Ensure section is not 'DEFAULT' or other special sections if ConfigParser version implies
        if section == 'DEFAULT' or section == _config.default_section:
            continue

        has_user = _config.has_option(section, 'username') and _config.get(section, 'username', fallback=None) is not None
        has_pass = _config.has_option(section, 'password') and _config.get(section, 'password', fallback=None) is not None
        # Check if 'auth' is explicitly set to '0' or '1'. If not present, it's not "set".
        auth_val = _config.get(section, 'auth', fallback=None)
        has_auth_explicitly_set = auth_val in ['0', '1']


        if has_user and has_pass and not has_auth_explicitly_set:
            # mark this section as needing auth if username/password are non-empty
            if _config.get(section, 'username') or _config.get(section, 'password'):
                 log.debug(f"Configuring auth=1 for section '{section}' due to presence of username/password and no explicit auth setting.")
                 _config[section]['auth'] = '1'
            elif auth_val is None: # If username/password are empty and auth is not set at all
                 _config[section]['auth'] = '0' # Default to auth=0

if __name__ == "__main__": # Ensure this runs only when script is executed directly
    # get all args
    args, config, firmware, my_ip = parse_args()

    # parsing hosts
    add_iprange_to_config(args.iprange, config)

    # Pass the 'hosts' section of config, not the whole config object
    ip_list = generate_ip_list(config, my_ip, float(config.get('defaults', 'gblTimeout', fallback=1.0)))

    # iterate devices, get each dev info, update fw, config and certificate
    processing_results = iterate_list(ip_list, firmware, config, args)

    log.info("\nDevice Processing Summary:")
    log.info("-" * 80)
    for res_item in processing_results:
        status_char = "✓" if res_item.success else "✗"
        device_info = [
            f"{status_char} Device {res_item.ip}",
            f"Product: {res_item.product_name}",
            f"MAC: {res_item.mac}",
            f"Initial FW: {res_item.initial_firmware}",
            f"Latest known FW: {res_item.latest_known_firmware}"
        ]
        
        if res_item.final_firmware and res_item.final_firmware != res_item.initial_firmware:
            device_info.append(f"Final FW: {res_item.final_firmware}")
            
        log.info(", ".join(device_info))
        
        if res_item.firmware_status:
            log.info(f"   Status: {res_item.firmware_status}")
        if res_item.firmware_upload_notes:
            log.info(f"   Notes: {res_item.firmware_upload_notes}")
        if res_item.error_message:
            log.info(f"   Error: {res_item.error_message}")
    
    log.info("-" * 80)
    success_count = sum(1 for r_item in processing_results if r_item.success)
    log.info(f"Successfully processed {success_count} of {len(processing_results)} devices (based on overall success flag).")
