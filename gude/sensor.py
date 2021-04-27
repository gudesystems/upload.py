import time
from gude.httpDevice import HttpDevice


class SensorVector:
    def __getitem__(self, item):
        return int(self.vector[item])

    def __str__(self):
        return f"{self[0]}.{self[1]}.{self[2]}.{self[3]}.{self[4]}"

    def getTuple(self):
        return self[0], self[1], self[2], self[3], self[4]

    def __init__(self, typ=0, index=0, groupIndex=0, groupMemberIndex=0, fieldIndex=0, fromStr=None):
        if fromStr is None:
            self.vector = [typ, index, groupIndex, groupMemberIndex, fieldIndex]
        else:
            self.vector = fromStr.split('.')


class SensorField:
    def __str__(self):
        return f"{self.value} {self.unit}"

    def __init__(self, vector, props, value):
        self.vector = vector
        self.name = props['name']
        self.unit = props['unit']
        self.decPrecision = props.get('decPrecision', 0)
        self.value = value['v']
        self.statistics = props.get('st', [])
        self.state = props.get('s', 0)
        self.json = {
            'descr': props,
            'value': value
        }


class SensorDev:

    TYPE_STRING = {
        1:  "Line",
        8:  "Port",
        9:  "Line",
        52: "THP",
        101: "Bank",
        102: "Powersource"
    }

    def parseSensorJson(self):
        descr = {}
        values = {}

        jsonIndex = -1

        sensorValueCollection = []
        for sensorValues in self.json['values']:
            sensorValueCollection.append((sensorValues['type'], sensorValues['num']))
        mismatch = self.sensorValueCollection != sensorValueCollection
        self.sensorValueCollection = sensorValueCollection
        if mismatch:
            return False

        for sensorType in self.json['descr']:
            jsonIndex += 1

            sensorValues = self.json['values'][jsonIndex]["values"]
            st = sensorType["type"]

            for (si, sensorProp) in enumerate(sensorType["properties"]):
                index = sensorProp.get("real_id", si)

                self.sensorProps[(st, index)] = sensorProp

                # simple ungrouped sensors
                if 'fields' in sensorType:
                    for (sf, fieldProp) in enumerate(sensorType["fields"]):
                        v = str(SensorVector(st, index, 0, 0, sf))
                        descr[v] = fieldProp
                        values[v] = sensorValues[si][sf]

                # complex sensor groups
                if 'groups' in sensorType:
                    for (gi, sensorGroup) in enumerate(sensorProp["groups"]):
                        for (grm, groupMember) in enumerate(sensorGroup):
                            self.sensorProps[(st, index, gi, grm)] = groupMember

                            for (sf, fieldProp) in enumerate(sensorType["groups"][gi]["fields"]):
                                v = str(str(SensorVector(st, index, gi, grm, sf)))
                                descr[v] = fieldProp
                                values[v] = sensorValues[si][gi][grm][sf]

        for v in descr.keys():
            self.sensors[v] = SensorField(SensorVector(fromStr=v), descr[v], values[v])

        return True

    def get(self, vectorStr=None, cached=True, cgiParams=None):
        if cgiParams is None:
            cgiParams = {}
        if self.json_cache_ttl == 0 or self.values_updated_at + self.json_cache_ttl < time.time():
            cached = False

        retry = 2
        while not cached and retry:
            status_flags = self.httpDev.JSON_STATUS_SENSOR_VALUES + self.httpDev.JSON_STATUS_SENSOR_EXT
            if self.json['descr'] == {}:
                status_flags |= self.httpDev.JSON_STATUS_SENSOR_DESCR + \
                                self.httpDev.JSON_STATUS_HARDWARE + \
                                self.httpDev.JSON_STATUS_MISC

            status = self.httpDev.httpGetStatusJson(status_flags, cgiParams)
            self.values_updated_at = time.time()

            if self.json['descr'] == {}:
                self.json['descr'] = status['sensor_descr']
                self.json['hardware'] = status['hardware']
                self.json['misc'] = status['misc']

            self.json['values'] = status['sensor_values']

            try:
                cached = self.parseSensorJson()
            except:
                cached = False

            if not cached:
                cgiParams = {}
                self.json['descr'] = {}
                self.sensors = {}
                retry -= 1

        if not cached:
            raise ValueError("descr/values mismatch pair cannot be resolved")

        if vectorStr is not None and vectorStr in self.sensors:
            return self.sensors[vectorStr]

    # set sensor field value (enable virtual sensor mode)
    def set(self, vectorStr, value, kalman=True):
        virtual_sensor_cmd = {
            'cmd': self.httpDev.CGI_CMD_VIRTUAL_SENSOR,
            'vtmode': 1,
            'kalman': 1 if kalman else 0,
            'sensor': vectorStr,
            'value': value
        }
        return self.get(vectorStr, cached=False, cgiParams=virtual_sensor_cmd)

    # release sensor field from manuel control (disable virtual sensor mode)
    def unset(self, vectorStr):
        virtual_sensor_cmd = {
            'cmd': self.httpDev.CGI_CMD_VIRTUAL_SENSOR,
            'vtmode': 0,
            'sensor': vectorStr
        }
        return self.get(vectorStr, cached=False, cgiParams=virtual_sensor_cmd)

    def updateData(self, status=None):
        if status is None:
            self.get(cached=False)
            return

        self.json['values'] = status['sensor_values']

        if status.get('sensor_descr', {}) != {}:
            for sensorValues in self.json['values']:
                self.sensorValueCollection.append((sensorValues['type'], sensorValues['num']))
            self.json['descr'] = status['sensor_descr']

        self.values_updated_at = time.time()
        return self.parseSensorJson()

    def setCacheTtl(self, ttl):
        self.json_cache_ttl = ttl

    def disableCache(self):
        self.setCacheTtl(-1)

    def __init__(self, host, ssl=False, username='admin', password='admin', logLevel=HttpDevice.LOG_NONE,
                 json=None, httpDev=None):
        # 0  : no cache at all, always reload JSON
        # <0 : cache never expires
        # >0 : Cache TTL in seconds
        self.json_cache_ttl = 1.0

        self.json = {
            'descr': {},
            'values': {}
        }
        self.sensors = {}
        self.sensorProps = {}
        self.sensorValueCollection = []

        self.values_updated_at = 0

        if httpDev is None:
            self.httpDev = HttpDevice(host)
            self.httpDev.httpOpts['ssl'] = ssl
            self.httpDev.httpOpts['username'] = username
            self.httpDev.httpOpts['password'] = password
            self.httpDev.setLogLevel(logLevel)
        else:
            self.httpDev = httpDev

        if json is None:
            self.get()
        else:
            self.updateData(json)
