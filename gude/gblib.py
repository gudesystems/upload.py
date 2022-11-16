# from os import get_terminal_size
from shutil import get_terminal_size
from sys import stdout

import socket
from time import sleep
import struct


def print_progress_bar(iteration, total, decimals=1, length=None, fill='█', clear='-', unit='', actual=None,
                       actual_total=None):
    if stdout.isatty():
        if length is None:
            length = get_terminal_size().columns - len(f"100.0%   {total}/{total} " + unit)
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        if iteration == total:
            filled_length = length
        else:
            filled_length = int(length * (iteration % total) // total)
        bar = fill * filled_length + clear * (length - filled_length)
        if not actual:
            actual = iteration
        if not actual_total:
            actual_total = total
        if length < 0:
            print(f'\r{percent.split(".")[0]:>3}%', end='')
        else:
            print(f'\r{percent:>5}% {bar} {actual}/{actual_total} ' + unit, end='')
        if iteration == total:
            print()


class Gblib(object):
    GBL_NETCONF = b'\x01'  # GBL CMD   1 : query / search device
    GBL_FABSETTINGS = b'\x05'  # GBL CMD   5 : delete all user config
    GBL_READEEP = b'\x0d'  # GBL CMD  13 : binary read eprom page
    GBL_WRITEEEP = b'\x0e'  # GBL CMD  14 : binary write eprom page
    GBL_GOFIRM = b'\x0f'  # GBL CMD  15 : start firmware from bootloader
    GBL_GOBLDR = b'\x10'  # GBL CMD  16 : start bootloader from firmware / restart bootloader
    GBL_FWINFO = b'\x11'  # GBL CMD  17 : (CF-legacy) get device info
    GBL_READENT = b'\x15'  # GBL CMD  21 : read eprom entity
    GBL_WRITENT = b'\x16'  # GBL CMD  22 : write eprom entity
    GBL_DELENT = b'\x18'  # GBL CMD  24 : delete eprom entity
    GBL_RDPART = b'\x1e'  # GBL CMD  30 : binary read flash partiton page
    GBL_WRPART = b'\x1f'  # GBL CMD  31 : binary write flash partiton page
    GBL_WRPARTTBL = b'\x20'  # GBL CMD  32 : write ext flash partition table (stage-X)
    GBL_WRSTG0IO = b'\x21'  # GBL CMD  33 : write stage IO defs to spi flash (stage-X)
    GBL_DELMAINT = b'\x22'  # GBL CMD  34 : delete maintenance flag (stage-X)
    GBL_GETCHIPID = b'\x23'  # GBL CMD  3% : get chip id

    GBL_DEL_MAGIC = b'\x87\x86\x85\x85\x86\xAD\x9E\x91\x9B\x90\x92\xBB\x9A\x89\x96\x93'

    DEFAULT_TIMEOUT = 1.0

    def __init__(self):
        self.dstMAC = bytes(0)
        self.bootl_mode = False
        self.ignore_bootl_mode = False
        self.allow_go_boot = False
        self.default_timeout = 1

    @staticmethod
    def gbl_checksum(data):
        chksum = 0
        for byte in data:
            chksum ^= int(byte)
        return chksum

    @staticmethod
    def send_gbl(ip_addr, cmd, timeout=1, wait_answ=True):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        s.settimeout(timeout)
        s.bind(("", 0))
        # print (f"send GBL1... with timeout {timeout}")
        payload = b'\x47\x42\x4c\x04' + cmd
        chksum = Gblib.gbl_checksum(payload)
        data = None
        s.sendto(payload + bytes([chksum]), (ip_addr, 50123))
        if wait_answ:
            try:
                data = s.recv(2048)
                # print("gbl answer: ", len(data), data.hex())
            except socket.timeout:
                s.close()
                return None
        s.close()
        return data

    def set_timeout(self, timeout):
        self.default_timeout = timeout

    def go_firmware(self, ip_addr):
        Gblib.send_gbl(ip_addr, Gblib.GBL_GOFIRM + self.dstMAC, self.default_timeout, False)

    def go_bootldr(self, ip_addr):
        Gblib.send_gbl(ip_addr, Gblib.GBL_GOBLDR + self.dstMAC, self.default_timeout, False)

    def fabsettings(self, ip_addr):
        Gblib.send_gbl(ip_addr, Gblib.GBL_FABSETTINGS + self.dstMAC, self.default_timeout, False)

    def parse_gbl_reply(self, udpdata, expected_cmd, keys=None, unpack=None):
        gbl_reply = {
            'prefix': udpdata[0:4],
            'cmd': udpdata[4:5],
            'mac': udpdata[5:11],
            'data': udpdata[11:-1],
            'crc': udpdata[-1],
            'unpacked': None,
            'udpdata': udpdata
        }

        if Gblib.gbl_checksum(udpdata[:-1]) != gbl_reply['crc']:
            raise ValueError('crc checksum error')

        if expected_cmd != gbl_reply['cmd']:
            raise ValueError('reply from unexpected cmd')

        if gbl_reply['mac'] != self.dstMAC:
            raise ValueError('reply from unexpected mac')

        if keys is not None and unpack is not None:
            gbl_reply['unpacked'] = dict(zip(keys, struct.unpack(unpack, gbl_reply['data'])))

        return gbl_reply

    @staticmethod
    def send_bc(ip_addr):
        payload = b'\x47\x42\x4c\x04\x01\x4c'
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
        s.settimeout(0)
        s.bind((ip_addr, 0))
        s.sendto(payload, ("<broadcast>", 50123))
        return ip_addr, s

    @staticmethod
    def eval_gbl1_reply(data):
        if len(data) == 37:
            return struct.unpack_from(">5s6sH5B4s4s4s3BHBB", data, 0)
        if len(data) == 131:
            return struct.unpack_from(">5s6sH5B4s4s4s3BH6s3s3H64s16sB", data, 0)
        if len(data) == 133:
            return struct.unpack_from(">5s6sH5B4s4s4s3BH6s3s3H64s16sHB", data, 0)

        return None

    @staticmethod
    def get_device_name(dev):
        devs = {0x32: "ExpertPowerControl 8x", 0x40: "EMC Professional NET",
                0x60: "Expert Power Meter", 0x80: "ExpertPowerControl 24x", 0x70: "ExpertTransferSwitch",
                0x90: "ExpertPowerControl 2x6", 0xa0: "ExpertPowerControl 1x", 0xb0: "ExpertPowerControl 1x",
                0xe0: "Expert Net control 2i2o", 0xeeee: "unknown device"}
        if len(dev) < 18:  # older
            return devs[dev[2]] if dev[2] in devs else "unknown device"
        else:
            return dev[20].decode().rstrip('\0')  # strip zeros at end!

    @staticmethod
    def get_dev_info(dev):
        if len(dev) < 18:  # older
            data2 = Gblib.send_gbl(socket.inet_ntoa(dev[8]), Gblib.GBL_FWINFO + dev[1] + b'\x01')
            hostname = bytes(data2[13:-1]).decode().rstrip('\0')  # strip zeros at end!
        else:
            hostname = dev[21].decode().rstrip('\0')  # strip zeros at end!

        return {
            'devname': Gblib.get_device_name(dev),
            'mac': ':'.join(f'{c:02x}' for c in dev[1]),
            'ip': socket.inet_ntoa(dev[8]),
            'hostname': hostname,
            'bootloader': {
                'active': True if dev[7] else False,
                'version': [dev[3], dev[4]]
            },
            'firmware': {
                'active': True if not dev[7] else False,
                'version': [dev[5], dev[6]]
            }
        }

    @staticmethod
    def get_dev_info_str(dev):
        info = Gblib.get_dev_info(dev)
        bl_str = " (*ACTIVE*)" if info['bootloader']['active'] else ""
        fw_ver = '.'.join(str(x) for x in info['firmware']['version'])
        bldr_ver = '.'.join(str(x) for x in info['bootloader']['version'])
        return (f"{info['mac']} - {info['devname']:32} - v{fw_ver} ({bldr_ver}{bl_str}), hostname {info['hostname']} - {info['ip']}")

    def check_mac(self, ip_addr, clear_cache=True):
        if clear_cache:
            self.dstMAC = bytes(0)

        if len(self.dstMAC) == 0:
            data = Gblib.send_gbl(ip_addr, Gblib.GBL_NETCONF, self.default_timeout)
            if data is not None:
                self.dstMAC = (struct.unpack_from("6s", data, 5))[0]
                self.bootl_mode = (struct.unpack_from("B", data, 17))[0]
                self.allow_go_boot = (struct.unpack_from("B", data, 32))[0] & 0x80
                self.dev_info = Gblib.eval_gbl1_reply(data)
                return True
            else:
                return False
        else:
            return True

    @staticmethod
    def recv_bc(myip='0.0.0.0', timeout=1):
        sock_lst = []
        device_lst = []
        sock_lst.append(Gblib.send_bc(myip))
        sleep(timeout)
        for ip_addr, sock in sock_lst:
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    if len(data) > 6:
                        device_lst.append(Gblib.eval_gbl1_reply(data))
                except BlockingIOError:
                    break
            sock.close()
        return device_lst

    def wait_for_netconf(self, ip_addr, secs=8):
        for i in range(secs):
            data = self.send_gbl(ip_addr, Gblib.GBL_NETCONF, 1)
            if data is not None:
                return True
            sleep(1)
        return False

