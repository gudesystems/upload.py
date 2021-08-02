# upload.py
- automatically deploy firmware updates, configuration and/or ssl certificates to multiple **Gude Systems GmbH PDU devices**
- Firmware udpates can be obtained automatically by using --onlineupdates
- device configuration and ssl certificates, needs to prepared as pre-requirement


# QuickStart
- You need to prepare three elements:
  - **which devices**
  - **which firmware version**
  - **which configuration / ssl certificate**


- **which devices**
  - enable 'gbl=search' in upload.ini
    - to run a 'search' broadcast in your local network(s)
  - enable e.g. 'net1 = 192.168.1.0/24'
    - to probe a subnet
  - enable e.g. 'ip1 = 192.168.1.11' 
    - to probe a single device unit (or multiple units with ip2, ip3, etc...)
  - use 'upload.py --iprange 192.168.1.11'
    - to probe a single device unit
  - or any combination of parameters mentioned above


- **which firmware version**
  - use 'upload.py --onlineupdate' to use the most recent internet firmware files
    - firmware binary files are automatically downloaded to fw/*.bin
  - to run offline updates
    - download firmware binary files to fw/*.bin
    - set target version in fw/version.ini
  - to get online files and run offline updates later
    - run onlineupdates.py in subdir fw
    - this will download all binary files to fw/*.bin, and sets fw/version.ini accordingly


- **which configuration / ssl certificate**
  - when the firmware is already up to date or updated, upload.py can also deploy device configuration
    and/or ssl certificates per device
  - configuration
    - if file exists, config/config_[MAC_ADD].txt is deployed to this device
      - e.g. **config/config_00_19_32_00_00_01.txt**
    - of otherwise, and if file exists, config/config_[IP].txt is deployed to this device
      - e.g. **config/config_192_168_1_10.txt**
    - of otherwise, and if file exists, **config/config.txt** is deployed to each device
  - ssl certificate
    - upload.py looks out for files ssl/cert_[MAC_ADD].pem, ssl/cert_[IP].pem or
      cert.pem, as described above with configuration files
      - e.g. **ssl/cert_00_19_32_00_00_01.pem** or **ssl/cert_192_168_1_10.pem** 
 
    
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
- requests

# example
- which device(s): 10.113.6.66, given by --iprange
- which firmware: most recent, given by --onlineupdate
- which config: cli given by file config\config_00_19_32_00_e8_b6.txt

```
py D:/gude/upload.py/upload.py --onlineupdate --iprange 10.113.6.66
 
trying 1 devices
trying 10.113.6.66...
Expert Power Control 8041-1 (80xx, 00_19_32_00_e8_b6) at 10.113.6.66
        running Fimware v1.1.2
downloading http://files.gude.info/fw/gude/firmware-epc8031.json
downloading http://files.gude.info/fw/gude/firmware-epc8031_v1.1.3.bin
        updateing to Fimware v1.1.3
uploading firmware-epc8031_v1.1.3.bin, please wait...
uploading 1172046 bytes...
upload progress 2.36% 27624/1172046
upload progress 7.10% 83176/1172046
upload progress 11.84% 138728/1172046
upload progress 16.58% 194280/1172046
[...]
upload progress 87.54% 1026024/1172046
upload progress 92.26% 1081320/1172046
upload progress 96.98% 1136616/1172046
upload progress 100.00% 1172046/1172046
upload complete, device is checking file consistency...
upload complete
Firmware update 1.1.2 -> 1.1.3, device reboots to extract firmware file, please wait...
Rebooting...
.
[...]
 10.113.6.66:80 up
uploading config/config_00_19_32_00_e8_b6.txt, please wait...
upload complete, device reboots to apply config file, please wait...
Rebooting...
.
[...]
.
 10.113.6.66:80 up
uploading ssl/cert_00_19_32_00_e8_b6.pem, please wait...
upload complete, device reboots to apply cert file, please wait...
Rebooting...
Rebooting...
.
[...]
.
 10.113.6.66:80 up
device with IP 10.113.6.66 has hostame EPC-8041 and FW Version 1.1.3
```

