import os

from temperature_web_control.utils import list_all_modules

# Automatically load available drivers

drivers = list_all_modules("(.*)_driver", os.path.dirname(os.path.abspath(__file__)))
driver_loaders = {}

for driver in drivers.values():
    for t in driver.dev_types():
        driver_loaders[t] = driver.from_config_dict

def load_driver(config_dict: dict):
    """
    Instantiate device instance based on config_dict.
    :param: config_dict:
    :return: device instance described by config_dict.
    """
    if config_dict['dev_type'] in driver_loaders:
        return driver_loaders[config_dict['dev_type']](config_dict)