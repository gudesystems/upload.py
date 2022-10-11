import time
from gude.httpDevice import HttpDevice


class SensorVector:
    def __getitem__(self, item):
        return int(self.vector[item])

    def __str__(self):
        return f"{self[0]}.{self[1]}.{self[2]}.{self[3]}.{self[4]}"

    def get_tuple(self):
        return self[0], self[1], self[2], self[3], self[4]

    def __init__(self, typ=0, index=0, group_index=0, group_member_index=0, field_index=0, from_str=None):
        if from_str is None:
            self.vector = [typ, index, group_index, group_member_index, field_index]
        else:
            self.vector = from_str.split('.')


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

    def parse_sensor_json(self):
        descr = {}
        values = {}

        json_index = -1

        sensor_value_collection = []
        for sensor_values in self.json['values']:
            sensor_value_collection.append((sensor_values['type'], sensor_values['num']))
        mismatch = self.sensorValueCollection != sensor_value_collection
        self.sensorValueCollection = sensor_value_collection
        if mismatch:
            return False

        for sensorType in self.json['descr']:
            json_index += 1

            sensor_values = self.json['values'][json_index]["values"]
            st = sensorType["type"]

            for (si, sensorProp) in enumerate(sensorType["properties"]):
                index = sensorProp.get("real_id", si)

                self.sensorProps[(st, index)] = sensorProp

                # simple ungrouped sensors
                if 'fields' in sensorType:
                    for (sf, fieldProp) in enumerate(sensorType["fields"]):
                        v = str(SensorVector(st, index, 0, 0, sf))
                        descr[v] = fieldProp
                        values[v] = sensor_values[si][sf]

                # complex sensor groups
                if 'groups' in sensorType:
                    for (gi, sensorGroup) in enumerate(sensorProp["groups"]):
                        for (grm, groupMember) in enumerate(sensorGroup):
                            self.sensorProps[(st, index, gi, grm)] = groupMember

                            for (sf, fieldProp) in enumerate(sensorType["groups"][gi]["fields"]):
                                v = str(str(SensorVector(st, index, gi, grm, sf)))
                                descr[v] = fieldProp
                                values[v] = sensor_values[si][gi][grm][sf]

        for v in descr.keys():
            self.sensors[v] = SensorField(SensorVector(from_str=v), descr[v], values[v])

        return True

    def get(self, vector_str=None, cached=True, cgi_params=None):
        if cgi_params is None:
            cgi_params = {}
        if self.json_cache_ttl == 0 or self.values_updated_at + self.json_cache_ttl < time.time():
            cached = False

        retry = 2
        while not cached and retry:
            status_flags = self.httpDev.JSON_STATUS_SENSOR_VALUES + self.httpDev.JSON_STATUS_SENSOR_EXT
            if self.json['descr'] == {}:
                status_flags |= self.httpDev.JSON_STATUS_SENSOR_DESCR + \
                                self.httpDev.JSON_STATUS_HARDWARE + \
                                self.httpDev.JSON_STATUS_MISC

            status = self.httpDev.http_get_status_json(status_flags, cgi_params)
            self.values_updated_at = time.time()

            if self.json['descr'] == {}:
                self.json['descr'] = status['sensor_descr']
                self.json['hardware'] = status['hardware']
                self.json['misc'] = status['misc']

            self.json['values'] = status['sensor_values']

            try:
                cached = self.parse_sensor_json()
            except ValueError:
                cached = False

            if not cached:
                cgi_params = {}
                self.json['descr'] = dict()
                self.sensors = {}
                retry -= 1

        if not cached:
            raise ValueError("descr/values mismatch pair cannot be resolved")

        if vector_str is not None and vector_str in self.sensors:
            return self.sensors[vector_str]

    # set sensor field value (enable virtual sensor mode)
    def set(self, vector_str, value, kalman=True):
        virtual_sensor_cmd = {
            'cmd': self.httpDev.CGI_CMD_VIRTUAL_SENSOR,
            'vtmode': 1,
            'kalman': 1 if kalman else 0,
            'sensor': vector_str,
            'value': value
        }
        return self.get(vector_str, cached=False, cgi_params=virtual_sensor_cmd)

    # release sensor field from manuel control (disable virtual sensor mode)
    def unset(self, vector_str):
        virtual_sensor_cmd = {
            'cmd': self.httpDev.CGI_CMD_VIRTUAL_SENSOR,
            'vtmode': 0,
            'sensor': vector_str
        }
        return self.get(vector_str, cached=False, cgi_params=virtual_sensor_cmd)

    def freeze_current_val(self, vector):
        self.set(vector, self.get(vector).value)

    def freeze_all(self, cb_func=None):
        for vector in self.sensors:
            val = self.get(vector).value
            if vector.startswith('20.0.1') or val is None:
                continue
            if cb_func is not None:
                cb_func(vector, val)
            self.set(vector, val)

    def unfreeze_all(self):
        for vector in self.sensors:
            self.unset(vector)

    def update_data(self, status=None):
        if status is None:
            self.get(cached=False)
            return

        self.json['values'] = status['sensor_values']

        if status.get('sensor_descr', {}) != {}:
            for sensorValues in self.json['values']:
                self.sensorValueCollection.append((sensorValues['type'], sensorValues['num']))
            self.json['descr'] = status['sensor_descr']

        self.values_updated_at = time.time()
        return self.parse_sensor_json()

    def set_cache_ttl(self, ttl):
        self.json_cache_ttl = ttl

    def disable_cache(self):
        self.set_cache_ttl(-1)

    def __init__(self, host, ssl=False, username='admin', password='admin', json=None, http_dev=None):
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

        if http_dev is None:
            self.httpDev = HttpDevice(host)
            self.httpDev.httpOpts['ssl'] = ssl
            self.httpDev.httpOpts['username'] = username
            self.httpDev.httpOpts['password'] = password
        else:
            self.httpDev = http_dev

        if json is None:
            self.get()
        else:
            self.update_data(json)
