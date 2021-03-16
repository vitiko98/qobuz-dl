import appdirs
import mutagen.id3 as id3

APPNAME = "qobuz-dl"

CACHE_DIR = appdirs.user_cache_dir(APPNAME)
CONFIG_DIR = appdirs.user_config_dir(APPNAME)
LOG_DIR = appdirs.user_config_dir(APPNAME)


AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0"

TIDAL_COVER_URL = "https://resources.tidal.com/images/{uuid}/{width}x{height}.jpg"

EXT = {
    5: ".mp3",
    6: ".flac",
    7: ".flac",
    27: ".flac",
}

QUALITY_DESC = {
    4: "128kbps",
    5: "320kbps",
    6: "16bit/44.1kHz",
    7: "24bit/96kHz",
    27: "24bit/192kHz",
}


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
    "harmonia-mundi",
    "universal-classic",
    "universal-jazz",
    "universal-jeunesse",
    "universal-chanson",
]

__MP4_KEYS = [
    "\xa9nam",
    "\xa9ART",
    "\xa9alb",
    r"aART",
    "\xa9day",
    "\xa9day",
    "\xa9cmt",
    "desc",
    "purd",
    "\xa9grp",
    "\xa9gen",
    "\xa9lyr",
    "\xa9too",
    "cprt",
    "cpil",
    "covr",
    "trkn",
    "disk",
]

__MP3_KEYS = [
    id3.TIT2,
    id3.TPE1,
    id3.TALB,
    id3.TPE2,
    id3.TCOM,
    id3.TYER,
    id3.COMM,
    id3.TT1,
    id3.TT1,
    id3.GP1,
    id3.TCON,
    id3.USLT,
    id3.TEN,
    id3.TCOP,
    id3.TCMP,
    None,
    id3.TRCK,
    id3.TPOS,
]

__METADATA_TYPES = [
    "title",
    "artist",
    "album",
    "albumartist",
    "composer",
    "year",
    "comment",
    "description",
    "purchase_date",
    "grouping",
    "genre",
    "lyrics",
    "encoder",
    "copyright",
    "compilation",
    "cover",
    "tracknumber",
    "discnumber",
]


FLAC_KEY = {v: v.upper() for v in __METADATA_TYPES}
MP4_KEY = dict(zip(__METADATA_TYPES, __MP4_KEYS))
MP3_KEY = dict(zip(__METADATA_TYPES, __MP3_KEYS))

COPYRIGHT = "\u2117"
PHON_COPYRIGHT = "\u00a9"
FLAC_MAX_BLOCKSIZE = 16777215  # 16.7 MB
FORMATTER_KEYS = ("title", "album", "albumartist", "artist", "year", "tracknumber")

QOBUZ_URL_REGEX = (
    r"(?:https:\/\/(?:w{3}|open|play)\.qobuz\.com)?"
    r"(?:\/[a-z]{2}-[a-z]{2})?\/(album|artist|track|playlist|label)(?:"
    r"\/[-\w\d]+)?\/([\w\d]+)"
)
