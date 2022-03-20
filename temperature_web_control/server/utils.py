import yaml


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


