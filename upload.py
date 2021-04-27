import configparser
import argparse
import os
import ipaddress
import re
import time
from gude.httpDevice import HttpDevice
from gude.gblib import Gblib

parser = argparse.ArgumentParser(prog='sensor')
parser.add_argument('--configip', help='ip address to select config')
parser.add_argument('--forcefw', help='upload fw even if already up to date', action="store_true")
args = parser.parse_args()

config = configparser.ConfigParser(strict=False)
config.read('upload.ini')
myIp = config['defaults']['myIp'] if 'myIp' in config['defaults'] else None

gbl = Gblib()


def getFileContent(filename, readOpts="r"):
    content = None
    if filename is not None:
        if os.path.exists(filename):
            fp = open(filename, readOpts)
            content = fp.read()
            fp.close()
        else:
            print(f"\tfile not found {filename}")
    return content


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
            cfgFilename = None
            if args.configip is not None:
                cfgFilename = os.path.join('config', f"config_{args.configip}.txt")

            if cfgFilename is None or not os.path.exists(cfgFilename):
                macAddr = '_'.join(f'{c:02x}' for c in gbl.dstMAC)
                cfgFilename = os.path.join('config', f"config_{macAddr}.txt")
                if not os.path.exists(cfgFilename):
                    cfgFilename = os.path.join('config', f"config_{ip}.txt")
                    if not os.path.exists(cfgFilename):
                        cfgFilename = os.path.join('config', f"config.txt")
                        if not os.path.exists(cfgFilename):
                            cfgFilename = None

        dev = HttpDevice(ip)
        configKey = ip if ip in config else 'httpDefaults'

        dev.setHttpPort(config[configKey]['port'], config[configKey]['ssl'] == '1')
        dev.setBasicAuth(config[configKey]['auth'] == '1', config[configKey]['username'], config[configKey]['password'])

        dev.setHttpTimeout(float(config['defaults']['httpTimeout']))
        dev.setHttpRetries(0)

        try:
            print(f"trying {ip}...")
            misc = dev.httpGetStatusJson(HttpDevice.JSON_STATUS_MISC)['misc']

            # update FW
            print(f"{misc['product_name']} ({misc['prodid']}) detected at {ip} running Fimware Version '{misc['firm_v']}'")
            if misc['prodid'] in config:
                needsUpdate = args.forcefw or (config[misc['prodid']]['fw'] != misc['firm_v'])
                print(f"\texpected FW {config[misc['prodid']]['fw']} needsUpdate({needsUpdate})")
                fwFilename = os.path.join('fw', config[misc['prodid']]['uploadFile'])
                if needsUpdate:
                    fw = getFileContent(fwFilename, "rb")
                    if fw is not None:
                        print(f"uploading {fwFilename}, please wait ... ")
                        dev.uploadFile(fw, dev.CGI_UPLOAD_TYPE_FIRMWARE)
                        print(f"upload complete, device reboots to extract firmware file, please wait...")
                        dev.reboot(waitreboot=True, maxWaitSecs=120)

            # upload config FW
            cfg = getFileContent(cfgFilename)
            if cfg is not None:
                print(f"uploading {cfgFilename}, please wait ... ")
                dev.uploadFile(cfg, dev.CGI_UPLOAD_TYPE_CONFIG)
                print(f"upload complete, device reboots to apply config file, please wait...")
                dev.reboot(waitreboot=False)
                if args.configip is not None:
                    dev.host = args.configip
                dev.waitReboot(maxWaitSecs=60)

                # apply every 'port X state set Y' by http
                for port, state in re.findall(r'port (\d+) state set (\d)', cfg):
                    newSate = dev.httpSwitchPort(int(port), int(state))['outputs'][int(port)-1]['state']
                    print(f"cmd 'port {port} state set {state}' -> '{newSate}' (sleeping 1s)")
                    time.sleep(1)

            # print FW Version and configured Hostname
            ipv4 = dev.httpGetConfigJson(dev.JSON_CONFIG_IP)['ipv4']
            misc = dev.httpGetStatusJson(HttpDevice.JSON_STATUS_MISC)['misc']
            print(f"device with IP {dev.host} has hostame {ipv4['hostname']} and FW Version {misc['firm_v']}")

        except Exception as e:
            print(f"skipped {ip} {e}")
