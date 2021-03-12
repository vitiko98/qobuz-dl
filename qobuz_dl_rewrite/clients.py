import hashlib
import logging
import time
from abc import ABC, abstractmethod
from typing import Union

import requests
import tidalapi

from .exceptions import (
    AuthenticationError,
    IneligibleError,
    InvalidAppIdError,
    InvalidAppSecretError,
    InvalidQuality,
)
from .spoofbuz import Spoofer

logger = logging.getLogger(__name__)

# Qobuz
QOBUZ_BASE = "https://www.qobuz.com/api.json/0.2/"
AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0"

# Tidal
TIDAL_Q_IDS = {
    4: tidalapi.Quality.low,  # AAC
    5: tidalapi.Quality.high,  # AAC
    6: tidalapi.Quality.lossless,  # Lossless, but it also could be MQA
}


# Deezer
DEEZER_BASE = "https://api.deezer.com"
DEEZER_DL = "http://dz.loaderapp.info/deezer"
DEEZER_Q_IDS = {4: 128, 5: 320, 6: 1411}


class ClientInterface(ABC):
    """Common API for clients of all platforms. Do not directly use this
    class; use a subclass.
    """

    @abstractmethod
    def search(self, query: str, type_="album"):
        """Search API for query.

        :param query:
        :type query: str
        :param type_:
        """
        pass

    @abstractmethod
    def get(self, meta_id, type_="album"):
        """Get metadata.

        :param meta_id:
        :param type_:
        """
        pass

    @abstractmethod
    def get_file_url(self, track_id):
        """Get the direct download url for a file.

        :param track_id: id of the track
        """
        pass


class SecureClientInterface(ClientInterface):
    """Identical to a ClientInterface except for a login
    method."""

    @abstractmethod
    def login(self, **kwargs):
        """Authenticate the client.

        :param kwargs:
        """
        pass


class QobuzClient(SecureClientInterface):
    # ------- Public Methods -------------
    def login(self, email: str, pwd: str, **kwargs):
        """Authenticate the QobuzClient. Must have a paid membership.

        :param email: email for the qobuz account
        :type email: str
        :param pwd: password for the qobuz account
        :type pwd: str
        :param kwargs: include `app_id` and `secrets` to save a lot of time
        """
        if (kwargs.get("app_id") or kwargs.get("secrets")) is None:
            logger.info("app_id and secrets not provided, fetching tokens")
            spoofer = Spoofer()
            kwargs["app_id"] = spoofer.get_app_id()
            kwargs["secrets"] = spoofer.get_secrets()

        self.id = kwargs["app_id"]
        self.secrets = kwargs["secrets"]

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": AGENT,
                "X-App-Id": self.id,
            }
        )

        logger.debug("authenticating")
        self._auth(email, pwd)
        logger.debug("setting up config")
        self._cfg_setup()
        logger.debug("ready to use")

        if kwargs.get("save_secrets"):
            return self.id, self.secrets

    def search(self, query: str, media_type: str = "album", limit: int = 500):
        if media_type.endswith("s"):
            media_type = media_type[:-1]

        f_map = {
            "album": self.search_albums,
            "artist": self.search_artists,
            "playlist": self.search_playlists,
            "track": self.search_tracks,
        }

        search_func = f_map[media_type]
        return search_func(query, limit=limit)

    def get(self, meta_id: Union[str, int], media_type: str = "album"):
        f_map = {
            "album": self.get_album_meta,
            "artist": self.get_artist_meta,
            "playlist": self.get_plist_meta,
            "track": self.get_track_meta,
        }
        return f_map[media_type](meta_id)

    def get_file_url(self, meta_id: Union[str, int], quality: int = 7):
        return self._api_call("track/getFileUrl", id=meta_id, fmt_id=quality)

    # ---------- Private Methods ---------------

    # Credits to Sorrow446 for these methods

    # TODO: Maybe a way of reducing the if statements (?)
    # TODO: prepend a `_` before private methods
    def _api_call(self, epoint, **kwargs):
        if epoint == "user/login":
            params = {
                "email": kwargs.get("email"),
                "password": kwargs.get("pwd"),
                "app_id": self.id,
            }
        elif epoint == "track/get":
            params = {"track_id": kwargs.get("id")}
        elif epoint == "album/get":
            params = {"album_id": kwargs.get("id")}
        elif epoint == "playlist/get":
            params = {
                "extra": "tracks",
                "playlist_id": kwargs.get("id"),
                "limit": 500,
                "offset": kwargs.get("offset"),
            }
        elif epoint == "artist/get":
            params = {
                "app_id": self.id,
                "artist_id": kwargs.get("id"),
                "limit": 500,
                "offset": kwargs.get("offset"),
                "extra": "albums",
            }
        elif epoint == "label/get":
            params = {
                "label_id": kwargs.get("id"),
                "limit": 500,
                "offset": kwargs.get("offset"),
                "extra": "albums",
            }
        elif epoint == "userLibrary/getAlbumsList":
            unix = time.time()
            r_sig = "userLibrarygetAlbumsList" + str(unix) + kwargs["sec"]
            r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
            params = {
                "app_id": self.id,
                "user_auth_token": self.uat,
                "request_ts": unix,
                "request_sig": r_sig_hashed,
            }
        elif epoint == "track/getFileUrl":
            unix = time.time()

            track_id = kwargs.get("id")
            fmt_id = kwargs.get("fmt_id", 6)  # 6 as default

            if int(fmt_id) not in (5, 6, 7, 27):  # Needed?
                raise InvalidQuality("Invalid quality id: choose between 5, 6, 7 or 27")

            r_sig = f"trackgetFileUrlformat_id{fmt_id}intentstreamtrack_id{track_id}{unix}{self.sec}"
            logger.debug("Raw request signature: %s", r_sig)
            r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
            logger.debug("Hashed request signature: %s", r_sig_hashed)

            params = {
                "request_ts": unix,
                "request_sig": r_sig_hashed,
                "track_id": track_id,
                "format_id": fmt_id,
                "intent": "stream",
            }
        elif epoint == "album/getFeatured":
            unix = time.time()
            params = {
                "limit": 500,
                "offset": kwargs.get("offset"),
                "type": kwargs.get("type"),
            }
        else:
            params = kwargs

        r = self.session.get(f"{QOBUZ_BASE}/{epoint}", params=params)

        if epoint == "user/login":
            if r.status_code == 401:
                raise AuthenticationError("Invalid credentials from params %s" % params)
            elif r.status_code == 400:
                raise InvalidAppIdError("Invalid app id from params %s" % params)
            else:
                logger.info("Logged in to Qobuz")

        elif epoint in ["track/getFileUrl", "userLibrary/getAlbumsList"]:
            if r.status_code == 400:
                raise InvalidAppSecretError(
                    "Invalid app secret from params %s" % params
                )

        r.raise_for_status()  # Needed?

        return r.json()

    def _auth(self, email, pwd):
        usr_info = self._api_call("user/login", email=email, pwd=pwd)

        if not usr_info["user"]["credential"]["parameters"]:
            raise IneligibleError("Free accounts are not eligible to download tracks.")

        self.uat = usr_info["user_auth_token"]

        self.session.headers.update({"X-User-Auth-Token": self.uat})

        self.label = usr_info["user"]["credential"]["parameters"]["short_label"]

        # logger.info(f"Membership: {self.label}")

    # Needs more testing and debugging
    def _multi_meta(self, epoint: str, key: str, meta_id: Union[str, int], type_: str):
        total = 1
        offset = 0
        while total > 0:
            if type_ in ("tracks", "albums"):
                j = self._api_call(epoint, id=meta_id, offset=offset, type=type)[type]
            else:
                j = self._api_call(epoint, id=meta_id, offset=offset, type=type)
            if offset == 0:
                yield j
                total = j[key] - 500
            else:
                yield j
                total -= 500
            offset += 500

    def get_album_meta(self, id):
        return self._api_call("album/get", id=id)

    def get_track_meta(self, id):
        return self._api_call("track/get", id=id)

    def get_artist_meta(self, id):
        return self._multi_meta("artist/get", "albums_count", id, None)

    def get_plist_meta(self, id):
        return self._multi_meta("playlist/get", "tracks_count", id, None)

    def get_label_meta(self, id):
        return self._multi_meta("label/get", "albums_count", id, None)

    def search_albums(self, query, limit):
        return self._api_call("album/search", query=query, limit=limit)

    def search_artists(self, query, limit):
        return self._api_call("artist/search", query=query, limit=limit)

    def search_playlists(self, query, limit):
        return self._api_call("playlist/search", query=query, limit=limit)

    def search_tracks(self, query, limit):
        return self._api_call("track/search", query=query, limit=limit)

    def get_favorite_albums(self, offset, limit):
        return self._api_call(
            "favorite/getUserFavorites", type="albums", offset=offset, limit=limit
        )

    def get_favorite_tracks(self, offset, limit):
        return self._api_call(
            "favorite/getUserFavorites", type="tracks", offset=offset, limit=limit
        )

    def get_favorite_artists(self, offset, limit):
        return self._api_call(
            "favorite/getUserFavorites", type="artists", offset=offset, limit=limit
        )

    def get_user_playlists(self, limit):
        return self._api_call("playlist/getUserPlaylists", limit=limit)

    def test_secret(self, sec):
        try:
            self._api_call("userLibrary/getAlbumsList", sec=sec)
            return True
        except InvalidAppSecretError as error:
            logger.debug("Test for %s secret didn't work: %s", sec, error)
            return False

    def _cfg_setup(self):
        for secret in self.secrets:
            if self.test_secret(secret):
                self.sec = secret
                break
        if not hasattr(self, "sec"):
            raise InvalidAppSecretError(f"Invalid secrets: {self.secrets}")


class DeezerClient(ClientInterface):
    def __init__(self):
        self.session = requests.Session()

    def search(self, query: str, media_type: str = "album"):
        """Search API for query.

        :param query:
        :type query: str
        :param type_:
        :type type_: str
        """
        # TODO: more robust url sanitize
        query = query.replace(" ", "+")

        if media_type.endswith("s"):
            media_type = media_type[:-1]

        response = self.session.get(f"{DEEZER_BASE}/search/{media_type}?q={query}")
        response.raise_for_status()

        return response.json()

    def get(self, meta_id: Union[str, int], type_: str = "album"):
        """Get metadata.

        :param meta_id:
        :type meta_id: Union[str, int]
        :param type_:
        :type type_: str
        """
        response = self.session.get(f"{DEEZER_BASE}/{type_}/{meta_id}")
        response.raise_for_status()

        return response.json()

    @staticmethod
    def get_file_url(meta_id: Union[str, int], quality: int = 6):
        return f'{DEEZER_DL}/{DEEZER_Q_IDS[quality]}/"{DEEZER_BASE}/track/{meta_id}"'


class TidalClient(SecureClientInterface):
    def login(self, email: str, pwd: str):

        config = tidalapi.Config()

        self.session = tidalapi.Session(config=config)
        self.session.login(email, pwd)
        logger.info("Logged into Tidal")

    def search(self, query: str, media_type: str = "album", limit: int = 50):
        """
        :param query:
        :type query: str
        :param media_type: artist, album, playlist, or track
        :type media_type: str
        :param limit:
        :type limit: int
        :raises ValueError: if field value is invalid
        """

        return self.session.search(media_type, query, limit)

    def get(self, meta_id: Union[str, int], media_type: str = "album"):
        """Get metadata.

        :param meta_id:
        :type meta_id: Union[str, int]
        :param media_type:
        :type media_type: str
        """
        f_map = {
            "album": self.session.get_album,
            "artist": self.session.get_artist,  # or get_artist_albums?
            "playlist": self.session.get_playlist,
            "track": self.session.get_track,
        }
        return f_map[media_type](meta_id)

    def get_file_url(self, meta_id: Union[str, int], quality: int = 6):
        """
        :param meta_id:
        :type meta_id: Union[str, int]
        :param quality:
        :type quality: int
        """
        # Not tested
        self.session._config.quality = TIDAL_Q_IDS[quality]
        return self.session.get_track_url(meta_id)
