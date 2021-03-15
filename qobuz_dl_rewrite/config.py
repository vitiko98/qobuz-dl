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
        self.credentials = {"email": None, "password": None}
        self.authentication = {"app_id": None, "secrets": None}
        self.downloads_database = None
        self.filters = {"smart_discography": False, "albums_only": False}
        self.downloads = {"downloads_folder": folder, "quality": quality}
        self.metadata = {"embed_covers": True, "large_covers": False, "default_comment": None}
        self.path_format = {"folder": folder_format, "track": track_format}

        if config_path is not None:
            with open(config_path) as cfg:
                self.__dict__.update(yaml.load(cfg))

    def reset(self, path):
        with open(path, 'w') as cfg:
            yaml.dump(self.__dict__, cfg)

    def load(self, path):
        with open(path) as cfg:
            self.__dict__ = yaml.load(cfg)

    def update(self, args):
        """Update configuration based on args from CLI.

        :param args:
        """
        self.__dict__.update(args)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, val):
        setattr(self, key, val)

    def __repr__(self):
        return f"Config({pformat(self.__dict__)})"
