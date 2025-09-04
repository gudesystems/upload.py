#!/usr/bin/python3
import argparse
import configparser
import requests

parser = argparse.ArgumentParser(prog='sensor')
parser.add_argument('-v', '--version_ini', help='fw version defs', default='version.ini')
args = parser.parse_args()

firmware = configparser.ConfigParser(strict=False)
firmware.read(args.version_ini)

basepath = 'https://files.gude-systems.com/fw/gude'
basepath_overwrite = False
latest = {}

if firmware.has_section('url') and firmware.has_option('url', 'basepath'):
    basepath = firmware['url']['basepath']
    basepath_overwrite = True

for devClass in firmware.sections():
    for (key, val) in firmware.items(devClass):
        if key == 'json':
            # check if subpath is used
            if basepath_overwrite and firmware.has_option(devClass, 'subpath'):
                url = f"{basepath}/{firmware[devClass]['subpath']}/{val}"
            else:
                url = f"{basepath}/{val}"
            print(f"downloading {url}")
            latest[devClass] = requests.get(url).json()[0]['version']

for (devClass, version) in latest.items():
    firmware[devClass]['version'] = version

    # download FW
    filename = firmware[devClass]['filename'].replace('{version}', version)
    # check if subpath is used
    if basepath_overwrite and firmware.has_option(devClass, 'subpath'):
        url = f"{basepath}/{firmware[devClass]['subpath']}/{filename}"
    else:
        url = f"{basepath}/{filename}"
    print(f"downloading {url}")
    r = requests.get(url)
    if r.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(r.content)

# write ini file
with open(args.version_ini, 'w') as inifile:
    firmware.write(inifile)
