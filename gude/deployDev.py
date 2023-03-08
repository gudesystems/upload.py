import os
import re
import time
import requests
import threading
from gude.httpDevice import HttpDevice

from gude.gblib import print_progress_bar

import logging
# logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)  # custom logger name can be set
log.setLevel(logging.getLevelName('INFO'))


class DeployDev(HttpDevice):
    def __init__(self, host):
        super().__init__(host)
        self.fw = None

    @staticmethod
    def get_file_content(filename, read_opts="r"):
        content = None
        if filename is not None:
            if os.path.exists(filename):
                fp = open(filename, read_opts)
                content = fp.read()
                fp.close()
            else:
                log.warning(f"\tfile not found {filename}")
        return content

    @staticmethod
    def get_config_filename(subdir, prefix, file_ext, mac_addr, ip, config_ip=None):
        log.info(f"Searching .{file_ext} file, trying:")
        cfg_filename = None
        if config_ip is not None:
            cfg_filename = os.path.join(subdir, f"{prefix}_{config_ip}.{file_ext}")
            log.info(f"- {cfg_filename}")

        if cfg_filename is None or not os.path.exists(cfg_filename):
            cfg_filename = os.path.join(subdir, f"{prefix}_{mac_addr}.{file_ext}")
            log.info(f"- {cfg_filename}")
            if not os.path.exists(cfg_filename):
                cfg_filename = os.path.join(subdir, f"{prefix}_{ip}.{file_ext}")
                log.info(f"- {cfg_filename}")
                if not os.path.exists(cfg_filename):
                    cfg_filename = os.path.join(subdir, f"{prefix}.{file_ext}")
                    log.info(f"- {cfg_filename}")
        if not os.path.exists(cfg_filename):
            cfg_filename = None
            log.warning(f"Could not find {file_ext} file.")
        else:
            log.info(f"Found: {cfg_filename}")

        return cfg_filename

    def threaded_upload(self):
        log.info(f"uploading {len(self.fw)} bytes...")
        self.upload_file(self.fw, self.CGI_UPLOAD_TYPE_FIRMWARE, timeout=300.0)
        log.info(f"upload complete")
        self.fw = None

    def update_firmware(self, device_data, cfg, fw_dir='fw', forced=False, online_update=False):
        prodid = device_data['prodid']
        dev_version = device_data['firm_v']

        if online_update:
            # check online JSON for latest version
            url = f"{cfg['url']['basepath']}/{cfg[prodid]['json']}"
            log.info(f"downloading {url}")
            latest_version = requests.get(url).json()[0]['version']
        else:
            latest_version = cfg[prodid]['version']

        # R2 check requires appendix
        if 'R2' in prodid:
            latest_version += '-R2'

        needs_update = forced or (latest_version != dev_version)
        if not needs_update:
            log.warning(f"\texpected Fimware v{latest_version} : no update needed")
            return

        fw_filename = cfg[prodid]['filename'].replace('{version}', latest_version)
        local_filename = os.path.join(os.path.join(fw_dir, fw_filename))

        if not os.path.isfile(local_filename):
            if online_update:
                # download latest firmware
                url = f"{cfg['url']['basepath']}/{fw_filename}"
                log.info(f"downloading {url}")
                r = requests.get(url)
                if r.status_code == 200:
                    with open(local_filename, 'wb') as fwfile:
                        fwfile.write(r.content)
                else:
                    raise ValueError(f"Firmware file not found : {local_filename}")

        log.info(f"updating to Firmware v{latest_version}")

        if fw_filename is None:
            log.warning("no update file given")
            return

        fw = self.get_file_content(local_filename, "rb")
        if fw is not None:
            log.info(f"uploading {fw_filename}, please wait...")

            self.fw = fw

            threading.Thread(target=self.threaded_upload, args=()).start()
            time.sleep(1)
            while self.fw is not None:
                upload_status = self.http_get_status_json(DeployDev.JSON_STATUS_UPLOAD)['fileupload']
                total = upload_status['total']
                progress = upload_status['progress']
                # p = (100 / total) * progress
                # log.info(f"upload progress {p:02.2f}% {upload_status['progress']}/{total}")

                time.sleep(2)

                print_progress_bar(progress, total, fill='#', clear=' ', unit='bytes')

                if upload_status['checking']:
                    log.info(f"upload complete, device is checking file consistency...")
                    time.sleep(5)

            upload_status = self.http_get_status_json(DeployDev.JSON_STATUS_UPLOAD)['fileupload']
            fw = [upload_status['update']['from'], upload_status['update']['to']]

            log.info(f"Firmware update {fw[0][1]}.{fw[0][2]}.{fw[0][3]} -> {fw[1][1]}.{fw[1][2]}.{fw[1][3]}, "
                     f"device is rebooting to extract firmware file, please wait...")
            self.reboot(wait_reboot=True, max_wait_secs=85)

    def upload_config(self, cfg_file_name, config_ip):
        cfg = self.get_file_content(cfg_file_name)
        if cfg is None:
            return
        log.info(f"uploading {cfg_file_name}, please wait...")
        self.upload_file(cfg, self.CGI_UPLOAD_TYPE_CONFIG)
        log.info(f"upload complete, device is rebooting to apply config file, please wait...")
        self.reboot(wait_reboot=False)
        if config_ip is not None:
            self.host = config_ip
        self.wait_reboot(max_wait_secs=25)

        # apply every 'port X state set Y' by http
        for port, state in re.findall(r'port (\d+) state set (\d)', cfg):
            new_sate = self.http_switch_port(int(port), int(state))['outputs'][int(port) - 1]['state']
            log.info(f"cmd 'port {port} state set {state}' -> '{new_sate}' (sleeping 1s)")
            time.sleep(1)

    def upload_ssl_certificate(self, ssl_cert_file_name):
        cert = self.get_file_content(ssl_cert_file_name)
        if cert is None:
            return
        log.info(f"uploading {ssl_cert_file_name}, please wait...")
        self.upload_file(cert, self.CGI_UPLOAD_TYPE_SSL_CERT)
        log.info(f"upload complete, device is rebooting to apply cert file, please wait...")
        self.reboot(wait_reboot=True, max_wait_secs=10)
