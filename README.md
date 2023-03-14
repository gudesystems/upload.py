# About upload.py
`upload.py` is a Script-Tool that aims to automatically deploy firmware updates, 
configuration and/or ssl certificates to multiple **Gude Systems GmbH PDU devices**

The Firmware udpates can be obtained automatically (by using `--onlineupdates`) or manually.

Device configuration and ssl certificates, can be prepared beforehand.

# Requirements
1. A `Python` capable device (e.g. PC).
   1. Minimum required: `Python Version 3.6`
   2. This Script is using `requests` python module
2. A **Gude Systems GmbH PDU device**

# Usage

There are two options to set individual commands either via **Command Line Parameters** or via `upload.ini`-config file.

## Preparation

### Essential
- Device selection
  - automatically detect device(s) to update
    - enable `gbl=search` in `upload.ini` to run a 'search' broadcast in your local network(s)
  - manually select device(s) to update
    - enable e.g. `net1 = 192.168.1.0/24`
      - to probe a subnet
    - enable e.g. `ip1 = 192.168.1.11`
      - to probe a single device unit (or multiple units with `ip2`, `ip3`, etc...)
    - use `--iprange 192.168.1.11` or `--iprange host/DNS` 
      - to probe a single device unit
  - any combination of parameters mentioned above can be combined
- Online update
  - use `--onlineupdate` to use the most recent internet firmware files
  (firmware binary files are automatically downloaded to `fw/*.bin`)

### Optional

- Get custom firmware version and save it under `fw/`
  - to run offline updates
    - download firmware binary files to `fw/*.bin`
    - set target version in `fw/version.ini`
  - to get online files and run offline updates later
    - run `onlineupdates.py` in subdir `fw/`
    - this will download all binary files to `fw/*.bin`, and sets `fw/version.ini` accordingly

- Prepare custom configuration and save it under `config/`
  - you can download / edit / down-strip / extend a device's live configuration by downloading `config.txt` at each device's maintenance page
  - you can use CLI commands to create your desired config file
    - a complete list of all CLI commands can be found in every device's PDF manual
  - if file exists, `config/config_[MAC_ADD].txt` is deployed to this device
    - e.g. `config/config_00_19_32_00_00_01.txt`
  - of otherwise, and if file exists, `config/config_[IP].txt` is deployed to this device
    - e.g. `config/config_192_168_1_10.txt`
  - of otherwise, and if file exists, `config/config.txt` is deployed to each device
- Prepare custom ssl certificate and save it under `ssl/`
  - upload.py looks out for files `ssl/cert_[MAC_ADD].pem`, `ssl/cert_[IP].pem` or `cert.pem`, 
  as described above with configuration files
    - e.g. `ssl/cert_00_19_32_00_00_01.pem` or `ssl/cert_192_168_1_10.pem` 
- when the firmware is already up to date or updated, `upload.py` can also deploy device configuration 
  and/or ssl certificates per device 

# Command Line Parameters
| Param            | Default       | Usage
|------------------|---------------|------------------
| `--forcefw`      |               | upload and extract firmware file, even if device is already up-to-date 
| `--upload_ini`   | `upload.ini`  | use alternative filename instead of upload.ini
| `--version_ini`  | `version.ini` | use alternative filename instead of fw/version.ini
| `--onlineupdate` |               | use online version info and download binary files
| `--iprange`      |               | add host / net to upload.ini's [host] section
| `--configip`     |               | if deploying a single device config, IP might change to this IP by config import 

# HTTPS / Authentication
- `upload.py` is using HTTP to upload config and firmware
- using HTTPS and user Authetification can be enabled in `upload.ini` 
- either tweak `[httpDefaults]` or the appropriate device section like e.g. `[192.168.1.11]`
  - `ssl=1` enabled HTTPS
  - giving username / password sets up HTTP Basic Authentication

# Example
- Selected device(s): `10.113.6.66`, given by `--iprange`
- Selected firmware: most recent, given by `--onlineupdate`
- Selected config: cli given by file `config\config_00_19_32_00_e8_b6.txt`

```
python .\upload.py --iprange 10.113.6.66 --onlineupdate
2022-10-11 11:44:18,400 __main__           INFO     trying 10.113.6.66...
2022-10-11 11:44:18,402 gude.deployDev     INFO     Searching .txt file, trying:
2022-10-11 11:44:18,402 gude.deployDev     INFO     - config\config_00_19_32_00_e8_b6.txt
2022-10-11 11:44:18,402 gude.deployDev     INFO     Found: config\config_00_19_32_00_e8_b6.txt
2022-10-11 11:44:18,402 gude.deployDev     INFO     Searching .pem file, trying:
2022-10-11 11:44:18,403 gude.deployDev     INFO     - ssl\cert_00_19_32_00_e8_b6.pem
2022-10-11 11:44:18,403 gude.deployDev     INFO     - ssl\cert_10.113.6.66.pem
2022-10-11 11:44:18,403 gude.deployDev     INFO     - ssl\cert.pem
2022-10-11 11:44:18,404 gude.deployDev     WARNING  Could not find pem file.
2022-10-11 11:44:18,444 __main__           INFO     Expert Power Control 1104-2 (1104, 00_19_32_00_e8_b6) at 10.113.6.66
                                                    running Firmware v1.3.0
2022-10-11 11:44:18,445 gude.deployDev     INFO     downloading https://files.gude-systems.com/fw/gude/firmware-epc1104.json
2022-10-11 11:44:18,548 gude.deployDev     INFO     downloading https://files.gude-systems.com/fw/gude/firmware-epc1104_v1.4.0.bin
2022-10-11 11:44:18,876 gude.deployDev     INFO     updating to Fimware v1.4.0
2022-10-11 11:44:18,878 gude.deployDev     INFO     uploading firmware-epc1104_v1.4.0.bin, please wait...
2022-10-11 11:44:18,879 gude.deployDev     INFO     uploading 1076287 bytes...
100.0% ########################################################################################## 1076287/1076287 bytes
2022-10-11 11:45:01,826 gude.deployDev     INFO     upload complete, device is checking file consistency...
2022-10-11 11:45:03,372 gude.deployDev     INFO     upload complete
2022-10-11 11:45:06,856 gude.deployDev     INFO     Firmware update 1.3.0 -> 1.4.0, device is rebooting to extract firmware file, please wait...
2022-10-11 11:45:06,857 gude.httpDevice    INFO     Rebooting...
100.0% ################################################################################################## 37/90 seconds
2022-10-11 11:45:44,214 gude.httpDevice    INFO     10.113.6.66:80 up
2022-10-11 11:45:45,222 gude.deployDev     INFO     uploading config\config_00_19_32_00_e8_b6.txt, please wait...
2022-10-11 11:45:45,445 gude.deployDev     INFO     upload complete, device is rebooting to apply config file, please wait...
2022-10-11 11:45:45,445 gude.httpDevice    INFO     Rebooting...
100.0% ################################################################################################## 5/30 seconds
2022-10-11 11:45:50,506 gude.httpDevice    INFO     10.113.6.66:80 up
2022-10-11 11:45:51,590 __main__           INFO     device with IP 10.113.6.66 has hostname EPC-1104 and FW Version 1.4.0
```
