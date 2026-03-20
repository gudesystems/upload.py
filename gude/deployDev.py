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
    def get_config_filename(subdir, prefix, file_ext, mac_addr, ip, config_ip=None, explicit_filename=None):
        log.info(f"Searching .{file_ext} file, trying:")
        cfg_filename = None

        if explicit_filename:
            # If explicit name provided (e.g. via UI upload), treat as priority.
            # We assume it's in the same subdir (e.g. config/foo.txt) if it's just a filename.
            # If it's a full path, os.path.join handles it (on windows, absolute path triggers override behavior).
            # But usually we just get the basename from the UI logic/upload.py.
            cfg_filename = os.path.join(subdir, explicit_filename)
            if os.path.exists(cfg_filename):
                 log.info(f"- Explicit match: {cfg_filename}")
                 return cfg_filename
            else:
                 log.warning(f"- Explicit filename given but not found: {cfg_filename}")
                 # Fallback to search or return None?
                 # If user explicitly requested it, we should probably fail/return None if missing
                 # rather than unexpected fallback.
                 return None
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
        log.info(f"[{self.host}] uploading {len(self.fw)} bytes...")
        try:
            # This call is specifically for firmware
            self.upload_file(self.fw, self.CGI_UPLOAD_TYPE_FIRMWARE, timeout=300.0)
            log.info(f"[{self.host}] upload_file call completed for firmware.")
        except requests.exceptions.ConnectionError as e:
            log.warning(f"[{self.host}] ConnectionError during firmware upload_file call: {e}. Device might still process the file.")
            self.firmware_upload_connection_error_info = str(e) # Store specific info
        except Exception as e:
            log.error(f"[{self.host}] Other exception during firmware upload_file call: {e}")
            self.firmware_upload_connection_error_info = f"Other upload error: {str(e)}"
        finally:
            log.info(f"[{self.host}] Threaded firmware upload processing finished, setting self.fw to None.")
            self.fw = None # Ensure this is always set to allow main thread to proceed

    def update_firmware(self, device_data, cfg, fw_dir='fw', forced=False, online_update=False, show_progress_bar=True, progress_cb=None):
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
            log.info(f"[{self.host}] downloading {url}")
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
                log.info(f"[{self.host}] downloading {url}")
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

        log.info(f"[{self.host}] updating to Firmware v{latest_version}")

        fw_content = self.get_file_content(local_filename, "rb")
        if fw_content is None: # Should be caught by ValueError above if file not found
             raise ValueError(f"Could not read firmware file content: {local_filename}")
        
        log.info(f"[{self.host}] uploading {fw_filename}, please wait...")

        self.fw = fw_content # Set self.fw for the thread

        log.info(f"[{self.host}] updating to Firmware v{latest_version}")

        fw_content = self.get_file_content(local_filename, "rb")
        if fw_content is None: # Should be caught by ValueError above if file not found
             raise ValueError(f"Could not read firmware file content: {local_filename}")
        
        log.info(f"[{self.host}] uploading {fw_filename}, please wait...")

        self.fw = fw_content # Set self.fw for the thread

        # with pf this may raise a requests.exceptions.ConnectionError: HTTPConnectionPool(host='', port=''): Read timed out.
        upload_thread = threading.Thread(target=self.threaded_upload, args=())
        upload_thread.start()
        time.sleep(2)

        upload_status_after_thread = None
        last_logged_progress = None
        while self.fw is not None:
            try:
                upload_status = self.http_get_status_json(DeployDev.JSON_STATUS_UPLOAD)['fileupload']
                upload_status_after_thread = upload_status
                total = upload_status['total']
                progress = upload_status['progress']
                # p = (100 / total) * progress
                # log.info(f"upload progress {p:02.2f}% {upload_status['progress']}/{total}")

                if show_progress_bar:
                    print_progress_bar(progress, total, fill='#', clear=' ', unit='bytes')
                else:
                    pct = (100 / total) * progress if total > 0 else 0
                    if progress_cb:
                        progress_cb({"ip": self.host, "type": "progress", "progress": pct})

                    p = pct
                    if last_logged_progress is None or p - last_logged_progress >= 20:
                         log.info(f"[{self.host}] Upload progress: {p:.0f}%")
                         last_logged_progress = p

                if upload_status['checking']:
                    log.info(f"[{self.host}] upload complete, device is checking file consistency...")
                    if progress_cb:
                        progress_cb({"ip": self.host, "type": "progress", "progress": 100, "status": "checking"})
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

        log.info(f"[{self.host}] Firmware update based on device status: {fw_versions_log_info}, "
                 f"device is rebooting to extract firmware file, please wait...")
        
        if progress_cb:
            progress_cb({"ip": self.host, "type": "progress", "progress": 100, "status": "Rebooting..."})
        
        reboot_successful = self.reboot(wait_reboot=True, max_wait_secs=85, show_progress_bar=show_progress_bar, progress_cb=progress_cb)

        new_actual_version = initial_dev_version # Default to old if reboot fails or version can't be read
        is_successful_fw_update = False
        status_message = ""
        upload_notes_message = None

        if reboot_successful:
            try:
                # Fetch fresh device info after reboot
                misc_info_after_reboot = self.http_get_status_json(DeployDev.JSON_STATUS_MISC)['misc']
                new_actual_version = misc_info_after_reboot['firm_v']
                log.info(f"[{self.host}] Device rebooted. Current firmware version: {new_actual_version}")

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

    def upload_config(self, cfg_file_name, config_ip, show_progress_bar=True, progress_cb=None):
        cfg = self.get_file_content(cfg_file_name)
        if cfg is None:
            return
        log.info(f"[{self.host}] uploading {cfg_file_name}, please wait...")
        
        if progress_cb:
            progress_cb({"ip": self.host, "type": "progress", "progress": 50, "status": "uploading config"})
            
        self.upload_file(cfg, self.CGI_UPLOAD_TYPE_CONFIG)
        log.info(f"[{self.host}] upload complete, device is rebooting to apply config file, please wait...")
        
        if progress_cb:
            progress_cb({"ip": self.host, "type": "progress", "progress": 100, "status": "Rebooting (cfg)..."})

        self.reboot(wait_reboot=False, show_progress_bar=show_progress_bar, progress_cb=progress_cb)
        if config_ip is not None:
            self.host = config_ip
        self.wait_reboot(max_wait_secs=25, show_progress_bar=show_progress_bar, progress_cb=progress_cb)

        # apply every 'port X state set Y' by http
        for port, state in re.findall(r'port (\d+) state set (\d)', cfg):
            new_sate = self.http_switch_port(int(port), int(state))['outputs'][int(port) - 1]['state']
            log.info(f"[{self.host}] cmd 'port {port} state set {state}' -> '{new_sate}' (sleeping 1s)")
            time.sleep(1)

    def upload_ssl_certificate(self, ssl_cert_file_name, show_progress_bar=True, progress_cb=None):
        cert = self.get_file_content(ssl_cert_file_name)
        if cert is None:
            return
        log.info(f"[{self.host}] uploading {ssl_cert_file_name}, please wait...")
        
        if progress_cb:
            progress_cb({"ip": self.host, "type": "progress", "progress": 50, "status": "uploading cert"})

        self.upload_file(cert, self.CGI_UPLOAD_TYPE_SSL_CERT)
        log.info(f"[{self.host}] upload complete, device is rebooting to apply cert file, please wait...")
        
        if progress_cb:
            progress_cb({"ip": self.host, "type": "progress", "progress": 100, "status": "Rebooting..."})

        self.reboot(wait_reboot=True, max_wait_secs=10, show_progress_bar=show_progress_bar, progress_cb=progress_cb)

    def factory_reset(self, timeout=10.0):
        """
        Trigger a factory reset via HTTP POST to status.json?components=2097152&cmd=42.
        Returns True if successful (HTTP 200), False otherwise.
        """
        url = self.get_http_url('status.json')
        auth = self.get_http_auth()
        params = {
            'components': 2097152,
            'cmd': 42
        }
        
        log.info(f"[{self.host}] Triggering factory reset (POST {url})...")
        try:
            r = requests.post(url, params=params, auth=auth, verify=False, timeout=timeout, headers=self.req_headers)
            if r.status_code == 200:
                return True
            else:
                log.warning(f"[{self.host}] Factory reset POST returned {r.status_code}")
                return False
        except Exception as e:
            log.error(f"[{self.host}] Factory reset exception: {e}")
            raise
