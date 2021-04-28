# upload.py
automatically deploy configuration and/or firmware updates to multiple **Gude Systems GmbH PDU devices**


# QuickStart
- You need to prepare three elements:
  - **which devices**
  - **which firmware version**
  - **which configuration**


- **which devices**
  - enable 'gbl=search' in upload.ini
    - to run a 'search' Broadcast in local network(s)
  - enable e.g. 'net1 = 192.168.1.0/24'
    - to probe a subnet
  - enable e.g. 'ip1 = 192.168.1.11' 
    - to probe a single device unit
  - use 'upload.py --iprange 192.168.1.11'
    - to probe a single device unit
  - or any combination of paramaters mentioned above


- **which firmare version**
  - use 'upload.py --onlineupdate to use the most recent internet firmware files
    - firmware binary files are automatically downloaded to fw/*.bin
  - to run offline updates
    - download firmware binary files to fw/*.bin
    - set target version in fw/version.ini
  - to get online files and run offline updates later
    - run onlineupdates.py in subdir fw
    - this will download all binary files to fw/*.bin, and sets fw/version.ini accordingly


- **which is configuration**
  - when the firmware is already up to date or updated, upload.py can also deploy device config
  - if file exists, config/config_[MAC_ADD].txt is deployed to this decvice
    - e.g. **config/config_00_19_32_00_00_01.txt**
  - of otherwise, and if file exists, config/config_[IP].txt is deployed to this decvice
    - e.g. **config/config_192_168_1_10.txt**
  - of otherwise, and if file exists, **config/config.txt** is deployed to each device
 
    
# create config
- you can download / edit / downstrip / extend device's live configuration by downloading config.txt at each device's maintanace page
- you can use CLI commands to create your desired config file

# Command Line Parameters
| Param           | Default      | Usage
|-----------------|--------------|------------------
| --forcefw       |              | upload and extract firmware file, even if device is already up-to-date 
| --upload_ini    | upload.ini   | use alternative filename instead of upload.ini
| --version_ini   | version.ini  | use alternative filename instead of fw/version.ini
| --onlineupdate  |              | use online version info and download binary files
| --iprange       |              | add host / net to upload.ini's [host] section
| --configip      |              | if deploying a single device config, IP might change to this IP by config import 


# HTTPS / authentification
- upload.py is using http to upload config and firmware
- using HTTPS and user Authetification can be enabled in upload.ini 
- either tweak [httpDefaults] or the apprortiate decvice section like e.g. [192.168.1.11]
  - ssl=1 enabled HTTPS
  - username / password sets up HTTP Basic Authentifaction 

# required non-standard python modules
- crcmod
- netifaces
- requests

