from pprint import pformat

from ruamel.yaml import YAML

yaml = YAML()


class Config:
    """Config class that handles command line args and config files.

    ***NOT FINISHED***

    Usage:
    >>> config = Config()

    Now config contains the default settings. Let's load a config file.

    >>> config.load(CONFIG_PATH)

    Now, it has been updated. If we want to merge these with command line
    args, we pass an args object in.

    >>> config.update(args)

    To access values, use like a dict

    >>> config["quality"]
    27

    Hopefully this will make it easier to add new command line options and features.
    """

    def __init__(self, config_path=None):

        # DEFAULTS
        folder = "Downloads"
        quality = 6
        folder_format = "{artist} - {album} ({year}) [{bit_depth}B-{sampling_rate}kHz]"
        track_format = "{tracknumber}. {tracktitle}"

        self.Qobuz = {"email": None, "password": None, "app_id": None, "secrets": None}
        self.Tidal = {"email": None, "password": None}
        self.downloads_database = None
        self.filters = {"smart_discography": False, "albums_only": False}
        self.downloads = {"folder": folder, "quality": quality}
        self.metadata = {
            "embed_covers": True,
            "large_covers": False,
            "default_comment": None,
        }
        self.path_format = {"folder": folder_format, "track": track_format}

        self.__path = config_path
        self.__loaded = False

    def save(self):
        if self.__loaded:
            info = dict()
            for k, v in self.__dict__.items():
                if not k.startswith("_"):
                    info[k] = v

            with open(self.__path, "w") as cfg:
                yaml.dump(info, cfg)

    def load(self):
        with open(self.__path) as cfg:
            self.__dict__.update(yaml.load(cfg))
        self.__loaded = True

    @property
    def tidal_creds(self):
        return {
            "email": self.Tidal["email"],
            "pwd": self.Tidal["password"],
        }

    @property
    def qobuz_creds(self):
        return {
            "email": self.Qobuz["email"],
            "pwd": self.Qobuz["password"],
            "app_id": self.Qobuz["app_id"],
            "secrets": self.Qobuz["secrets"].split(","),
        }

    def creds(self, source: str):
        if source == "qobuz":
            return self.qobuz_creds
        elif source == "tidal":
            return self.tidal_creds
        else:
            raise NotImplementedError

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, val):
        setattr(self, key, val)

    def __repr__(self):
        return f"Config({pformat(self.__dict__)})"
