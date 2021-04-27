import sys
import json
import time
import requests
import os


class HttpDevice:
    JSON_STATUS_OUTPUTS = 0x00000001  # Output status
    JSON_STATUS_INPUTS = 0x00000002  # Internal inputs status
    JSON_STATUS_DNS_CACHE = 0x00000004  # Content of the actual DNS cache
    JSON_STATUS_ETHERNET = 0x00000008  # Ethernet status / counter
    JSON_STATUS_MISC = 0x00000010  # Miscellaneous status info (Firmware version, Bootloader version, etc.)
    JSON_STATUS_EVENTS = 0x00000080  # Message-events counter
    JSON_STATUS_PORT_SUMMARY = 0x00000100  # Summarized status information of the outputs and inputs
    JSON_STATUS_HARDWARE = 0x00000200  # Summarized status information of the general hardware
    JSON_STATUS_GSM_STATUS = 0x00000400  # Status information for GSM products
    JSON_STATUS_GSM_LOG = 0x00000800  # Call-log for GSM products
    JSON_STATUS_GSM_COUNTERS = 0x00001000  # Summarized status information for GSM products
    JSON_STATUS_SIM = 0x00002000  # Sim card status for GSM products
    JSON_STATUS_SENSOR_VALUES = 0x00004000  # Actual values of available sensors (temperature, etc.)
    JSON_STATUS_SENSOR_DESCR = 0x00010000  # Field description of the actual available sensors (temperature, etc.)
    JSON_STATUS_CLOCK = 0x00008000  # status clock
    JSON_STATUS_SENSOR_EXT = 0x00800000 # enable grouped sensors in SENSOR_VALUES / SENSOR_DESCR

    # config.json components flags
    JSON_CONFIG_MAIL = 0x00000002  # Mail client/server configuration
    JSON_CONFIG_HTTP = 0x00000004  # HTTP server configuration
    JSON_CONFIG_HW = 0x00000008  # Hardware config, like hw.fan, etc...
    JSON_CONFIG_MESSAGES = 0x00000020  # Configuration of which sensors/measurement modules send messages
    JSON_CONFIG_SYSLOG = 0x00000040  # Syslog configuration
    JSON_CONFIG_PORT_CFG = 0x00000080  # Outputs configuration (Power ports)
    JSON_CONFIG_IP = 0x00000100  # IP configuration (IP address, network mask, etc.)
    JSON_CONFIG_IPCAL = 0x00000200  # IP-ACL configuration (filter list)
    JSON_CONFIG_BEEPER = 0x00000400  # Possibly integrated beeper (alarm transmitter) configuration
    JSON_CONFIG_SNMP = 0x00000800  # SNMP configuration
    JSON_CONFIG_INPUT_CFG = 0x00001000  # Input configuration
    JSON_CONFIG_GSM_CODES = 0x00002000  # GSM code configuration (for products with GSM)
    JSON_CONFIG_GSM_NUMBERS = 0x00004000  # Configuration of some special GSM phone numbers (for products with GSM)
    JSON_CONFIG_GSM_PHONEBOOK = 0x00008000  # Configuration of a GSM phone number list (for products with GSM)
    JSON_CONFIG_CLOCK = 0x00040000  # Condig Clock (timezone, ntp, manual, etc..)
    JSON_CONFIG_GSM_FLAGS = 0x00010000  # Individual GSM features configuration (for products with GSM)
    JSON_CONFIG_GSM_PROVIDER = 0x00020000  # Configuration of GSM provider specific numbers (for products with GSM)
    JSON_CONFIG_ETS = 0x00100000  # Config ETS
    JSON_CONFIG_CONSOLE = 0x00200000  # mixed Telnet / Serial Console Config Json
    JSON_CONFIG_MODBUS = 0x00400000  # config Modbus
    JSON_CONFIG_RADIUS = 0x00800000  # config Raduis
    JSON_CONFIG_FRONTPANEL = 0x01000000  # config front panel
    JSON_CONFIG_SENSORS = 0x02000000  # config sensors
    JSON_CONFIG_TIMER = 0x04000000  # config fabdefaults

    EVENT_MSG_PIPE_SYSLOG = 0x01
    EVENT_MSG_PIPE_SNMP = 0x02
    EVENT_MSG_PIPE_EMAIL = 0x04
    EVENT_MSG_PIPE_SMS = 0x08
    EVENT_MSG_PIPE_GSMEMAIL = 0x10
    EVENT_MSG_PIPE_DISPLAY = 0x20
    EVENT_MSG_PIPE_BEEPER = 0x40
    EVENT_MSG_PIPE_CONSOLE = 0x80
    EVENT_MSG_PIPES_ETH = EVENT_MSG_PIPE_SYSLOG + EVENT_MSG_PIPE_SNMP + EVENT_MSG_PIPE_EMAIL + EVENT_MSG_PIPE_CONSOLE

    EVENT_PORT_ON = 1
    EVENT_PORT_OFF = 2
    EVENT_DIG_INP_HI = 3
    EVENT_DIG_INP_LO = 4
    EVENT_INCOMINGCALL = 5
    EVENT_GSMNET = 6
    EVENT_WDOG_ERROR = 7
    EVENT_WDOG_OK = 8
    EVENT_WDOG_BOOTING = 9
    EVENT_WDOG_REBOOTING = 10
    EVENT_POWERUP_START = 11
    EVENT_POWERUP_END = 12
    EVENT_SYSLOG_ON = 13
    EVENT_SYSLOG_OFF = 14
    EVENT_DEV_POWERUP = 15
    EVENT_POE_ON = 16
    EVENT_POE_OFF = 17
    EVENT_TESTMAIL = 18
    EVENT_SNTP_ON = 19
    EVENT_SNTP_OFF = 20
    EVENT_ATS_PRIMARY_ON = 21
    EVENT_ATS_PRIMARY_OFF = 22
    EVENT_ATS_SECONDARY_ON = 23
    EVENT_ATS_SECONDARY_OFF = 24
    EVENT_ATS_SWITCH_TO_PRIMARY = 25
    EVENT_ATS_SWITCH_TO_SECONDARY = 26
    EVENT_ATS_MANUAL_SWITCH = 27
    EVENT_FUSE_BLOWN = 28
    EVENT_POWER_LOSS = 29
    EVENT_POWER_RETURN = 30
    EVENT_WDOG_MS_ON = 31
    EVENT_WDOG_MS_OFF = 32
    EVENT_COMP_ABOVE = 33
    EVENT_COMP_BELOW = 34
    EVENT_COMP_INBOUNDS = 35
    EVENT_STOP_INPUT_ON = 36
    EVENT_STOP_INPUT_OFF = 37
    EVENT_FUSE_RESTORED = 38
    EVENT_EFUSE_TRIGGERED = 39
    EVENT_EFUSE_RESET = 40
    EVENT_PUBLISH_VALUE = 41

    EVENTS_PER_PORT = [
        EVENT_PORT_ON, EVENT_PORT_OFF,
        EVENT_WDOG_ERROR, EVENT_WDOG_OK, EVENT_WDOG_BOOTING, EVENT_WDOG_REBOOTING,
        EVENT_EFUSE_TRIGGERED, EVENT_EFUSE_RESET
    ]
    EVENTS_PER_INPUT = [
        EVENT_DIG_INP_HI, EVENT_DIG_INP_HI
    ]

    RADIUS_AUTH_RESULT_DENIED = 0
    RADIUS_AUTH_RESULT_USER = 1
    RADIUS_AUTH_RESULT_ADMIN = 2

    JSON_ALL = 0x0FFFFFFF

    CGI_CMD_SWITCH_POWERPORTS = 1
    CGI_CMD_CANCEL_BATCHMODES = 2

    CGI_CMD_CONFIG_POWERPORTS = 3
    CGI_CMD_CONFIG_IP = 4
    CGI_CMD_CONFIG_IPACL = 6
    CGI_CMD_CONFIG_SNMP = 8
    CGI_CMD_VIRTUAL_SENSOR = 10
    CGI_CMD_CONFIG_INPUTPORTS = 13
    CGI_CMD_CONFIG_MAIL = 15
    CGI_CMD_CONFIG_SYSLOG = 17
    CGI_CMD_CONFIG_HTTP = 18
    CGI_CMD_CONFIG_CLOCK = 19
    CGI_CMD_SWITCH_ETS = 28
    CGI_CMD_CONFIG_ETS = 29
    CGI_CMD_CONFIG_FAN = 21
    CGI_CMD_CONFIG_GSM_CFG = 22
    CGI_CMD_CONFIG_GSM_CODES = 23
    CGI_CMD_CONFIG_GSM_PROVIDER = 24
    CGI_CMD_CONFIG_GSM_TELEBOOK = 25
    CGI_CMD_CONFIG_SENSORS = 30
    CGI_CMD_TEST_EVENT_MSG = 31
    CGI_CMD_TESTMAIL = 35
    CGI_CMD_RESET = 39
    CGI_CMD_RESET_TO_STAGE1 = 40
    CGI_CMD_FLUSHDNS = 41
    CGI_CMD_RESET_TO_FAB = 42
    CGI_CMD_CONFIG_TELNET = 43
    CGI_CMD_CONFIG_SERCON = 44
    CGI_CMD_CONFIG_MODBUS = 45
    CGI_CMD_CONFIG_RADIUS = 46
    CGI_CMD_CONFIG_FRONTPANEL = 48
    CGI_CMD_RESETSTAT_AGGREGATE = 49
    CGI_CMD_SET_CLOCK = 50
    CGI_CMD_CONFIG_TIMER = 51
    CGI_CMD_CONFIG_TIMER_DEL = 52

    CGI_UPLOAD_TYPE_FIRMWARE = 0
    CGI_UPLOAD_TYPE_SSL_CERT = 1
    CGI_UPLOAD_TYPE_CONFIG = 2
    CGI_UPLOAD_TYPE_SENSOR_ENTITY = 3
    CGI_UPLOAD_TYPE_EPROM_BIN = 4
    CGI_UPLOAD_TYPE_SSHPUBKEY = 5

    SENSOR_MSG_TYPE_MINMAX = 1
    SENSOR_MSG_TYPE_INPUT = 2
    SENSOR_MSG_TYPE_PIPES = 3

    sensorMsgOpt = {
        SENSOR_MSG_TYPE_MINMAX: [],
        SENSOR_MSG_TYPE_INPUT: [],
        SENSOR_MSG_TYPE_PIPES: []
    }

    DEFAULT_DISPLAY_SENSOR = 1  # genau einen sensor Feld ins Display
    DEFAULT_DISPLAY_AMPERE = 2  # spezial fall Bank A auf display 1, Bank B auf display 2

    GSM_FLAG_CODE_ACTIVE = 0x00000001
    GSM_FLAG_TELBOOK_ACTIVE = 0x00000002
    GSM_FLAG_GSMSTATUS_ACTIVE = 0x00000004
    GSM_FLAG_EMAIL_ACTIVE = 0x00000008
    GSM_FLAG_TEMP_ACTIVE = 0x00000010
    GSM_FLAG_ANSWER_ACTIVE = 0x00000020
    GSM_FLAG_ERROR_ACTIVE = 0x00000040
    GSM_FLAG_PORTNAME_ACTIVE = 0x00000080
    GSM_FLAG_FREECALL_ACTIVE = 0x00000100
    GSM_FLAG_MASTERGSM_ACTIVE = 0x00000200
    GSM_FLAG_AUTOSYNC_ACTIVE = 0x00000400
    GSM_FLAG_GSM_ACTIVE = 0x00000800
    GSM_FLAG_TONE_ACTIVE = 0x00001000
    GSM_FLAG_VOICE_ACTIVE = 0x00002000
    GSM_FLAG_COV_MSG_ACTIVE = 0x00004000

    gsmFlags = {
        'code': GSM_FLAG_CODE_ACTIVE,
        'telbook': GSM_FLAG_TELBOOK_ACTIVE,
        'gsmstatus': GSM_FLAG_GSMSTATUS_ACTIVE,
        'email': GSM_FLAG_EMAIL_ACTIVE,
        'temp': GSM_FLAG_TEMP_ACTIVE,
        'answer': GSM_FLAG_ANSWER_ACTIVE,
        'error': GSM_FLAG_ERROR_ACTIVE,
        'portname': GSM_FLAG_PORTNAME_ACTIVE,
        'coverage': GSM_FLAG_COV_MSG_ACTIVE,
        'freecall': GSM_FLAG_FREECALL_ACTIVE,
        'master': GSM_FLAG_MASTERGSM_ACTIVE,
        'autosync': GSM_FLAG_AUTOSYNC_ACTIVE,
        'gsm': GSM_FLAG_GSM_ACTIVE,
        'tone': GSM_FLAG_TONE_ACTIVE,
        'voice': GSM_FLAG_VOICE_ACTIVE
    }

    defaultDisplayOpt = {
        DEFAULT_DISPLAY_SENSOR: [],
        DEFAULT_DISPLAY_AMPERE: None
    }
    CGI_CMD_JSON_MAP = {
        CGI_CMD_SWITCH_POWERPORTS: {
            'resource': {
                'file': 'status.json',
                'components': JSON_STATUS_OUTPUTS
            },
            'params': {
                'p': 0,
                's': 0
            }
        },
        CGI_CMD_CANCEL_BATCHMODES: {
            'resource': {
                'file': 'status.json',
                'components': JSON_STATUS_OUTPUTS
            },
            'params': {
                'p': 0
            }
        },
        CGI_CMD_CONFIG_POWERPORTS: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_PORT_CFG,
                'jsonObj': 'port_cfg'
            },
            'params': {
                'p': 1,
                'name': 'Power Port',
                'powup': 0,
                'powrem': 0,
                'stickylogical': 0,
                'idle': 0,
                'on_again': 0,
                'twin': 0,
                'reset': 10,
                'we': 0,
                'wip': '',
                'wt': 0,
                'wrbx': 10,
                'wport': 80,
                'wint': 10,
                'wret': 6
                # 'gsmcode': 'P',
                # 'ipl0': 0,
                # 'ipl1': 0,
            }
        },
        CGI_CMD_CONFIG_INPUTPORTS: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_INPUT_CFG,
                'jsonObj': 'input_cfg'
            },
            'params': {
                "p": 1,
                "name": "Input",
                "hitext": "on / closed",
                "lowtext": "off / open",
                "inverted": 1,
                "msgt": 0,
                "msg_pipes": 0,
                "sms_numbers": 0,
                "stinhi_p": 0,
                "stinhi_s": 0,
                "stinlow_p": 0,
                "stinlow_s": 0,
                "beeper_modes": 1,
                "pubmode": 0,
                "pubval": 0
            }
        },
        CGI_CMD_CONFIG_CLOCK: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_CLOCK,
                'jsonObj': 'clock'
            },
            'params': {
                'ntp': 0,
                'ntpsrv1': '',
                'ntpsrv2': '',
                'tz_offset': 60,
                'dst': 1
            }
        },
        CGI_CMD_CONFIG_SYSLOG: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_SYSLOG,
                'jsonObj': 'syslog'
            },
            'params': {
                'syslog': 0,
                'slgsrv': ''
            }
        },
        CGI_CMD_CONFIG_IPACL: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_IPCAL,
                'jsonObj': 'ipacl'
            },
            'params': {
                'ping': 1,
                'acl': 0,
                'ipsec0': '',
                'ipsec1': '',
                'ipsec2': '',
                'ipsec3': '',
                'ipsec4': '',
                'ipsec5': '',
                'ipsec6': '',
                'ipsec7': ''
            }
        },
        CGI_CMD_SET_CLOCK: {
            'resource': {
                'file': 'status.json',
                'components': JSON_STATUS_CLOCK
            },
            'params': {
                'time': 0
            }
        },
        CGI_CMD_CONFIG_TIMER: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_TIMER,
                'jsonObj': 'timer'
            },
            'params': {
                'enabled': 0,
                'syslog': 1,
                'ruleid': 0,
                'trenabled': 0,
                'name': 'rule-0',
                'hour': 0,
                'minute[0]': 0,
                'minute[1]': 0,
                'day': 4294967294,
                'month': 8190,
                'dow': 127,
                'mind': 1,
                'minm': 1,
                'miny': 2000,
                'maxd': 1,
                'maxm': 1,
                'maxy': 2000,
                'jitter': 0,
                'chance': 100,
                'batchdelay': 5,
                'actiontest': 0,
                'actionid': 1,
                'portlist[0][0]': 0,
                'statelist[0][0]': 0,
                'portlist[0][1]': 0,
                'statelist[0][1]': 0,
                'portlist[1][0]': 0,
                'statelist[1][0]': 0,
                'portlist[1][1]': 0,
                'statelist[1][1]': 0
            }
        },
        CGI_CMD_CONFIG_HTTP: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_HTTP,
                'jsonObj': 'http'
            },
            'params': {
                'apwd': 'admin',
                'upwd': 'user',
                'pwd': 0,
                'basicauth': 1,
                'ploc': 1,
                'prad': 0,
                'port': 80,
                'ports': 443,
                'srvopts': 3,
                'sprp': 0,
                'refr': 1
            }
        },
        CGI_CMD_CONFIG_IP: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_IP,
                'jsonObj': ['ipv4', 'ipv6']
            },
            'params': {
                'host': 'epc',
                'ip': '192.168.0.2',
                'nm': '255.255.255.0',
                'gw': '192.168.0.2',
                'dns': '192.168.0.1',
                'dhcp': 1,
                'ipv6': 0,
                'dhcp6': 0,
                'slaac': 0,
                'manualv6': 0,
                'ip6[0]': '',
                'ip6[1]': '',
                'ip6[2]': '',
                'ip6[3]': '',
                'dns6[0]': '',
                'dns6[1]': '',
                'gw6[0]': ''
            }
        },
        CGI_CMD_CONFIG_TELNET: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_CONSOLE,
                'jsonObj': 'console'  # console.telnet
            },
            'params': {
                'tact': 0,
                'traw': 0,
                'techo': 0,
                'tlog': 0,
                'tlogloc': 1,
                'tlograd': 0,
                'tneg': 0,
                'tdelay': 0,
                'tname': 'telnet',
                'tport': 23
                # 'tpass': ''
            }
        },
        CGI_CMD_CONFIG_SERCON: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_CONSOLE,
                'jsonObj': 'console'  # console.serial
            },
            'params': {
                'tact': 0,
                'traw': 0,
                'techo': 0,
                'tlog': 0,
                'tlogloc': 1,
                'tlograd': 0,
                'tneg': 0,
                'tdelay': 0,
                'tname': 'telnet',
                'tport': 23
            }
        },
        CGI_CMD_CONFIG_SNMP: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_SNMP,
                'jsonObj': 'snmp'
            },
            'params': {
                'get': 0,
                'set': 0,
                'port': 161,
                'v2enab': 0,
                'cpub': 'public',
                'cpriv': 'private',
                'v3enab': 0,
                'uname': 'standard',
                'authalg': 0,
                'privalg': 0,
                'trapv': 0,
                'tr0': '',
                'tr1': '',
                'tr2': '',
                'tr3': '',
                'tr4': '',
                'tr5': '',
                'tr6': '',
                'tr7': ''
            },
        },
        CGI_CMD_CONFIG_RADIUS: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_RADIUS,
                'jsonObj': 'radius'
            },
            'params': {
                'dflt_session_timeout': 1800,
                'chap': 0,
                'msgauth': 1,
                'enabled0': 0,
                'server0': '',
                # 'secret0': '',
                'retries0': 3,
                'timeout0': 5,
                'enabled1': 0,
                'server1': '',
                'retries1': 3,
                'timeout1': 5
                # 'secret1': ''
            }
        },
        CGI_CMD_CONFIG_MODBUS: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_MODBUS,
                'jsonObj': 'modbus'
            },
            'params': {
                "enabled": 0,
                "port": 502
            }
        },
        CGI_CMD_CONFIG_MAIL: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_MAIL,
                'jsonObj': 'mail'
            },
            'params': {
                "mail": 0,
                "user": "",
                "pass": "",
                "auth": 0,
                "connsec": 0,
                "mailsrv": "",
                "sender": "",
                "email": ""
            }
        },
        CGI_CMD_CONFIG_SENSORS: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_SENSORS + JSON_CONFIG_BEEPER,
                'jsonObj': 'sensors'
            },
            'params': {
                'sbeeper': 1,
                'beeper': 1,
                'period': 1
            }
        },
        CGI_CMD_CONFIG_FRONTPANEL: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_FRONTPANEL,
                'jsonObj': 'front_panel'
            },
            'params': {
                "gbright": 0,
                "btnlock": 0,
                "ddt": 2,
                "ddst": 0,
                "ddsi": 0,
                "ddgi": 0,
                "ddgm": 0,
                "ddfi": 0
            }
        },
        CGI_CMD_SWITCH_ETS: {
            'resource': {
                'file': 'status.json',
                'components': JSON_STATUS_HARDWARE,
                'jsonObj': 'hardware'
            },
            'params': {
                "switch": 1
            }
        },
        CGI_CMD_CONFIG_ETS: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_ETS + JSON_CONFIG_BEEPER,
                'jsonObj': ['ets', 'beeper']
            },
            'params': {
                "preferred": 0,
                "sensitivity": 0,
                "fastonsync": 0,
                "beeperen": 0
            }
        },
        CGI_CMD_CONFIG_GSM_CFG: {
            'resource': {
                'file': 'config.json',
                'components':
                    JSON_CONFIG_GSM_CODES + JSON_CONFIG_GSM_FLAGS + JSON_CONFIG_GSM_NUMBERS + JSON_CONFIG_GSM_PROVIDER,
                'jsonObj': ['gsm_codes', 'gsm_flags', 'gsm_numbers', 'gsm_provider']
            },
            'params': {
                'code': 1,
                'telbook': 0,
                'gsmstatus': 0,
                'email': 0,
                # 'temp': 0,
                'answer': 1,
                'error': 1,
                'coverage': 0,
                'portname': 0,
                'freecall': 0,
                'master': 0,
                'autosync': 0,
                'gsm': 0,
                'tone': 0,
                'voice': 1
            }
        },
        CGI_CMD_CONFIG_GSM_CODES: {
            'resource': {
                'file': 'config.json',
                'components':
                    JSON_CONFIG_GSM_CODES + JSON_CONFIG_GSM_FLAGS + JSON_CONFIG_GSM_NUMBERS + JSON_CONFIG_GSM_PROVIDER,
                'jsonObj': ['gsm_codes', 'gsm_flags', 'gsm_numbers', 'gsm_provider']
            },
            'params': {
                'simpin': '',
                'mytel': '',
                'mastern': '',
                'email': '',
                'mastercode': 'M0000'
            }
        },
        CGI_CMD_CONFIG_GSM_TELEBOOK: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_GSM_PHONEBOOK,
                'jsonObj': 'gsm_phonebook'
            },
            'params': {
                'index': '0',
                'name': '',
                'number': '',
                'port': '1',
                'action': '0',
            }
        },
        CGI_CMD_CONFIG_FAN: {
            'resource': {
                'file': 'config.json',
                'components': JSON_CONFIG_HW,
                'jsonObj': 'hw'
            },
            'params': {
                'subcomponents': 1,
                'mode': 0
            }
        }
    }

    httpOpts = {
        "ssl": False,
        "port": 80,
        "basicauth": False,
        "sessionauth": False,
        "username": "admin",
        "password": "admin"
    }

    LOG_NONE = 0
    LOG_INFO = 1
    LOG_VERBOSE = 2
    LOG_DEBUG = 3
    LOG_INSANE = 10

    logLevel = LOG_INFO

    lastGetReq = {
        "time": None,
        "url": None,
        "code": None
    }

    httpTimeout = 10.0
    httpRetries = 4
    httpAutoAddAjaxTimestamp = False

    def log(self, text, level=LOG_INFO, end=os.linesep):
        if self.logLevel >= level:
            if end is None:
                print(text, end='')
                sys.stdout.flush()
            else:
                print(text)

    def setLogLevel(self, level):
        self.logLevel = level

    def getCgiCmdParamDefaults(self, cmd, extraParams=None):
        if cmd in self.CGI_CMD_JSON_MAP:
            params = self.CGI_CMD_JSON_MAP[cmd]
            params.update({"cmd": cmd})
            if extraParams is not None:
                params.update(extraParams)
            return params
        else:
            raise ValueError("missing cgi cmd params for cmd {0}".format(cmd))

    @staticmethod
    def jsonDump(jsonData):
        return json.dumps(jsonData, sort_keys=True, indent=4, separators=(',', ': '))

    # setHttpPort(443, ssl=True)
    # setHttpPort(80)
    def setHttpPort(self, port=80, ssl=False):
        self.httpOpts["ssl"] = ssl
        if port is None:
            if ssl:
                port = 443
            else:
                port = 80
        self.httpOpts["port"] = port

    # setBasicAuth(True, "admin", "admin")
    # setBasicAuth(False, "", "")
    def setBasicAuth(self, basicauth=False, username='', password=''):
        self.httpOpts["basicauth"] = basicauth
        self.httpOpts["username"] = username
        self.httpOpts["password"] = password

    def setLastReq(self, url, code, timeVal, size, method="GET"):
        self.lastGetReq["time"] = timeVal
        self.lastGetReq["url"] = url
        self.lastGetReq["code"] = code
        self.log("HTTP {0} {1} {2} {3}".format(method, code, url, size), self.LOG_VERBOSE)

    def getHttpUrl(self, file):
        if self.httpOpts["ssl"]:
            protocol = "https"
            port = (':' + str(self.httpOpts["port"])) if (self.httpOpts["port"] != 443) else ''
        else:
            protocol = "http"
            port = (':' + str(self.httpOpts["port"])) if (self.httpOpts["port"] != 80) else ''

        return '{0}://{1}{2}/{3}'.format(protocol, self.host, port, file)

    def getHttpAuth(self):
        auth = None
        if self.httpOpts["basicauth"]:
            auth = requests.auth.HTTPBasicAuth(self.httpOpts["username"], self.httpOpts["password"])
        return auth

    def setHttpTimeout(self, timeout):
        self.httpTimeout = timeout

    def setHttpRetries(self, retries):
        self.httpRetries = retries

    def httpGet(self, filename, cgiGetParams=None):
        url = self.getHttpUrl(filename)
        auth = self.getHttpAuth()

        if cgiGetParams is None:
            cgiGetParams = {}

        self.log(cgiGetParams, self.LOG_DEBUG)

        start = stop = None
        retries = 0
        r = None
        while retries < (1+self.httpRetries) and stop is None:
            try:
                start = time.time()
                if self.httpAutoAddAjaxTimestamp:
                    cgiGetParams["_"] = int(time.time())
                r = requests.get(url, params=cgiGetParams, verify=False, timeout=self.httpTimeout, auth=auth,
                                 headers={'Connection': 'close'})
                stop = time.time()
            except requests.exceptions.Timeout:
                self.log(f"Timeout {url} {cgiGetParams} {retries}")
                retries += 1

        if r is not None:
            if r.status_code == 200:
                self.setLastReq(r.url, r.status_code, (stop - start), len(r.text))
                return r.text
            else:
                self.setLastReq(r.url, r.status_code, (stop - start), None)
                raise ValueError("http request error {0}".format(r.status_code))
        raise ValueError("http request failed")

    def httpPing(self, timeout=1.0):
        url = self.getHttpUrl('index.html')
        auth = self.getHttpAuth()
        try:
            r = requests.get(url, params={}, verify=False, timeout=timeout, auth=auth, headers={'Connection': 'close'})
            return r.status_code == 200
        except (ValueError, Exception):
            return False

    def uploadFile(self, filedata, uploadType, cgiGetParams=None, retRessource='fwupdate.txt', timeout=10.0):
        url = self.getHttpUrl(retRessource)
        auth = self.getHttpAuth()

        if cgiGetParams is None:
            cgiGetParams = {}

        cgiGetParams["type"] = uploadType
        files = {'fwupload': filedata}

        start = time.time()
        r = requests.post(url, params=cgiGetParams, files=files, verify=False, timeout=timeout, auth=auth)
        stop = time.time()

        if r.status_code == 200:
            self.setLastReq(r.url, r.status_code, (stop - start), len(r.text), method="POST")
            return r.text
        else:
            self.setLastReq(r.url, r.status_code, (stop - start), None, method="POST")
            raise ValueError("http request error {0}".format(r.status_code))

    def uploadConfig(self, filedata):
        self.log(filedata, self.LOG_DEBUG)
        return self.uploadFile(filedata, self.CGI_UPLOAD_TYPE_CONFIG)

    def httpGetJson(self, file, cgiGetParams=None):
        if cgiGetParams is None:
            cgiGetParams = {}

        jsonString = self.httpGet(file, cgiGetParams)
        if jsonString:
            return json.loads(jsonString)
        else:
            return False

    def httpGetStatusJson(self, components, cgiGetParams=None):
        if cgiGetParams is None:
            cgiGetParams = {}
        cgiGetParams["components"] = components
        return self.httpGetJson("status.json", cgiGetParams)

    def httpGetConfigJson(self, components, cgiGetParams=None):
        if cgiGetParams is None:
            cgiGetParams = {}
        cgiGetParams["components"] = components
        return self.httpGetJson("config.json", cgiGetParams)

    def httpCgiJsonCmd(self, cmd, params=None, mergeDefaults=True):
        if params is None:
            params = {}

        if cmd not in self.CGI_CMD_JSON_MAP:
            jsonMap = {'resource': {'file': 'status.json', 'components': 0}, 'params': {}}
        else:
            jsonMap = self.CGI_CMD_JSON_MAP[cmd]

        myParams = {}
        if mergeDefaults:
            myParams.update(jsonMap['params'])

        myParams["cmd"] = cmd
        myParams["components"] = jsonMap['resource']['components']
        myParams.update(params)

        return self.httpGetJson(jsonMap['resource']['file'], myParams)

    def getAllJson(self):
        self.allConfigJson = self.httpGetConfigJson(self.JSON_ALL)
        self.allStatusJson = self.httpGetStatusJson(self.JSON_ALL)

    def getEpromJson(self, removeVolatiles=True):
        self.entities = self.httpGetJson('eprom.json')

        if not self.entities:
            return False

        if removeVolatiles:
            newJson = []
            for entity in self.entities:
                #
                # completely remove entities
                #   14: CONFIG_ID_BOOT_STATS
                #   30: CONFIG_ID_GSM_COUNTERS
                #   32: CONFIG_ID_GSM_LOGENTRY
                #   41: CONFIG_ID_ENERGY_COUNT (obsolete)
                #   54: CONFIG_ID_EXT_ENERGY_COUNT
                #
                if entity["id"] not in [14, 30, 32, 41, 54]:
                    newJson.append(entity)

                #
                # whiteout entities parts
                #
                if entity["id"] == 36:
                    # watchdog status
                    entity["data"] = entity["data"][:2] + "00" + entity["data"][5:]

                if entity["id"] == 38:
                    # whiteout current port state (remember last state maybe is fab default)
                    optByte = int(bytearray.fromhex(entity["data"][:2])[0]) & 0xFE
                    entity["data"] = f'{optByte:0>2X}' + entity["data"][2:]

            self.entities = newJson
        return self.entities

    def flushConfigBuffer(self):
        self.allConfigJson = None
        self.allStatusJson = None
        self.entities = None

    def waitReboot(self, maxWaitSecs=20.0):
        for i in range(1, 10):
            self.log(".", self.LOG_INFO, end='')
            time.sleep(1)

        retries = maxWaitSecs
        while retries:
            if self.httpPing(1.0):
                self.log(" {0}:{1} up".format(self.host, self.httpOpts["port"]))
                time.sleep(1)
                return True
            else:
                retries -= 1
                self.log(".", self.LOG_INFO, end='')

        self.log("ERROR: no reply, giving up", self.LOG_INFO, end='')
        return False

    def rebootCmd(self, cmd, waitreboot=False, maxWaitSecs=20.0):
        self.httpCgiJsonCmd(cmd)
        if waitreboot:
            return self.waitReboot(maxWaitSecs)
        else:
            return True

    #
    # reboot device to Fab Defaults
    #
    def rebootFab(self, waitreboot=True):
        self.log("Reboot to FabSettings...")
        self.flushConfigBuffer()
        ret = self.rebootCmd(self.CGI_CMD_RESET_TO_FAB, waitreboot)
        return ret

    #
    # reboot device
    #
    def reboot(self, waitreboot=True, maxWaitSecs=20):
        self.log("Rebooting...")
        self.flushConfigBuffer()
        ret = self.rebootCmd(self.CGI_CMD_RESET, waitreboot, maxWaitSecs)
        return ret

    #
    # switch port
    #
    def httpSwitchPort(self, port, status):
        jsonData = self.httpCgiJsonCmd(self.CGI_CMD_SWITCH_POWERPORTS, {"p": port, "s": status})
        if jsonData['outputs'][port-1]['state'] != status:
            raise ValueError("illegal switch state")
        return jsonData

    def setBankSource(self, bankId, source):
        jsonData = self.httpCgiJsonCmd(self.CGI_CMD_CONFIG_POWERPORTS,
                                       {f'banksource[{bankId}]': '.'.join((str(x) for x in source))})
        return jsonData

    def httpSwitchEtsPowerSource(self, source):
        jsonData = self.httpCgiJsonCmd(self.CGI_CMD_SWITCH_ETS, {"switch": source})
        return jsonData['hardware']['power'][0]['outputs'][0]['source']['connected']

    #
    # cancel Batchmode
    #
    def httpCancelBatchmode(self, port):
        return self.httpCgiJsonCmd(self.CGI_CMD_CANCEL_BATCHMODES, {"p": port})

    #
    # config Clock (helper):
    #
    def httpConfigClock(self, ntpEnabled, ntpsrv1, ntpsrv2, tz_offset, dstEnabled):
        cgi = {
           "ntp": ntpEnabled,
           "ntpsrv1": ntpsrv1,
           "ntpsrv2": ntpsrv2,
           "tz_offset": tz_offset,
           "dst": dstEnabled
        }
        return self.httpCgiJsonCmd(self.CGI_CMD_CONFIG_CLOCK, cgi)

    def triggerEventMessage(self, typ, idx=0, context=0, pipe=EVENT_MSG_PIPES_ETH, extra=None):
        cgi = {'id': typ, 'idx': idx, 'context': context, 'pipe': pipe}
        if extra is not None:
            cgi['extra'] = extra
        self.log(f"Trigger test event {typ}.{idx} context({context}) pipe({pipe}) extra({extra})", self.LOG_INFO)
        return self.httpCgiJsonCmd(HttpDevice.CGI_CMD_TEST_EVENT_MSG, cgi)

    def exportConfig(self):
        return self.httpGet("config.txt")

    def getRamUsage(self):
        debugJson = self.httpGetJson('debug.json')
        return debugJson["internal"]["free_mem"], debugJson["external"]["free_mem"]

    def getMemlog(self, facility=None, maxlevel=None, minid=None):
        cgi = {}
        if facility is not None:
            cgi['facility'] = facility
        if maxlevel is not None:
            cgi['maxlevel'] = maxlevel
        if minid is not None:
            cgi['minid'] = minid

        return self.httpGetJson('memlog.json', cgi)

    def getMemlogLastId(self, facility=None, maxlevel=None):
        lastId = 0
        log = self.getMemlog(facility=facility, maxlevel=maxlevel)
        if len(log):
            lastId = log[-1]['id']
        return lastId

    @staticmethod
    def hystByPrec(precision):
        hyst = 1
        if precision == 1:
            hyst = 0.5
        if precision == 2:
            hyst = 0.05
        if precision == 3:
            hyst = 0.005
        if precision == 4:
            hyst = 0.0005

        return hyst

    def __init__(self, host, logLevel=LOG_INFO):
        self.host = host
        self.setLogLevel(logLevel)
        self.allConfigJson = None
        self.allStatusJson = None
        self.entities = None
