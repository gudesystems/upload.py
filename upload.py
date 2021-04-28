import configparser
import argparse
import os
import ipaddress
from gude.deployDev import DeployDev
from gude.gblib import Gblib

parser = argparse.ArgumentParser(prog='sensor')
parser.add_argument('--configip', help='ip address to select config')
parser.add_argument('-f', '--forcefw', help='upload fw even if already up to date', action="store_true")
parser.add_argument('-u', '--upload_ini', help='upload.ini paramater set', default='upload.ini')
parser.add_argument('-v', '--version_ini', help='fw version defs', default='version.ini')
parser.add_argument('--onlineupdate', help='use online update files', action="store_true", default=False)
parser.add_argument('--iprange', help='range of ip address to manage')
args = parser.parse_args()

config = configparser.ConfigParser(strict=False)
config.read(args.upload_ini)

firmware = configparser.ConfigParser(strict=False)
firmware.read(os.path.join('fw', args.version_ini))

myIp = config['defaults']['myIp'] if 'myIp' in config['defaults'] else None

gbl = Gblib()

# add cmd line arg to ip list
if args.iprange is not None:
    config['hosts']['iprange'] = args.iprange

for addrRange in config['hosts']:
    target = config['hosts'][addrRange]
    if target == "search":
        ipList = []

        print("Searching devices...")
        device_lst = Gblib.recv_bc(myIp, float(config['defaults']['gblTimeout']))
        for dev in device_lst:
            ipList.append(Gblib.get_dev_info(dev)['ip'])
    else:
        ipList = ipaddress.IPv4Network(target)

    for ip in ipList:
        print(ip)
        if not gbl.check_mac(str(ip)):
            print("cannot query dev by check_mac()")
            exit(1)
        else:
            mac = '_'.join(f'{c:02x}' for c in gbl.dstMAC)
            cfgFilename = DeployDev.getConfigFilename(mac, ip, args.configip)

        dev = DeployDev(ip)
        configKey = ip if ip in config else 'httpDefaults'

        dev.setHttpPort(config[configKey]['port'], config[configKey]['ssl'] == '1')
        dev.setBasicAuth(config[configKey]['auth'] == '1', config[configKey]['username'], config[configKey]['password'])

        dev.setHttpTimeout(float(config['defaults']['httpTimeout']))
        dev.setHttpRetries(0)

        try:
            print(f"trying {ip}...")
            deviceData = dev.httpGetStatusJson(DeployDev.JSON_STATUS_MISC)['misc']
            print(f"{deviceData['product_name']} ({deviceData['prodid']}) detected at {ip} running Fimware Version '{deviceData['firm_v']}'")

            # deploy Firmware
            if deviceData['prodid'] in firmware:
                dev.updateFirmware(deviceData, firmware, config['defaults']['fwdir'],
                                   forced=args.forcefw, onlineUpdate=args.onlineupdate)

            # deploy Configuration
            if cfgFilename is not None:
                dev.uploadConfig(cfgFilename, args.configip)

            # print FW Version and configured Hostname
            ipv4 = dev.httpGetConfigJson(dev.JSON_CONFIG_IP)['ipv4']
            misc = dev.httpGetStatusJson(DeployDev.JSON_STATUS_MISC)['misc']
            print(f"device with IP {dev.host} has hostame {ipv4['hostname']} and FW Version {misc['firm_v']}")

        except Exception as e:
            print(f"skipped : {ip} {e}")
