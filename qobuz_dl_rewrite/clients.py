import hashlib
import logging
import time
from abc import ABC, abstractmethod
from typing import Generator, Optional, Tuple, Union

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

QOBUZ_FEATURED_KEYS = [
    "most-streamed",
    "recent-releases",
    "best-sellers",
    "press-awards",
    "ideal-discography",
    "editor-picks",
    "most-featured",
    "qobuzissims",
    "new-releases",
    "new-releases-full",
]

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


# ----------- Abstract Classes -----------------


class ClientInterface(ABC):
    """Common API for clients of all platforms.

    This is an Abstract Base Class. It cannot be instantiated;
    it is merely a template.
    """

    @abstractmethod
    def search(self, query: str, media_type="album"):
        """Search API for query.

        :param query:
        :type query: str
        :param type_:
        """
        pass

    @abstractmethod
    def get(self, meta_id, media_type="album"):
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
    method.

    This is an Abstract Base Class. It cannot be instantiated;
    it is merely a template.
    """

    @abstractmethod
    def login(self, **kwargs):
        """Authenticate the client.

        :param kwargs:
        """
        pass


# ------------- Clients -----------------


class QobuzClient(SecureClientInterface):
    # ------- Public Methods -------------
    def login(self, email: str, pwd: str, **kwargs):
        """Authenticate the QobuzClient. Must have a paid membership.

        If `app_id` and `secrets` are not provided, this will run the
        Spoofer script, which retrieves them. This will take some time,
        so it is recommended to cache them somewhere for reuse.

        :param email: email for the qobuz account
        :type email: str
        :param pwd: password for the qobuz account
        :type pwd: str
        :param kwargs: app_id: str, secrets: list, return_secrets: bool
        """
        if not (kwargs.get("app_id") or kwargs.get("secrets")):
            logger.info("Fetching tokens from Qobuz")
            spoofer = Spoofer()
            kwargs["app_id"] = spoofer.get_app_id()
            kwargs["secrets"] = spoofer.get_secrets()

        self.id = str(kwargs["app_id"])  # Ensure it is a string
        self.secrets = kwargs["secrets"]

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": AGENT,
                "X-App-Id": self.id,
            }
        )

        self._auth(email, pwd)
        self._cfg_setup()
        logger.debug("Qobuz client is ready to use")

        # used for caching app_id and secrets
        if kwargs.get("return_secrets"):
            return self.id, self.secrets

    def search(self, query: str, media_type: str = "album", limit: int = 500):
        if media_type.endswith("s"):
            media_type = media_type[:-1]

        f_map = {
            "album": self.search_albums,
            "artist": self.search_artists,
            "playlist": self.search_playlists,
            "track": self.search_tracks,
            "featured": self.get_featured_albums,
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
        elif epoint == "album/getFeatured":
            params = {
                "limit": 500,
                "offset": kwargs.get("offset"),
                "type": kwargs.get("type"),
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
        else:
            params = kwargs

        logging.debug(f"calling api endpoint {epoint} with params {params}")
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

    def get_artist_meta(self, id) -> Generator:
        return self._multi_meta("artist/get", "albums_count", id, None)

    def get_plist_meta(self, id) -> Generator:
        logging.info("in get plist meta")
        return self._multi_meta("playlist/get", "tracks_count", id, None)

    def get_label_meta(self, id) -> Generator:
        return self._multi_meta("label/get", "albums_count", id, None)

    def search_albums(self, query, limit):
        return self._api_call("album/search", query=query, limit=limit)

    def search_artists(self, query, limit):
        return self._api_call("artist/search", query=query, limit=limit)

    def search_playlists(self, query, limit):
        return self._api_call("playlist/search", query=query, limit=limit)

    def search_tracks(self, query, limit):
        return self._api_call("track/search", query=query, limit=limit)

    def get_featured_albums(self, query: str, limit: int):
        """Get featured albums.

        Available queries:

            * most-streamed
            * recent-releases
            * best-sellers
            * press-awards
            * ideal-discography
            * editor-picks
            * most-featured
            * qobuzissims
            * new-releases
            * new-releases-full

        :param query: a query from the available queries
        :param limit: max number of results
        """
        assert query in QOBUZ_FEATURED_KEYS, f'query "{query}" is invalid.'

        return self._api_call("album/getFeatured", limit=limit, type=query)

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
                logger.debug("Working secret and app_id: %s - %s", secret, self.id)
                break
        if not hasattr(self, "sec"):
            raise InvalidAppSecretError(f"Invalid secrets: {self.secrets}")

    # ---------- NEW FUNCTIONS -------------
    def _api_get(self, media_type, **kwargs):
        item_id = kwargs.get("id")
        assert item_id is not None, "must provide id"

        params = {
            "app_id": self.id,
            f"{media_type}_id": item_id,
            "limit": kwargs.get("limit", 500),
            "offset": kwargs.get("offset", 0),
        }
        extras = {
            "artist": "albums",
            "playlist": "tracks",
            "label": "albums",  # not tested
        }

        if extras.get(media_type):
            params.update({"extra": extras[media_type]})

        epoint = f"{media_type}/get"

        response, status_code = self._api_request(epoint, params)
        return response

    def _api_login(self, email, pwd):
        # usr_info = self._api_call("user/login", email=email, pwd=pwd)
        params = {
            "email": email,
            "password": pwd,
            "app_id": self.id,
        }
        epoint = "user/login"
        resp, status_code = self._api_request(epoint, params)

        if status_code == 401:
            raise AuthenticationError("Invalid credentials from params %s" % params)
        elif status_code == 400:
            raise InvalidAppIdError("Invalid app id from params %s" % params)
        else:
            logger.info("Logged in to Qobuz")

        if not resp["user"]["credential"]["parameters"]:
            raise IneligibleError("Free accounts are not eligible to download tracks.")

        self.uat = resp["user_auth_token"]
        self.session.headers.update({"X-User-Auth-Token": self.uat})
        self.label = resp["user"]["credential"]["parameters"]["short_label"]

    def _api_get_file_url(self, track_id, quality=6, sec=None):
        unix_ts = time.time()

        if int(quality) not in (5, 6, 7, 27):  # Needed?
            raise InvalidQuality(f"Invalid quality id {quality}. Choose 5, 6, 7 or 27")

        secret = sec or self.sec
        r_sig = f"trackgetFileUrlformat_id{quality}intentstreamtrack_id{track_id}{unix_ts}{secret}"
        logger.debug("Raw request signature: %s", r_sig)
        r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
        logger.debug("Hashed request signature: %s", r_sig_hashed)

        params = {
            "request_ts": unix_ts,
            "request_sig": r_sig_hashed,
            "track_id": track_id,
            "format_id": quality,
            "intent": "stream",
        }
        response, status_code = self._api_request("track/getFileUrl", params)
        if status_code == 400:
            raise InvalidAppSecretError("Invalid app secret from params %s" % params)
        return response

    def _api_request(self, epoint, params) -> Tuple[dict, int]:
        logging.debug(f"Calling API with endpoint {epoint} params {params}")
        r = self.session.get(f"{QOBUZ_BASE}/{epoint}", params=params)
        r.raise_for_status()
        return r.json(), r.status_code

    def _test_secret(self, secret) -> bool:
        try:
            self._api_get_file_url("19512574", sec=secret)
            return True
        except InvalidAppSecretError as error:
            logger.debug("Test for %s secret didn't work: %s", secret, error)
            return False


class DeezerClient(ClientInterface):
    def __init__(self):
        self.session = requests.Session()

    def search(self, query: str, media_type: str = "album", limit: int = 200):
        """Search API for query.

        :param query:
        :type query: str
        :param media_type:
        :type media_type: str
        :param limit:
        :type limit: int
        """
        # TODO: more robust url sanitize
        query = query.replace(" ", "+")

        if media_type.endswith("s"):
            media_type = media_type[:-1]

        # TODO: use limit parameter
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
