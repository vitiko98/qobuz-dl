import logging
import os

import requests
from pathvalidate import sanitize_filename
from tqdm import tqdm

import qobuz_dl.metadata as metadata
from qobuz_dl.color import OFF, GREEN, RED, YELLOW, CYAN
from qobuz_dl.exceptions import NonStreamable

QL_DOWNGRADE = "FormatRestrictedByFormatAvailability"
logger = logging.getLogger(__name__)


def tqdm_download(url, fname, track_name):
    r = requests.get(url, allow_redirects=True, stream=True)
    total = int(r.headers.get("content-length", 0))
    with open(fname, "wb") as file, tqdm(
        total=total,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
        desc=track_name,
        bar_format=CYAN + "{n_fmt}/{total_fmt} /// {desc}",
    ) as bar:
        for data in r.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)


def get_description(u: dict, track_title, multiple=None):
    downloading_title = f'{track_title} [{u["bit_depth"]}/{u["sampling_rate"]}]'
    if multiple:
        downloading_title = f"[Disc {multiple}] {downloading_title}"
    return downloading_title


def get_format(client, item_dict, quality, is_track_id=False, track_url_dict=None):
    quality_met = True
    if int(quality) == 5:
        return "MP3", quality_met
    track_dict = item_dict
    if not is_track_id:
        track_dict = item_dict["tracks"]["items"][0]

    try:
        new_track_dict = (
            client.get_track_url(track_dict["id"], quality)
            if not track_url_dict
            else track_url_dict
        )
        restrictions = new_track_dict.get("restrictions")
        if isinstance(restrictions, list):
            if any(
                restriction.get("code") == QL_DOWNGRADE for restriction in restrictions
            ):
                quality_met = False
        if (
            new_track_dict["bit_depth"] == 16
            and new_track_dict["sampling_rate"] == 44.1
        ):
            return "FLAC", quality_met
        return (
            f'{new_track_dict["bit_depth"]}B-{new_track_dict["sampling_rate"]}Khz',
            quality_met,
        )
    except (KeyError, requests.exceptions.HTTPError):
        return "Unknown", quality_met


def get_title(item_dict):
    album_title = item_dict["title"]
    version = item_dict.get("version")
    if version:
        album_title = (
            f"{album_title} ({version})"
            if version.lower() not in album_title.lower()
            else album_title
        )
    return album_title


def get_extra(i, dirn, extra="cover.jpg", og_quality=False):
    extra_file = os.path.join(dirn, extra)
    if os.path.isfile(extra_file):
        logger.info(f"{OFF}{extra} was already downloaded")
        return
    tqdm_download(
        i.replace("_600.", "_org.") if og_quality else i,
        extra_file,
        extra,
    )


# Download and tag a file
def download_and_tag(
    root_dir,
    tmp_count,
    track_url_dict,
    track_metadata,
    album_or_track_metadata,
    is_track,
    is_mp3,
    embed_art=False,
    multiple=None,
):
    """
    Download and tag a file

    :param str root_dir: Root directory where the track will be stored
    :param int tmp_count: Temporal download file number
    :param dict track_url_dict: get_track_url dictionary from Qobuz client
    :param dict track_metadata: Track item dictionary from Qobuz client
    :param dict album_or_track_metadata: Album/track dictionary from Qobuz client
    :param bool is_track
    :param bool is_mp3
    :param bool embed_art: Embed cover art into file (FLAC-only)
    :param multiple: Multiple disc integer
    :type multiple: integer or None
    """
    extension = ".mp3" if is_mp3 else ".flac"

    try:
        url = track_url_dict["url"]
    except KeyError:
        logger.info(f"{OFF}Track not available for download")
        return

    if multiple:
        root_dir = os.path.join(root_dir, f"Disc {multiple}")
        os.makedirs(root_dir, exist_ok=True)

    filename = os.path.join(root_dir, f".{tmp_count:02}.tmp")

    # Determine the filename
    artist = track_metadata.get("performer", {}).get("name")
    album_artist = track_metadata.get("album", {}).get("artist", {}).get("name")
    new_track_title = track_metadata.get("title")
    version = track_metadata.get("version")

    if artist or album_artist:
        new_track_title = (
            f"{artist if artist else album_artist}" f' - {track_metadata["title"]}'
        )
    if version:
        new_track_title = f"{new_track_title} ({version})"

    track_file = f'{track_metadata["track_number"]:02}. {new_track_title}'
    final_file = os.path.join(root_dir, sanitize_filename(track_file))[:250] + extension

    if os.path.isfile(final_file):
        logger.info(f"{OFF}{new_track_title} was already downloaded")
        return

    desc = get_description(track_url_dict, new_track_title, multiple)
    tqdm_download(url, filename, desc)
    tag_function = metadata.tag_mp3 if is_mp3 else metadata.tag_flac
    try:
        tag_function(
            filename,
            root_dir,
            final_file,
            track_metadata,
            album_or_track_metadata,
            is_track,
            embed_art,
        )
    except Exception as e:
        logger.error(f"{RED}Error tagging the file: {e}", exc_info=True)


def download_id_by_type(
    client,
    item_id,
    path,
    quality,
    album=False,
    embed_art=False,
    albums_only=False,
    downgrade_quality=True,
    cover_og_quality=False,
    no_cover=False,
):
    """
    Download and get metadata by ID and type (album or track)

    :param Qopy client: qopy Client
    :param int item_id: Qobuz item id
    :param str path: The root directory where the item will be downloaded
    :param int quality: Audio quality (5, 6, 7, 27)
    :param bool album: album type or not
    :param embed_art album: Embed cover art into files
    :param bool albums_only: Ignore Singles, EPs and VA releases
    :param bool downgrade: Skip releases not available in set quality
    :param bool cover_og_quality: Download cover in its original quality
    :param bool no_cover: Don't download cover art
    """
    count = 0

    if album:
        meta = client.get_album_meta(item_id)

        if not meta.get("streamable"):
            raise NonStreamable("This release is not streamable")

        if albums_only and (
            meta.get("release_type") != "album"
            or meta.get("artist").get("name") == "Various Artists"
        ):
            logger.info(f'{OFF}Ignoring Single/EP/VA: {meta.get("title", "")}')
            return

        album_title = get_title(meta)
        album_format, quality_met = get_format(client, meta, quality)
        if not downgrade_quality and not quality_met:
            logger.info(
                f"{OFF}Skipping {album_title} as doesn't met quality requirement"
            )
            return

        logger.info(f"\n{YELLOW}Downloading: {album_title}\nQuality: {album_format}\n")
        dirT = (
            meta["artist"]["name"],
            album_title,
            meta["release_date_original"].split("-")[0],
            album_format,
        )
        sanitized_title = sanitize_filename("{} - {} ({}) [{}]".format(*dirT))
        dirn = os.path.join(path, sanitized_title)
        os.makedirs(dirn, exist_ok=True)

        if no_cover:
            logger.info(f"{OFF}Skipping cover")
        else:
            get_extra(meta["image"]["large"], dirn, og_quality=cover_og_quality)

        if "goodies" in meta:
            try:
                get_extra(meta["goodies"][0]["url"], dirn, "booklet.pdf")
            except:  # noqa
                pass
        media_numbers = [track["media_number"] for track in meta["tracks"]["items"]]
        is_multiple = True if len([*{*media_numbers}]) > 1 else False
        for i in meta["tracks"]["items"]:
            parse = client.get_track_url(i["id"], quality)
            if "sample" not in parse and parse["sampling_rate"]:
                is_mp3 = True if int(quality) == 5 else False
                download_and_tag(
                    dirn,
                    count,
                    parse,
                    i,
                    meta,
                    False,
                    is_mp3,
                    embed_art,
                    i["media_number"] if is_multiple else None,
                )
            else:
                logger.info(f"{OFF}Demo. Skipping")
            count = count + 1
    else:
        parse = client.get_track_url(item_id, quality)

        if "sample" not in parse and parse["sampling_rate"]:
            meta = client.get_track_meta(item_id)
            track_title = get_title(meta)
            logger.info(f"\n{YELLOW}Downloading: {track_title}")
            track_format, quality_met = get_format(client, meta, quality, True, parse)
            if not downgrade_quality and not quality_met:
                logger.info(
                    f"{OFF}Skipping {track_title} as doesn't met quality requirement"
                )
                return
            dirT = (
                meta["album"]["artist"]["name"],
                track_title,
                meta["album"]["release_date_original"].split("-")[0],
                track_format,
            )
            sanitized_title = sanitize_filename("{} - {} [{}] [{}]".format(*dirT))
            dirn = os.path.join(path, sanitized_title)
            os.makedirs(dirn, exist_ok=True)
            if no_cover:
                logger.info(f"{OFF}Skipping cover")
            else:
                get_extra(
                    meta["album"]["image"]["large"], dirn, og_quality=cover_og_quality
                )
            is_mp3 = True if int(quality) == 5 else False
            download_and_tag(dirn, count, parse, meta, meta, True, is_mp3, embed_art)
        else:
            logger.info(f"{OFF}Demo. Skipping")
    logger.info(f"{GREEN}Completed")
