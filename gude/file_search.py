import os
from configparser import ConfigParser


def rekursive_search(path):
    results = list()
    for item_name in os.listdir(path):
        if os.path.isfile(os.path.join(path, item_name)):
            if item_name[:8] == 'firmware' and '.bin' in item_name[9:]:
                result = get_model(item_name, path)
                result['version'] = get_version(item_name)
                if result is not None or result['version'] is not None:
                    results.append(result)
        else:
            results += rekursive_search(os.path.join(path, item_name))
    return results


def get_version(item_name, start_index=9):
    try:
        return item_name[start_index:].split('_v')[1].split('.bin')[0]
    except IndexError:
        print(f"Could not detect version info: ({item_name[start_index:]})")
        return None


def get_model(item_name, path, start_index=9):
    try:
        result = {}
        if item_name[start_index-1:start_index] == '-':
            # online name
            model = item_name[start_index:].split('_')[0]
            result['name'] = str()
            result['model_nbr'] = str()
            rev_2 = ''
            if 'r2' in model or 'R2' in model:
                model = model.replace('r2', '').replace('R2', '')
                rev_2 = 'R2'
            for char in model:
                if char.isnumeric():
                    result['model_nbr'] += char
                elif char != '_' and char != '-':
                    result['name'] += char
            result['model_nbr'] += rev_2
            result['model_oem'] = "online"
            result['dir'] = path
        elif item_name[start_index-1:start_index] == '_':
            # offline name
            d_split = path.replace(os.path.dirname(path) + '\\', '').split('_')
            infos = item_name[start_index:].split('_')
            if len(d_split) == 1:
                print(f"Could not determine Device Name/Typ by folder name ({path} {item_name})! JSON NAME MAY BE WRONG")
                result['name'] = ''
            else:
                result['name'] = d_split[0].lower()
                if d_split[1] != infos[0]:
                    print("Model by folder name does not match with model by file name!")
            result['model_nbr'] = infos[0]
            result['model_oem'] = infos[1]
            result['dir'] = path
        return result
    except IndexError:
        print(f"Could not detect model info: ({item_name[start_index:]})")
        return None


def get_unique_devices(items):
    """
    Function to get unique devices from a list of devices Using the latest version
    :param items List: config parser to be edited
    :rtype: List: List of unique devices
    """
    devices_by_nbr = dict()
    for item in items:
        if item['model_nbr'] in devices_by_nbr:
            devices_by_nbr[item['model_nbr']].append(item)
        else:
            devices_by_nbr[item['model_nbr']] = [item]
    unique_result = list()
    for value in devices_by_nbr.values():
        best = None
        # if len(value) > 1:
        #     print('debug here')
        for item in value:
            if best is None:
                best = item
            elif (item['model_oem'] == 'gude' or item['model_oem'] == 'online') and item['version'] >= best['version']:
                best = item
        unique_result.append(best)
    return unique_result


def get_config(unique_items, config=None):
    if config is None:
        config = ConfigParser()

    for item in unique_items:
        print(item)

        filename = ''
        if item['model_oem'] == 'online':
            filename = 'firmware-' + item['name'] + item['model_nbr'].replace("R2", "-r2") + '_v{version}.bin'
        else:
            filename = 'firmware_' + item['model_nbr'] + '_' + item['model_oem'] + '_v{version}.bin'

        config[item['model_nbr']] = {
            'json': 'firmware-' + item['name'] + item['model_nbr'].replace("R2", "-r2") + '.json',
            'version': item['version'],
            'filename': filename,
            'path': item['dir']
        }
    return config


if __name__ == '__main__':
    root_dir = 'W:\\Produktentwicklung\\Plattformen-Allgemein\\MQX-Kinetis\\latest-builds-debugjson'
    root_dir = 'C:\\Users\\fn\\Downloads\\firmware-epc8031_v1.3.0'
    root_dir = 'C:\\Users\\fn\\Downloads'
    root_dir = 'C:\\Users\\fn\\Downloads\\sample'

    items = rekursive_search(root_dir)

    unique_items = get_unique_devices(items)

    config = get_config(unique_items)


    with open('version.offline.ini', 'w') as configfile:
        config.write(configfile)
