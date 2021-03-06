import os
import re
import time
import requests
import threading
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
    def getConfigFilename(subdir, prefix, fileext, macAddr, ip, configip=None):
        cfgFilename = None
        if configip is not None:
            cfgFilename = os.path.join(subdir, f"{prefix}_{configip}.{fileext}")

        if cfgFilename is None or not os.path.exists(cfgFilename):
            cfgFilename = os.path.join(subdir, f"{prefix}_{macAddr}.{fileext}")
            if not os.path.exists(cfgFilename):
                cfgFilename = os.path.join(subdir, f"{prefix}_{ip}.{fileext}")
                if not os.path.exists(cfgFilename):
                    cfgFilename = os.path.join(subdir, f"{prefix}.{fileext}")
                    if not os.path.exists(cfgFilename):
                        cfgFilename = None

        return cfgFilename

    def threadedUpload(self):
        print(f"uploading {len(self.fw)} bytes...")
        self.uploadFile(self.fw, self.CGI_UPLOAD_TYPE_FIRMWARE, timeout=300.0)
        print(f"upload complete")
        self.fw = None

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

        needsUpdate = forced or (latest_version != devVersion)
        if not needsUpdate:
            print(f"\texpected Fimware v{latest_version} : no update needed")
            return

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

        print(f"\tupdateing to Fimware v{latest_version}")

        if fwFilename is None:
            print("no update file given")
            return

        fw = self.getFileContent(localFilename, "rb")
        if fw is not None:
            print(f"uploading {fwFilename}, please wait...")
            self.fw = fw
            threading.Thread(target=self.threadedUpload, args=()).start()
            time.sleep(1)
            while self.fw is not None:
                uploadStatus = self.httpGetStatusJson(DeployDev.JSON_STATUS_UPLOAD)['fileupload']
                total = uploadStatus['total']
                progress = uploadStatus['progress']
                p = (100 / total) * progress
                print(f"upload progress {p:02.2f}% {uploadStatus['progress']}/{total}")
                time.sleep(2)
                if uploadStatus['checking']:
                    print(f"upload complete, device is checking file consistency...")
                    time.sleep(4)

            uploadStatus = self.httpGetStatusJson(DeployDev.JSON_STATUS_UPLOAD)['fileupload']
            fw = [uploadStatus['update']['from'], uploadStatus['update']['to']]
            print(f"Firmware update {fw[0][1]}.{fw[0][2]}.{fw[0][3]} -> {fw[1][1]}.{fw[1][2]}.{fw[1][3]}, "
                  f"device is rebooting to extract firmware file, please wait...")
            self.reboot(waitreboot=True, maxWaitSecs=120)

    def uploadConfig(self, cfgFileName, configip):
        cfg = self.getFileContent(cfgFileName)
        if cfg is None:
            return
        print(f"uploading {cfgFileName}, please wait...")
        self.uploadFile(cfg, self.CGI_UPLOAD_TYPE_CONFIG)
        print(f"upload complete, device is rebooting to apply config file, please wait...")
        self.reboot(waitreboot=False)
        if configip is not None:
            self.host = configip
        self.waitReboot(maxWaitSecs=60)

        # apply every 'port X state set Y' by http
        for port, state in re.findall(r'port (\d+) state set (\d)', cfg):
            newSate = self.httpSwitchPort(int(port), int(state))['outputs'][int(port) - 1]['state']
            print(f"cmd 'port {port} state set {state}' -> '{newSate}' (sleeping 1s)")
            time.sleep(1)

    def uploadSslCertifiate(self, sslCertFileName):
        cert = self.getFileContent(sslCertFileName)
        if cert is None:
            return
        print(f"uploading {sslCertFileName}, please wait...")
        self.uploadFile(cert, self.CGI_UPLOAD_TYPE_SSL_CERT)
        print(f"upload complete, device is rebooting to apply cert file, please wait...")
        self.reboot(waitreboot=True, maxWaitSecs=30)
