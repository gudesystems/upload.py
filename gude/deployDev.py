import os
import re
import time
import requests
from gude.httpDevice import HttpDevice


class DeployDev(HttpDevice):
    @staticmethod
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

    @staticmethod
    def getConfigFilename(macAddr, ip, configip=None):
        cfgFilename = None
        if configip is not None:
            cfgFilename = os.path.join('config', f"config_{configip}.txt")

        if cfgFilename is None or not os.path.exists(cfgFilename):
            cfgFilename = os.path.join('config', f"config_{macAddr}.txt")
            if not os.path.exists(cfgFilename):
                cfgFilename = os.path.join('config', f"config_{ip}.txt")
                if not os.path.exists(cfgFilename):
                    cfgFilename = os.path.join('config', f"config.txt")
                    if not os.path.exists(cfgFilename):
                        cfgFilename = None

        return cfgFilename

    def updateFirmware(self, deviceData, cfg, fwdir='fw', forced=False, onlineUpdate=False):
        prodid = deviceData['prodid']
        devVersion = deviceData['firm_v']

        if onlineUpdate:
            # check online JSON for latest version
            url = f"{cfg['url']['basepath']}/{cfg[prodid]['json']}"
            print(f"downloading {url}")
            latest_version = requests.get(url).json()[0]['version']
        else:
            latest_version = cfg[prodid]['version']

        fwFilename = cfg[prodid]['filename'].replace('{version}', latest_version)
        localFilename = os.path.join(os.path.join(fwdir, fwFilename))

        if not os.path.isfile(localFilename):
            if onlineUpdate:
                # download latest firmware
                url = f"{cfg['url']['basepath']}/{fwFilename}"
                print(f"downloading {url}")
                r = requests.get(url)
                if r.status_code == 200:
                    with open(localFilename, 'wb') as fwfile:
                        fwfile.write(r.content)
            else:
                raise ValueError(f"Firmare file not found : {localFilename}")
                fwFilename = None

        needsUpdate = forced or (latest_version != devVersion)
        print(f"\texpected FW {latest_version} needsUpdate({needsUpdate})")
        if needsUpdate and fwFilename is not None:
            fw = self.getFileContent(localFilename, "rb")
            if fw is not None:
                print(f"uploading {fwFilename}, please wait ... ")
                self.uploadFile(fw, self.CGI_UPLOAD_TYPE_FIRMWARE)
                print(f"upload complete, device reboots to extract firmware file, please wait...")
                self.reboot(waitreboot=True, maxWaitSecs=120)

    def uploadConfig(self, cfgFileName, configip):
        cfg = self.getFileContent(cfgFileName)
        if cfg is not None:
            print(f"uploading {cfgFileName}, please wait ... ")
            self.uploadFile(cfg, self.CGI_UPLOAD_TYPE_CONFIG)
            print(f"upload complete, device reboots to apply config file, please wait...")
            self.reboot(waitreboot=False)
            if configip is not None:
                self.host = configip
            self.waitReboot(maxWaitSecs=60)

            # apply every 'port X state set Y' by http
            for port, state in re.findall(r'port (\d+) state set (\d)', cfg):
                newSate = self.httpSwitchPort(int(port), int(state))['outputs'][int(port) - 1]['state']
                print(f"cmd 'port {port} state set {state}' -> '{newSate}' (sleeping 1s)")
                time.sleep(1)


