import re
import json

from constants import COPYRIGHT, PHON_COPYRIGHT


class TrackMetadata:
    """Contains all of the metadata needed to tag the file."""

    def __init__(self, track: dict = None, album: dict = None):
        """Creates a `TrackMetadata` object optionally initialized with
        dicts returned by the Qobuz API.

        :param track: track dict from API
        :type track: dict
        :param album: album dict from API
        :type album: dict
        """
        if track and album is None:
            return

        if track is not None:
            self.add_track_meta(track)
            # prefer track['album'] over album
            if "album" in track:
                album = track["album"]

        if album is not None:
            self.add_album_meta(album)

    def add_album_meta(self, album: dict):
        """Parse the metadata from an album dict returned by the
        Qobuz API.

        :param dict album: from the Qobuz API
        """
        self.album = album["title"]
        self.tracktotal = str(album["tracks_count"])
        self.genre = album["genres_list"]
        self.date = album["release_date_original"]
        self.copyright = album["copyright"]
        self.albumartist = album["artist"]["name"]

        if "label" in album:
            self.label = album["label"]["name"]

    def add_track_meta(self, track: dict):
        """Parse the metadata from a track dict returned by the
        Qobuz API.

        :param track:
        """
        self.title = track["title"]
        if "version" in track:
            self.title = f"{self.title} ({track['version']})"
        if "work" in track:
            self.title = f"{track['work']}: {self.title}"

        self.tracknumber = str(track["track_number"])
        self.discnumber = str(track["media_number"])
        try:
            self.artist = track["performer"]["name"]
        except KeyError:
            if hasattr(self, "albumartist"):
                self.artist = self.albumartist

    @property
    def artist(self) -> str:
        """Returns the value to set for the artist tag. Defaults to
        `self.albumartist` if there is no track artist.

        :rtype: str
        """
        if self._artist is None and self.albumartist is not None:
            return self.albumartist
        elif self._artist is not None:
            return self._artist
        else:
            return None

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
    def genre(self, val: list):
        """Sets the internal `genre` field to the given list.
        It is not formatted until it is requested with `meta.genre`.

        :param val:
        :type val: list
        """
        assert type(val) == list
        self._genres = val

    @property
    def copyright(self) -> str:
        """Formats the copyright string to use nice-looking unicode
        characters.

        :rtype: str
        """
        if hasattr(self, "_copyright"):
            cr = self.__copyright.replace("(P)", PHON_COPYRIGHT)
            cr = self.__copyright.replace("(C)", COPYRIGHT)
        else:
            cr = None
        return cr

    @copyright.setter
    def copyright(self, val: str):
        """Sets the internal copyright variable to the given value.
        Only formatted when requested.

        :param val:
        :type val: str
        """
        self.__copyright = val

    @property
    def year(self) -> str:
        """Returns the year published of the track.

        :rtype: str
        """
        if hasattr(self, "_year"):
            return str(self._year)
        else:
            return self.date[:4]

    @year.setter
    def year(self, val):
        """Sets the internal year variable to val.

        :param val:
        """
        self._year = val

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

    def __repr__(self) -> str:
        """Returns the string representation of the metadata object.

        :rtype: str
        """
        # TODO: make a more readable repr
        return json.dumps(self.__dict__, indent=2)
