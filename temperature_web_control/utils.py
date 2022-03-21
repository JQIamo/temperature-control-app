import sys
import pkgutil
import re
import yaml


def get_module(full_package_name, module_info):
    if full_package_name not in sys.modules:
        module = module_info.module_finder.find_module(
            module_info.name).load_module(module_info.name)
        sys.modules[full_package_name] = module
    else:
        module = sys.modules[full_package_name]

    return module

def list_all_modules(pattern, dirname):
    modules_dict = {}

    for module_info in pkgutil.iter_modules([dirname]):
        package_name = module_info.name
        match = re.match(pattern, package_name)
        if not match:
            continue

        module_name = match[1]

        full_package_name = f"{dirname}.{package_name}"
        modules_dict[module_name] = get_module(full_package_name, module_info)

    return modules_dict


class Config:
    def __init__(self, path):
        self.config = {}
        self.path = path

        with open(path, "r") as f:
            self.config = yaml.safe_load(f)

    def get(self, *args, default=None):
        ret = self.config
        try:
            for name in args:
                ret = ret[name]
            return ret
        except KeyError as e:
            return default

    def set(self, *args, value):
        target = self.config

        for i, name in enumerate(args):
            if i == len(args) - 1:
                target[name] = value
                break

            if name in target:
                target = target[name]
            else:
                target[name] = {}
                target = target[name]

    def write(self):
        with open(self.path, "w") as f:
            yaml.dump(self.config, f)


