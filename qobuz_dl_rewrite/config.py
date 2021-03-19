import logging
import os
from pprint import pformat

import click
from ruamel.yaml import YAML

from .exceptions import InvalidSourceError

yaml = YAML()


logger = logging.getLogger(__name__)


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

    def __init__(self, config_path: str):

        # DEFAULTS
        folder = "Downloads"
        quality = 6
        folder_format = "{artist} - {album} ({year}) [{bit_depth}B-{sampling_rate}kHz]"
        track_format = "{tracknumber}. {tracktitle}"

        self.Qobuz = {
            "enabled": True,
            "email": None,
            "password": None,
            "app_id": "",  # Avoid NoneType error
            "secrets": "",
        }
        self.Tidal = {"enabled": True, "email": None, "password": None}
        self.Deezer = {"enabled": True}
        self.downloads_database = None
        self.filters = {"smart_discography": False, "albums_only": False}
        self.downloads = {"folder": folder, "quality": quality}
        self.metadata = {
            "embed_covers": False,
            "large_covers": False,
            "default_comment": None,
            "remove_extra_tags": False,
        }
        self.path_format = {"folder": folder_format, "track": track_format}

        self.__path = config_path
        self.__loaded = False

    def save(self):
        if self.__loaded:
            info = dict()
            for k, v in self.__dict__.items():
                logger.debug("Adding value %s to %s key to config", k, v)
                if not k.startswith("_"):
                    info[k] = v

            with open(self.__path, "w") as cfg:
                logger.debug("Config saved: %s", self.__path)
                yaml.dump(info, cfg)

    def load(self):
        if not os.path.isfile(self.__path):
            logger.debug("File not found. Creating one: %s", self.__path)
            self.__loaded = True
            self.save()

            click.secho(
                "A config file has been created. Please update it "
                f"with your credentials: {self.__path}",
                fg="yellow",
            )

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
        elif source == 'deezer':
            return dict()
        else:
            raise InvalidSourceError(source)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, val):
        setattr(self, key, val)

    def __repr__(self):
        return f"Config({pformat(self.__dict__)})"
