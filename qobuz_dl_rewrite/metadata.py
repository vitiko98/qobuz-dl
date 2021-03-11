import json
import logging
import re
from typing import Optional, Union

from .constants import COPYRIGHT, FLAC_KEY, MP3_KEY, MP4_KEY, PHON_COPYRIGHT
from .exceptions import InvalidContainerError

logger = logging.getLogger(__name__)


class TrackMetadata:
    # TODO: implement the ones that are not
    """Contains all of the metadata needed to tag the file.
    Available attributes:
        * title
        * artist
        * album
        * albumartist
        * composer
        * year
        * comment
        * description
        * purchase_date
        * grouping
        * genre
        * lyrics
        * encoder
        * copyright
        * compilation
        * cover
        * tracknumber
        * discnumber

    """

    def __init__(self, track: Optional[dict] = None, album: Optional[dict] = None):
        """Creates a TrackMetadata object optionally initialized with
        dicts returned by the Qobuz API.

        :param track: track dict from API
        :type track: Optional[dict]
        :param album: album dict from API
        :type album: Optional[dict]
        """
        # self.title = None
        # self.artist = None
        self.album = None
        self.albumartist = None
        self.composer = None
        # self.year = None
        self.comment = "Lossless download from Qobuz"
        self.description = None
        self.purchase_date = None
        self.grouping = None
        # self.genre = None
        self.lyrics = None
        self.encoder = None
        # self.copyright = None
        self.compilation = None
        self.cover = None
        self.tracknumber = None
        self.discnumber = None

        if track and album is None:
            return

        if track is not None:
            self.add_track_meta(track)
            # prefer track['album'] over album
            if track.get("album"):
                album = track.get("album")

        if album is not None:
            self.add_album_meta(album)

    def add_album_meta(self, album: dict):
        """Parse the metadata from an album dict returned by the
        Qobuz API.

        :param dict album: from the Qobuz API
        """
        self.album = album.get("title")
        self.tracktotal = str(album.get("tracks_count", 1))
        self.genre = album.get("genres_list", [])
        self.date = album.get("release_date_original") or album.get("release_date")
        self.copyright = album.get("copyright")
        self.albumartist = album.get("artist", {}).get("name")

        self.label = album.get("label")

        if isinstance(self.label, dict):
            self.label = self.label.get("name")

    def add_track_meta(self, track: dict):
        """Parse the metadata from a track dict returned by the
        Qobuz API.

        :param track:
        """
        self.title = track.get("title").strip()
        if track.get("version"):
            logger.debug("Version found: %s", track["version"])
            self.title = f"{self.title} ({track['version']})"
        if track.get("work"):
            logger.debug("Work found: %s", track["work"])
            self.title = f"{track['work']}: {self.title}"

        self.tracknumber = str(track.get("track_number", 1))
        self.discnumber = str(track.get("media_number", 1))
        try:
            self.artist = track["performer"]["name"]
        except KeyError:
            if hasattr(self, "albumartist"):
                self.artist = self.albumartist

    @property
    def artist(self) -> Union[str, None]:
        """Returns the value to set for the artist tag. Defaults to
        `self.albumartist` if there is no track artist.

        :rtype: str
        """
        if self._artist is None and self.albumartist is not None:
            return self.albumartist
        elif self._artist is not None:
            return self._artist

    @artist.setter
    def artist(self, val: str):
        """Sets the internal artist variable to val.

        :param val:
        :type val: str
        """
        self._artist = val

    @property
    def genre(self) -> str:
        """Formats the genre list returned by the Qobuz API.
        >>> g = ['Pop/Rock', 'Pop/Rock→Rock', 'Pop/Rock→Rock→Alternatif et Indé']
        >>> _format_genres(g)
        'Pop, Rock, Alternatif et Indé'

        :rtype: str
        """
        genres = re.findall(r"([^\u2192\/]+)", "/".join(self._genres))
        no_repeats = []
        [no_repeats.append(g) for g in genres if g not in no_repeats]
        return ", ".join(no_repeats)

    @genre.setter
    def genre(self, val: list):  # Is the assert necessary?
        """Sets the internal `genre` field to the given list.
        It is not formatted until it is requested with `meta.genre`.

        :param val:
        :type val: list
        """
        assert type(val) == list
        self._genres = val

    @property
    def copyright(self) -> Union[str, None]:
        """Formats the copyright string to use nice-looking unicode
        characters.

        :rtype: str, None
        """
        if hasattr(self, "_copyright"):
            cr = self._copyright.replace("(P)", PHON_COPYRIGHT)
            cr = cr.replace("(C)", COPYRIGHT)
            return cr
        else:
            raise AttributeError("Copyright tag must be set before acessing")

    @copyright.setter
    def copyright(self, val: str):
        """Sets the internal copyright variable to the given value.
        Only formatted when requested.

        :param val:
        :type val: str
        """
        self._copyright = val

    @property
    def year(self) -> str:
        """Returns the year published of the track.

        :rtype: str
        """
        if hasattr(self, "_year"):
            return self._year

        return self.date[:4]

    @year.setter
    def year(self, val):
        """Sets the internal year variable to val.

        :param val:
        """
        self._year = val

    def get_formatter(self) -> dict:
        """Returns a dict that is used to apply values to file format strings.

        :rtype: dict
        """
        # the keys in the tuple are the possible keys for format strings
        return {
            k: getattr(self, k)
            for k in ("artist", "year", "album", "tracknumber", "title")
        }

    def tags(self, container: str = "flac"):
        """Return (key, value) pairs for tagging with mutagen.

        Usage:
        >>> audio = MP4(path)
        >>> for k, v in meta.tags(container='MP4'):
        ...     audio[k] = v
        >>> audio.save()

        :param container: the container format
        :type container: str
        """
        container = container.lower()
        if container in ("flac", "vorbis"):
            return self.__gen_flac_tags()
        elif container in ("mp3", "id3"):
            return self.__gen_mp3_tags()
        elif container in ("alac", "m4a", "mp4", "aac"):
            return self.__gen_mp4_tags()
        else:
            raise InvalidContainerError(f"Invalid container {container}")

    def __gen_flac_tags(self):
        for k, v in FLAC_KEY.items():
            tag = getattr(self, k)
            if tag is not None:
                yield (v, tag)

    def __gen_mp3_tags(self):
        for k, v in MP3_KEY.items():
            if k == "tracknumber":
                text = f"{self.tracknumber}/{self.tracktotal}"
            elif k == "discnumber":
                text = str(self.discnumber)
            else:
                text = getattr(self, k)

            if text is not None:
                yield (v.__name__, v(encoding=3, text=text))

    def __mp4_tags(self):
        for k, v in MP4_KEY.items():
            return (v, getattr(self, k))

    def __setitem__(self, key, val):
        """Dict-like access for tags.

        :param key:
        :param val:
        """
        setattr(self, key, val)

    def __getitem__(self, key):
        """Dict-like access for tags.

        :param key:
        """
        return getattr(self, key)

    def get(self, key, default=None):
        if hasattr(self, key):
            res = self.__getitem__(key)
            if res is not None:
                return res

            return default

        return default

    def set(self, key, val):
        return self.__setitem__(key, val)

    def __repr__(self) -> str:
        """Returns the string representation of the metadata object.

        :rtype: str
        """
        # TODO: make a more readable repr
        return json.dumps(self.__dict__, indent=2) + f"{self.genre} {self.copyright}"
