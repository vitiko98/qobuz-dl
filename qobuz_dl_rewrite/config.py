import yaml


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
        self.directory = "Qobuz Downloads"
        self.quality = 6
        self.embed_art = False
        self.lucky_limit = 1
        self.lucky_type = "album"
        self.interactive_limit = 20
        self.ignore_singles_eps = False
        self.no_m3u_for_playlists = False
        self.quality_fallback = True
        self.cover_og_quality = False
        self.no_cover = False
        self.downloads_db = None
        self.folder_format = "{artist} - {album} ({year}) [{bit_depth}B-{sampling_rate}kHz]"
        self.track_format = "{tracknumber}. {tracktitle}"
        self.smart_discography = False

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
