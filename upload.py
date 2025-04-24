#!/usr/bin/python3

from configparser import ConfigParser
from argparse import ArgumentParser, Namespace
import os
import ipaddress
from socket import gaierror
from requests.exceptions import ConnectionError
from typing import Tuple

from gude.deployDev import DeployDev
from gude.gblib import Gblib
import json
import re

from gude import file_search

import logging
logging.basicConfig(format='%(asctime)s %(name)-18s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)  # custom logger name can be set
log.setLevel(logging.getLevelName('DEBUG'))


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
    parser.add_argument('-s', '--search_folder', help='folder to search for binary')
    parser.add_argument('-r', '--repl_prod_id', help='product ids to replace', default={'2110': '2111'}) # , '8221': '822x', '8226': '822x'
    parser.add_argument('-H', '--header', help='Setting custom http header like \'{"Connection": "close"}\'', default=None, type=json.loads)
    _args = parser.parse_args()

    log.debug(f"Reading {_args.upload_ini} ...")
    _config = ConfigParser(strict=False)
    _config.read(_args.upload_ini)

    set_host_default(_config)
    set_default(_config)
    set_http_defaults(_config)

    _firmware = ConfigParser(strict=False)
    if _args.search_folder is not None and os.path.isdir(_args.search_folder):
         log.debug(f"Searching for binaries in {_args.search_folder} ...")
         bin_infos = file_search.rekursive_search(_args.search_folder)
         log.debug(f"Found {len(bin_infos)} binaries in {_args.search_folder} ...")
         unique_bin_infos = file_search.get_unique_devices(bin_infos)
         _firmware = file_search.get_config(unique_bin_infos, config=_firmware)
    else:
        log.debug(f"Reading {os.path.join(_config['defaults']['fwdir'], _args.version_ini)} ...")
        _firmware.read(os.path.join(_config['defaults']['fwdir'], _args.version_ini))
    log.debug("Getting my IP (for GBL/UDP search ...")
    _my_ip = _config['defaults']['myIp'] if 'myIp' in _config['defaults'] else '0.0.0.0'

    return _args, _config, _firmware, _my_ip


def set_host_default(_config):
    """
    Function to set host section.
    :param _config ConfigParser: config parser to be edited
    """
    if not _config.has_section("hosts"):
        _config["hosts"] = {}


def set_default(_config, section='defaults'):
    """
    Function to set defaults.
    :param _config ConfigParser: config parser to be edited
    :param str section: Relevant section
    """
    if not _config.has_section(section):
        _config[section] = {}
    if not _config.has_option(section, 'httpTimeout'):
        _config[section]['httpTimeout'] = '3.0'
    if not _config.has_option(section, 'gblTimeout'):
        _config[section]['gblTimeout'] = '1.0'
    if not _config.has_option(section, 'fwdir'):
        _config[section]['fwdir'] = 'fw'


def set_http_defaults(_config, section='httpDefaults'):
    """
    Function to set httpDefaults.
    :param _config ConfigParser: config parser to be edited
    :param str section: Relevant section
    """
    if not _config.has_section(section):
        _config[section] = {}
    if not _config.has_option(section, 'port'):
        _config[section]['port'] = '80'
    if not _config.has_option(section, 'ssl'):
        _config[section]['ssl'] = '0'
    if not _config.has_option(section, 'auth'):
        _config[section]['auth'] = '0'
    if not _config.has_option(section, 'username'):
        _config[section]['username'] = ''
    if not _config.has_option(section, 'password'):
        _config[section]['password'] = ''


def add_iprange_to_config(_iprange: str, _config: ConfigParser):
    """
    Function that adds hosts from args to hosts in _config (parsed hosts from upload.ini)
    :param str _iprange: ip, ip-sub-net OR hostname
    :param ConfigParser _config: local properties parsed from upload.ini
    """
    # add cmd line arg to ip list
    if _iprange is not None:
        for i, ip in enumerate(_iprange):
            log.debug(f"Adding iprange: {ip}")
            if ':' in ip and '/' not in ip:
                if (']' in ip and ':' in ip.rpartition(']')[2]) or ']' not in ip:
                    _config[ip] = {}
                    _config[ip]['port'] = ip.rpartition(':')[2]

            _config['hosts'][f'iprange_{i}'] = ip
    else:
        if len(_config['hosts']) == 0:
            log.error("no EPC/PDU device IP address(es) given.\n"
                      "\tPlease try to enable 'gbl=search' or 'ip1=192.168.0.1' in your upload.ini,\n"
                      "\tand/or give an IP address or subnet by --iprange parameter\n")
            raise KeyError("Missing required args, could not determine device!")


def generate_ip_list(_hosts: list, _my_ip: str, _gbl_timeout: float) -> list:
    """
    Function that adds hosts from args to hosts in _config (parsed hosts from upload.ini)
    :param list _hosts: list of ips, ip-sub-nets OR hostnames
    :param list _my_ip: this is the broadcaster/client ip, require for GBL/UDP search
    :param float _gbl_timeout: timeout in seconds to wait after sending broadcast

    :returns:
    - _ip_list - parsed args
    :rtype: list
    """
    _ip_list = []
    log.debug(f"Getting all IPs for hosts: {[addrRange for addrRange in _hosts]}")
    for addrRange in _hosts:
        log.debug(f"Checking host(s): {_hosts[addrRange]}")
        target = _hosts[addrRange]
        if target == "search":
            log.info("Searching devices by GBL UDP broadcast...")
            device_lst = Gblib.recv_bc(_my_ip, _gbl_timeout)
            for dev in device_lst:
                _ip_list.append(Gblib.get_dev_info(dev)['ip'])
        else:
            num_hosts = 0

            try:
                # TODO: Consider not using 'ipaddress' pkg?
                ip_addresses = ipaddress.ip_network(target).hosts()
            except ValueError:
                # from this point on target can only be a single device (no network)
                if '/' in target:
                    raise ValueError(f"{target} detected an IPv4 or IPv6 network, but can not be handled as it")
                else:
                    log.warning(f"{target} could not be parsed as nativ IPAddress or IP-Network, "
                                f"trying to handle without parsing...")
                    '''
                    new_target = socket.gethostbyname(target)
                    log.info(f"Resolved: {target} as: {new_target}, trying again...")
                    ip_addresses = ipaddress.ip_network(new_target).hosts()
                    '''
                    # TODO: This requires an additional CHECK!
                    # TODO: Keep in mind, that this only adds a str to a list containing also 'IPv4Address' objects!
                    # TODO: Give option to enter port in arguments (how to handle port?)
                    ip_addresses = [target]

            # THIS IS VERY HACKY (better to resolve all ips, but mapping to device dependant config will be complex)
            for ip in ip_addresses:
                _ip_list.append(ip)
                num_hosts += 1
            if num_hosts == 0:
                _ip_list.append(target)
    return _ip_list


def iterate_list(_ip_list: list, _firmware: ConfigParser, _config: ConfigParser, _args: object):
    """
    Function that iterates over all hosts from _ip_list hosts,
    matching corresponding firmware in _firmware,
    using http config given by _config,
    considering additional options from _args
    :param list _ip_list: list of ips, ip-sub-nets OR hostnames
    :param ConfigParser _firmware: containing firmware information
    :param ConfigParser _config: containing http config
    :param Namespace _args: additional options
    """

    # TODO: Is GBL in this context necessary?
    gbl = Gblib()

    log.debug(f"trying {len(_ip_list)} devices")
    for ip in _ip_list:
        log.debug("Initializing DeployDev")
        # TODO: ip can be str or 'IPv4Address' or 'IPv6Address'!
        if isinstance(ip, str) and ip.count(':') == 1:
            dev_ip = ip.split(':')[0]
        else:
            dev_ip = ip
        dev = DeployDev(dev_ip, req_headers=_args.header)

        # this ensures mapping of device dependant config
        config_key = ip if ip in _config else 'httpDefaults'

        set_http_defaults(_config, config_key)

        # config_key corresponds to the matching http configuration that can be found in upload.ini
        log.debug(f"Setting up DeployDev with config-key: {config_key}")
        dev.set_http_port(_config[config_key]['port'], _config[config_key]['ssl'] == '1')
        dev.set_basic_auth(_config[config_key]['auth'] == '1',
                           _config[config_key]['username'],
                           _config[config_key]['password'])
        dev.set_http_timeout(float(_config['defaults']['httpTimeout']))
        dev.set_http_retries(0)

        gbl_error = False
        try:
            # This hase been moved from top of function
            log.info(f"trying {ip}... (via GBL/UDP)")
            # update gbl info (dstMAC, bootl_mode, allow_go_boot, dev_info)
            try:
                if not gbl.check_mac(str(ip)):
                    log.warning("GBL Timeout (UDP port 50123)")
                    # continue
                    gbl_error = True
                # extract mac (bytes longer than 255 result in two hex values so b'\x192' results in 1*16+9 and 2*16+0)
                # this dec values need to be converted back to hex ('x') as string with the length 2 ('02')
                mac = '_'.join(f'{c:02x}' for c in gbl.dstMAC)
            except ConnectionResetError:
                log.error("Could not send broadcast, connection has been reset ...")
                gbl_error = True
        except gaierror:
            gbl_error = True
            # TODO: Resolve hostname beforehand?
            log.warning("Could not resolve address")
        if gbl_error:
            log.info(f"trying {ip}... (via HTTP(s) )")
            try:
                mac = dev.http_get_status_json(DeployDev.JSON_STATUS_ETHERNET, req_headers=None)['ethernet']['mac'].replace(':', '_')
                log.debug(f"got mac {mac}... (via HTTP(s) )")
            except TimeoutError:
                log.error(f"Could not reach device {ip}")
                continue
            except ValueError as ve:
                log.error(f"Could not reach device {ip} {ve}")
                continue
            except ConnectionError as ce:
                log.error(f"Could not reach device on defined port/protocol (http OR https) on {ip} {ce}")
                continue

        log.debug(f"Getting config filename ...")
        cfg_filename = DeployDev.get_config_filename('config', 'config', 'txt', mac, ip, _args.configip)
        log.debug(f"Getting ssl-cert filename ...")
        ssl_cert_filename = DeployDev.get_config_filename('ssl', 'cert', 'pem', mac, ip, _args.configip)

        # this may fail due to https
        # TODO: Rework?
        try:
            device_data = dev.http_get_status_json(DeployDev.JSON_STATUS_MISC)['misc']
        except ConnectionError as ce:
            log.error(f"Could not reach device on defined port/protocol (http OR https) on {ip} {ce}")
            continue

        # --- before logging/deploy ---
        actual_prod_id = device_data['prodid']
        selected_prod_id = None

        # 1) Try exact match on the original prodid
        if actual_prod_id in _firmware:
            selected_prod_id = actual_prod_id

        # 2) If no match yet, apply your replacement map
        if not selected_prod_id:
            repl_map = _args.repl_prod_id
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
            device_data["prodid"] = selected_prod_id
            log.info(
                f"{device_data['product_name']} "
                f"({actual_prod_id} → {selected_prod_id}, {mac}) at {ip}\n"
                + " " * 52
                + f"running Firmware v{device_data['firm_v']}"
            )
        else:
            log.warning(f"No firmware entry found for product '{actual_prod_id}'")
            # …handle missing‐firmware case (raise, skip, default, etc.)…

        try:
            # deploy Firmware
            if device_data['prodid'] in _firmware:
                dev.update_firmware(device_data, _firmware, _config['defaults']['fwdir'],
                                    forced=_args.forcefw, online_update=_args.onlineupdate)
        except ValueError as ve:
            log.warning(f"skipped firmware update: {ip} {ve}")

        # deploy Configuration
        if cfg_filename is not None:
            log.debug(f"Uploading {cfg_filename} ...")
            dev.upload_config(cfg_filename, _args.configip)

        # deploy SSL certificate
        if ssl_cert_filename is not None:
            log.debug(f"Uploading {ssl_cert_filename} ...")
            dev.upload_ssl_certificate(ssl_cert_filename)

        # print FW Version and configured Hostname
        ipv4 = dev.http_get_config_json(dev.JSON_CONFIG_IP)['ipv4']
        misc = dev.http_get_status_json(DeployDev.JSON_STATUS_MISC)['misc']
        log.info(f"device with IP {dev.host} has hostname {ipv4['hostname']} and FW Version {misc['firm_v']}")

        # except Exception as e:
        #     log.warning(f"skipped : {ip} {e}")


# get all args
args, config, firmware, my_ip = parse_args()

# parsing hosts
add_iprange_to_config(args.iprange, config)

# get all target ips
ip_list = generate_ip_list(config['hosts'], my_ip, float(config['defaults']['gblTimeout']))

# iterate devices, get each dev info, update fw, config and certificate
iterate_list(ip_list, firmware, config, args)
