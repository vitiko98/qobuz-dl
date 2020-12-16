import os

import requests
from pathvalidate import sanitize_filename
from tqdm import tqdm

import qobuz_dl.metadata as metadata

QL_DOWNGRADE = "FormatRestrictedByFormatAvailability"


def tqdm_download(url, fname, track_name):
    r = requests.get(url, allow_redirects=True, stream=True)
    total = int(r.headers.get("content-length", 0))
    with open(fname, "wb") as file, tqdm(
        total=total,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
        desc=track_name,
        bar_format="{n_fmt}/{total_fmt} /// {desc}",
    ) as bar:
        for data in r.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)


def get_description(u, mt, multiple=None):
    return "{} [{}/{}]".format(
        ("[Disc {}] {}".format(multiple, mt["title"])) if multiple else mt["title"],
        u["bit_depth"],
        u["sampling_rate"],
    )


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
        return "Hi-Res", quality_met
    except (KeyError, requests.exceptions.HTTPError):
        return "Unknown", quality_met


def get_title(item_dict):
    try:
        album_title = (
            ("{} ({})".format(item_dict["title"], item_dict["version"]))
            if item_dict["version"]
            and item_dict["version"].lower() not in item_dict["title"].lower()
            else item_dict["title"]
        )
    except KeyError:
        album_title = item_dict["title"]
    try:
        final_title = (
            (album_title + " (Explicit)")
            if item_dict["parental_warning"] and "explicit" not in album_title.lower()
            else album_title
        )
    except KeyError:
        final_title = album_title
    return final_title


def get_extra(i, dirn, extra="cover.jpg"):
    extra_file = os.path.join(dirn, extra)
    if os.path.isfile(extra_file):
        print(extra.split(".")[0].title() + " already downloaded")
        return
    tqdm_download(
        i.replace("_600.", "_org."),
        extra_file,
        "Downloading " + extra.split(".")[0],
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
        print("Track not available for download")
        return

    if multiple:
        root_dir = os.path.join(root_dir, "Disc " + str(multiple))
        os.makedirs(root_dir, exist_ok=True)

    filename = os.path.join(root_dir, ".{:02}".format(tmp_count) + extension)

    new_track_title = sanitize_filename(track_metadata["title"])
    track_file = "{:02}. {}{}".format(
        track_metadata["track_number"], new_track_title, extension
    )
    final_file = os.path.join(root_dir, track_file)
    if os.path.isfile(final_file):
        print(track_metadata["title"] + " was already downloaded. Skipping...")
        return

    desc = get_description(track_url_dict, track_metadata, multiple)
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
        print("Error tagging the file: " + str(e))
        os.remove(filename)


def download_id_by_type(
    client,
    item_id,
    path,
    quality,
    album=False,
    embed_art=False,
    albums_only=False,
    downgrade_quality=True,
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
    """
    count = 0

    if album:
        meta = client.get_album_meta(item_id)

        if albums_only and (
            meta.get("release_type") != "album"
            or meta.get("artist").get("name") == "Various Artists"
        ):
            print("Ignoring Single/EP/VA: " + meta.get("title", ""))
            return

        album_title = get_title(meta)
        album_format, quality_met = get_format(client, meta, quality)
        if not downgrade_quality and not quality_met:
            print("Skipping release as doesn't met quality requirement")
            return

        print("\nDownloading: {}\n".format(album_title))
        dirT = (
            meta["artist"]["name"],
            album_title,
            meta["release_date_original"].split("-")[0],
            album_format,
        )
        sanitized_title = sanitize_filename("{} - {} [{}] [{}]".format(*dirT))
        dirn = os.path.join(path, sanitized_title)
        os.makedirs(dirn, exist_ok=True)
        get_extra(meta["image"]["large"], dirn)
        if "goodies" in meta:
            try:
                get_extra(meta["goodies"][0]["url"], dirn, "booklet.pdf")
            except:  # noqa
                pass
        media_numbers = [track["media_number"] for track in meta["tracks"]["items"]]
        is_multiple = True if len([*{*media_numbers}]) > 1 else False
        for i in meta["tracks"]["items"]:
            try:
                parse = client.get_track_url(i["id"], quality)
            except requests.exceptions.HTTPError:
                print("Nothing found")
                continue
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
                print("Demo. Skipping")
            count = count + 1
    else:
        try:
            parse = client.get_track_url(item_id, quality)
        except requests.exceptions.HTTPError:
            print("Nothing found")
            return

        if "sample" not in parse and parse["sampling_rate"]:
            meta = client.get_track_meta(item_id)
            track_title = get_title(meta)
            print("\nDownloading: {}\n".format(track_title))
            track_format, quality_met = get_format(client, meta, quality, True, parse)
            if not downgrade_quality and not quality_met:
                print("Skipping track as doesn't met quality requirement")
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
            get_extra(meta["album"]["image"]["large"], dirn)
            is_mp3 = True if int(quality) == 5 else False
            download_and_tag(dirn, count, parse, meta, meta, True, is_mp3, embed_art)
        else:
            print("Demo. Skipping")
    print("\nCompleted\n")
