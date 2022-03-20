import sys
import os
import pkgutil
import re

# Automatically load available drivers

def get_module(full_package_name, module_info):
    if full_package_name not in sys.modules:
        module = module_info.module_finder.find_module(
            module_info.name).load_module(module_info.name)
        sys.modules[full_package_name] = module
    else:
        module = sys.modules[full_package_name]

    return module

def list_all_driver_modules():
    drivers_dict = {}

    dirname = os.path.dirname(os.path.abspath(__file__))
    for module_info in pkgutil.iter_modules([dirname]):
        package_name = module_info.name
        match = re.match("(.*)_driver", package_name)
        if not match:
            continue

        driver_name = match[1]

        full_package_name = f"{dirname}.{package_name}"
        drivers_dict[driver_name] = get_module(full_package_name, module_info)

    return drivers_dict

drivers = list_all_driver_modules()
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