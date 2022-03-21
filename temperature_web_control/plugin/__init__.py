import os

from temperature_web_control.utils import list_all_modules

# Automatically load available drivers

plugins = list_all_modules("(.*)_plugin", os.path.dirname(os.path.abspath(__file__)))