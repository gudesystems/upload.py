#!/usr/bin/python3

from configparser import ConfigParser
from argparse import ArgumentParser, Namespace
import os
import ipaddress
import socket
from typing import Tuple

from gude.deployDev import DeployDev
from gude.gblib import Gblib

import logging
logging.basicConfig(format='%(asctime)s %(name)-18s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)  # custom logger name can be set
log.setLevel(logging.getLevelName('INFO'))


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
    parser.add_argument('--configip', help='ip address to select config')
    parser.add_argument('-f', '--forcefw', help='upload fw even if already up to date', action="store_true")
    parser.add_argument('-u', '--upload_ini', help='upload.ini paramater set', default='upload.ini')
    parser.add_argument('-v', '--version_ini', help='fw version defs', default='version.ini')
    parser.add_argument('--onlineupdate', help='use online update files', action="store_true", default=False)
    parser.add_argument('--iprange', nargs = "+", help='range of ip address to manage')
    _args = parser.parse_args()

    log.debug(f"Reading {_args.upload_ini} ...")
    _config = ConfigParser(strict=False)
    _config.read(_args.upload_ini)
    log.debug(f"Reading {os.path.join(_config['defaults']['fwdir'], _args.version_ini)} ...")
    _firmware = ConfigParser(strict=False)
    _firmware.read(os.path.join(_config['defaults']['fwdir'], _args.version_ini))

    log.debug("Getting my IP ...")
    _my_ip = _config['defaults']['myIp'] if 'myIp' in _config['defaults'] else '0.0.0.0'

    return _args, _config, _firmware, _my_ip


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
            _config['hosts'][f'iprange_{i}'] = ip
    else:
        if len(_config['hosts']) == 0:
            log.error("no EPC/PDU device IP address(es) given.\n"
                      "\tPlease try to enable 'gbl=search' or 'ip1=192.168.0.1' in your upload.ini,\n"
                      "\tand/or give an IP address or subnet by --iprange parameter\n")
            raise KeyError("Missing required args, could not determine device!")


def generate_ip_list(_hosts: list, _gbl_timeout: float) -> list:
    """
    Function that adds hosts from args to hosts in _config (parsed hosts from upload.ini)
    :param list _hosts: list of ips, ip-sub-nets OR hostnames
    :param float _gbl_timeout: timeout in seconds to wait after sending broadcast

    :returns:
    - _ip_list - parsed args
    :rtype: list
    """
    _ip_list = []
    log.debug(f"Getting all IPs for hosts: {_hosts}")
    for addrRange in _hosts:
        log.debug(f"Checking for hosts: {_hosts}")
        target = _hosts[addrRange]
        if target == "search":
            log.info("Searching devices by GBL UDP broadcast...")
            device_lst = Gblib.recv_bc(myIp, _gbl_timeout)
            for dev in device_lst:
                _ip_list.append(Gblib.get_dev_info(dev)['ip'])
        else:
            num_hosts = 0

            try:
                ip_addresses = ipaddress.ip_network(target).hosts()
            except ValueError:
                # from this point on target can only be a single device (no network)
                if '/' in target:
                    raise ValueError(f"{target} does not appear to be an IPv4 or IPv6 network")
                else:
                    log.warning(f"Could not detect IP: {target}, trying to resolve potential hostname...")
                    new_target = socket.gethostbyname(target)
                    log.info(f"Resolved: {target} as: {new_target}, trying again...")
                    ip_addresses = ipaddress.ip_network(new_target).hosts()

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
    gbl = Gblib()

    log.debug(f"trying {len(_ip_list)} devices")
    for ip in _ip_list:
        log.info(f"trying {ip}...")
        # update gbl info (dstMAC, bootl_mode, allow_go_boot, dev_info)
        if not gbl.check_mac(str(ip)):
            log.warning("GBL Timeout (UDP port 50123)")
            continue
        # extract mac
        mac = '_'.join(f'{c:02x}' for c in gbl.dstMAC)
        log.debug(f"Getting config filename ...")
        cfg_filename = DeployDev.get_config_filename('config', 'config', 'txt', mac, ip, _args.configip)
        log.debug(f"Getting ssl-cert filename ...")
        ssl_cert_filename = DeployDev.get_config_filename('ssl', 'cert', 'pem', mac, ip, _args.configip)

        log.debug("Initializing DeployDev")
        dev = DeployDev(ip)
        config_key = ip if ip in _config else 'httpDefaults'

        # config_key corresponds to the matching http configuration that can be found in upload.ini
        log.debug(f"Setting up DeployDev with config-key: {config_key}")
        dev.set_http_port(_config[config_key]['port'], _config[config_key]['ssl'] == '1')
        dev.set_basic_auth(_config[config_key]['auth'] == '1',
                           _config[config_key]['username'],
                           _config[config_key]['password'])
        dev.set_http_timeout(float(_config['defaults']['httpTimeout']))
        dev.set_http_retries(0)

        try:
            device_data = dev.http_get_status_json(DeployDev.JSON_STATUS_MISC)['misc']

            log.info(f"{device_data['product_name']} ({device_data['prodid']}, {mac}) at {ip}\n"+(52*" ")
                     + f"running Firmware v{device_data['firm_v']}")

            try:
                # deploy Firmware
                if device_data['prodid'] in _firmware:
                    log.debug(f"Found {device_data['prodid']} in firmware list, starting update ...")
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

        except Exception as e:
            log.warning(f"skipped : {ip} {e}")


# get all args
args, config, firmware, myIp = parse_args()

# parsing hosts
add_iprange_to_config(args.iprange, config)

# get all target ips
ip_list = generate_ip_list(config['hosts'], float(config['defaults']['gblTimeout']))

# iterate devices, get each dev info, update fw, config and certificate
iterate_list(ip_list, firmware, config, args)
