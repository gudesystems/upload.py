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
log.setLevel(logging.getLevelName('DEBUG'))


class DeployDev(HttpDevice):
    def __init__(self, host, req_headers=None):
        super().__init__(host, req_headers)
        self.fw = None
        self.firmware_upload_connection_error_info = None

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
        try:
            # This call is specifically for firmware
            self.upload_file(self.fw, self.CGI_UPLOAD_TYPE_FIRMWARE, timeout=300.0)
            log.info(f"upload_file call completed for firmware.")
        except requests.exceptions.ConnectionError as e:
            log.warning(f"ConnectionError during firmware upload_file call: {e}. Device might still process the file.")
            self.firmware_upload_connection_error_info = str(e) # Store specific info
        except Exception as e:
            log.error(f"Other exception during firmware upload_file call: {e}")
            self.firmware_upload_connection_error_info = f"Other upload error: {str(e)}"
        finally:
            log.info(f"Threaded firmware upload processing finished, setting self.fw to None.")
            self.fw = None # Ensure this is always set to allow main thread to proceed

    def update_firmware(self, device_data, cfg, fw_dir='fw', forced=False, online_update=False):
        prodid = device_data['prodid']
        dev_version = device_data['firm_v']
        initial_dev_version = dev_version # Store initial version for reporting

        # Reset connection error info for this attempt
        self.firmware_upload_connection_error_info = None

        if online_update:
            # check online JSON for latest version
            # check if subpath is used
            if cfg.has_option(prodid, 'subpath'):
                url = f"{cfg['url']['basepath']}/{cfg[prodid]['subpath']}/{cfg[prodid]['json']}"
            else:
                url = f"{cfg['url']['basepath']}/{cfg[prodid]['json']}"
            log.info(f"downloading {url}")
            latest_version = requests.get(url).json()[0]['version']
        else:
            latest_version = cfg[prodid]['version']

        needs_update = forced
        if not forced:
            # Logic for checking if update is needed
            if 'R2' in prodid and ("R2" not in latest_version and "r2" not in latest_version) and 'BUILD' not in dev_version:
                needs_update = (latest_version + '-R2' != dev_version)
            else:
                needs_update = (latest_version != dev_version)

        if not needs_update:
            log.warning(f"\tDevice Firmware v{dev_version} is already expected v{latest_version} or v{latest_version + '-R2' if 'R2' in prodid else ''} : no update needed")
            return {
                "updated": False,
                "initial_version": initial_dev_version,
                "final_version": initial_dev_version,
                "status_message": f"up to date (v{initial_dev_version})",
                "upload_notes": None
            }

        fw_filename = cfg[prodid]['filename'].replace('{version}', latest_version)
        if cfg.has_option(prodid, 'path'):
            fw_dir = cfg[prodid]['path']
        local_filename = os.path.join(os.path.join(fw_dir, fw_filename))

        if not os.path.isfile(local_filename):
            if online_update:
                # download latest firmware
                if cfg.has_option(prodid, 'subpath'):
                    url = f"{cfg['url']['basepath']}/{cfg[prodid]['subpath']}/{fw_filename}"
                else:
                    url = f"{cfg['url']['basepath']}/{fw_filename}"
                log.info(f"downloading {url}")
                r = requests.get(url)
                if r.status_code == 200:
                    # ensure target directory exists before writing the file
                    target_dir = os.path.dirname(local_filename)
                    if target_dir:
                        try:
                            os.makedirs(target_dir, exist_ok=True)
                        except Exception as e:
                            raise ValueError(f"Could not create firmware directory '{target_dir}': {e}")
                    with open(local_filename, 'wb') as fwfile:
                        fwfile.write(r.content)
                else:
                    raise ValueError(f"Firmware file not found (online): {local_filename}")
            else:
                raise ValueError(f"Firmware file not found (offline): {local_filename}")

        log.info(f"updating to Firmware v{latest_version}")

        fw_content = self.get_file_content(local_filename, "rb")
        if fw_content is None: # Should be caught by ValueError above if file not found
             raise ValueError(f"Could not read firmware file content: {local_filename}")
        
        log.info(f"uploading {fw_filename}, please wait...")

        self.fw = fw_content # Set self.fw for the thread

        # with pf this may raise a requests.exceptions.ConnectionError: HTTPConnectionPool(host='', port=''): Read timed out.
        upload_thread = threading.Thread(target=self.threaded_upload, args=())
        upload_thread.start()
        time.sleep(2)

        upload_status_after_thread = None
        while self.fw is not None:
            try:
                upload_status = self.http_get_status_json(DeployDev.JSON_STATUS_UPLOAD)['fileupload']
                upload_status_after_thread = upload_status
                total = upload_status['total']
                progress = upload_status['progress']
                # p = (100 / total) * progress
                # log.info(f"upload progress {p:02.2f}% {upload_status['progress']}/{total}")

                print_progress_bar(progress, total, fill='#', clear=' ', unit='bytes')

                if upload_status['checking']:
                    log.info(f"upload complete, device is checking file consistency...")
                    time.sleep(5)
            except (requests.exceptions.RequestException, ValueError) as e:
                log.warning(f"Could not get upload status during firmware update: {e}. Continuing...")
            # If we can't get status, we rely on the thread's outcome and post-reboot check
            time.sleep(2) # Wait before retrying or fw becomes None

        # After the loop, ensure the thread has fully completed
        log.debug("Waiting for firmware upload thread to join...")
        upload_thread.join(timeout=15.0) # Wait for up to 15 seconds for the thread to finish
        if upload_thread.is_alive():
            log.warning("Firmware upload thread did not complete within timeout after self.fw was set to None. It might be stuck.")
        else:
            log.debug("Firmware upload thread has joined.")

        # Thread has finished (self.fw is None)
        # Get final upload status if possible, or use last known
        try:
            upload_status_final_check = self.http_get_status_json(DeployDev.JSON_STATUS_UPLOAD)['fileupload']
            upload_status_after_thread = upload_status_final_check
        except (requests.exceptions.RequestException, ValueError) as e:
            log.warning(f"Could not get final upload status after thread: {e}. Using last known status if available.")

        fw_versions_log_info = "unknown versions"
        if upload_status_after_thread and 'update' in upload_status_after_thread and upload_status_after_thread['update']:
            # fw = [upload_status['update']['from'], upload_status['update']['to']]
            from_v = upload_status_after_thread['update']['from']
            to_v = upload_status_after_thread['update']['to']
            fw_versions_log_info = f"{from_v[1]}.{from_v[2]}.{from_v[3]} -> {to_v[1]}.{to_v[2]}.{to_v[3]}"

        log.info(f"Firmware update based on device status: {fw_versions_log_info}, "
                 f"device is rebooting to extract firmware file, please wait...")
        
        reboot_successful = self.reboot(wait_reboot=True, max_wait_secs=85)

        new_actual_version = initial_dev_version # Default to old if reboot fails or version can't be read
        is_successful_fw_update = False
        status_message = ""
        upload_notes_message = None

        if reboot_successful:
            try:
                # Fetch fresh device info after reboot
                misc_info_after_reboot = self.http_get_status_json(DeployDev.JSON_STATUS_MISC)['misc']
                new_actual_version = misc_info_after_reboot['firm_v']
                log.info(f"Device rebooted. Current firmware version: {new_actual_version}")

                # Determine if update was successful based on version comparison
                expected_target_version = latest_version
                if 'R2' in prodid and ("R2" not in latest_version and "r2" not in latest_version) and 'BUILD' not in new_actual_version:
                    expected_target_version = latest_version + '-R2'

                is_successful_fw_update = (new_actual_version == expected_target_version)

                if is_successful_fw_update:
                    status_message = f"updated from {initial_dev_version} to {new_actual_version}"
                    if self.firmware_upload_connection_error_info:
                        upload_notes_message = f"Transient connection error during upload ({self.firmware_upload_connection_error_info}), but update succeeded."
                else:
                    status_message = f"failed: version mismatch post-update (expected {expected_target_version}, got {new_actual_version})"
                    if self.firmware_upload_connection_error_info:
                         upload_notes_message = f"Original upload connection error: {self.firmware_upload_connection_error_info}."
            except (requests.exceptions.RequestException, ValueError) as e:
                log.error(f"Failed to get device status after reboot: {e}")
                status_message = f"failed: could not verify version after reboot ({e})"
                if self.firmware_upload_connection_error_info:
                    upload_notes_message = f"Original upload connection error: {self.firmware_upload_connection_error_info}."
        else: # Reboot failed
            new_actual_version = initial_dev_version # Stays old version
            status_message = "failed: reboot failed after firmware update attempt"
            if self.firmware_upload_connection_error_info:
                upload_notes_message = f"Original upload connection error: {self.firmware_upload_connection_error_info}."

        return {
            "updated": is_successful_fw_update,
            "initial_version": initial_dev_version,
            "final_version": new_actual_version,
            "status_message": status_message,
            "upload_notes": upload_notes_message
        }

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
