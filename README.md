# upload.py
automatically deploy configuration and/or firmware updates to multiple **Gude Systems GmbH PDU devices**


# QuickStart
- You need to prepare three elements:
  - **which devices**
  - **which firmware version**
  - **which configuration**


- **which devices**
  - enable 'gbl=search' in upload.ini
    - to run a 'search' Broadcast in your local network(s)
  - enable e.g. 'net1 = 192.168.1.0/24'
    - to probe a subnet
  - enable e.g. 'ip1 = 192.168.1.11' 
    - to probe a single device unit (or multiple with ip2, ip3, etc...)
  - use 'upload.py --iprange 192.168.1.11'
    - to probe a single device unit
  - or any combination of parameters mentioned above


- **which firmware version**
  - use 'upload.py --onlineupdate to use the most recent internet firmware files
    - firmware binary files are automatically downloaded to fw/*.bin
  - to run offline updates
    - download firmware binary files to fw/*.bin
    - set target version in fw/version.ini
  - to get online files and run offline updates later
    - run onlineupdates.py in subdir fw
    - this will download all binary files to fw/*.bin, and sets fw/version.ini accordingly


- **which configuration**
  - when the firmware is already up to date or updated, upload.py can also deploy device configuration
  - if file exists, config/config_[MAC_ADD].txt is deployed to this device
    - e.g. **config/config_00_19_32_00_00_01.txt**
  - of otherwise, and if file exists, config/config_[IP].txt is deployed to this device
    - e.g. **config/config_192_168_1_10.txt**
  - of otherwise, and if file exists, **config/config.txt** is deployed to each device
 
    
# create config
- you can download / edit / down-strip / extend a device's live configuration by downloading config.txt at each device's maintenance page
- you can use CLI commands to create your desired config file
  - a complete list of all CLI commands can be found in every device's PDF manual

# Command Line Parameters
| Param           | Default      | Usage
|-----------------|--------------|------------------
| --forcefw       |              | upload and extract firmware file, even if device is already up-to-date 
| --upload_ini    | upload.ini   | use alternative filename instead of upload.ini
| --version_ini   | version.ini  | use alternative filename instead of fw/version.ini
| --onlineupdate  |              | use online version info and download binary files
| --iprange       |              | add host / net to upload.ini's [host] section
| --configip      |              | if deploying a single device config, IP might change to this IP by config import 


# HTTPS / Authentication
- upload.py is using HTTP to upload config and firmware
- using HTTPS and user Authetification can be enabled in upload.ini 
- either tweak [httpDefaults] or the appropriate device section like e.g. [192.168.1.11]
  - ssl=1 enabled HTTPS
  - giving username / password sets up HTTP Basic Authentication 

# required non-standard python modules
- crcmod
- netifaces
- requests

# example
- which device(s): 10.113.6.66, given by --iprange
- which firmware: most recent, given by --onlineupdate
- which config: cli given by file config\config_00_19_32_00_e8_b6.txt

```
py D:/gude/upload.py/upload.py --onlineupdate --iprange 10.113.6.66
 
trying 10.113.6.66...
Expert Power Control 8041-1 (80xx) detected at 10.113.6.66 running Fimware Version '1.0.2'
downloading http://files.gude.info/fw/gude/firmware-epc8031.json
	expected FW 1.1.3 needsUpdate(True)
uploading firmware-epc8031_v1.1.3.bin, please wait ... 
upload complete, device reboots to extract firmware file, please wait...
Rebooting...
.
.
.
.
 10.113.6.66:80 up
device with IP 10.113.6.66 has hostame EPC-8041 and FW Version 1.1.3

uploading config\config_00_19_32_00_e8_b6.txt, please wait ... 
upload complete, device reboots to apply config file, please wait...
Rebooting...
.
.
.
 10.113.6.66:80 up
device with IP 10.113.6.66 has hostame EPC-8041 and FW Version 1.1.3
```
