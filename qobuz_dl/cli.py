import argparse
import base64
import configparser
import os
import re
import sys

from pick import pick
from pathvalidate import sanitize_filename

import qobuz_dl.spoofbuz as spoofbuz
from qobuz_dl import downloader, qopy
from qobuz_dl.search import Search
from qobuz_dl.commands import qobuz_dl_args

if os.name == "nt":
    OS_CONFIG = os.environ.get("APPDATA")
else:
    OS_CONFIG = os.path.join(os.environ["HOME"], ".config")

CONFIG_PATH = os.path.join(OS_CONFIG, "qobuz-dl")
CONFIG_FILE = os.path.join(CONFIG_PATH, "config.ini")

QUALITIES = {5: "320", 6: "LOSSLESS", 7: "24B <96KHZ", 27: "24B <196KHZ"}


def reset_config(config_file):
    print("Creating config file: " + config_file)
    config = configparser.ConfigParser()
    config["DEFAULT"]["email"] = input("\nEnter your email:\n- ")
    config["DEFAULT"]["password"] = base64.b64encode(
        input("\nEnter your password\n- ").encode()
    ).decode()
    config["DEFAULT"]["default_folder"] = (
        input("\nFolder for downloads (leave empy for default 'Qobuz Downloads')\n- ")
        or "Qobuz Downloads"
    )
    config["DEFAULT"]["default_quality"] = (
        input(
            "\nDownload quality (5, 6, 7, 27) "
            "[320, LOSSLESS, 24B <96KHZ, 24B >96KHZ]"
            "\n(leave empy for default '6')\n- "
        )
        or "6"
    )
    config["DEFAULT"]["default_limit"] = "10"
    print("Getting tokens. Please wait...")
    spoofer = spoofbuz.Spoofer()
    config["DEFAULT"]["app_id"] = str(spoofer.getAppId())
    config["DEFAULT"]["secrets"] = ",".join(spoofer.getSecrets().values())
    with open(config_file, "w") as configfile:
        config.write(configfile)
    print("Config file updated.")


def musicDir(directory):
    fix = os.path.normpath(directory)
    if not os.path.isdir(fix):
        print("New directory created: " + fix)
        os.makedirs(fix, exist_ok=True)
    return fix


def get_id(url):
    return re.match(
        r"https?://(?:w{0,3}|play|open)\.qobuz\.com/(?:(?:album|track|artist"
        "|playlist|label)/|[a-z]{2}-[a-z]{2}/album/-?\w+(?:-\w+)*-?/|user/library/favorites/)(\w+)",
        url,
    ).group(1)


def processSelected(Qz, path, albums, ids, types, quality, embed_art=False):
    quality = [i for i in QUALITIES.keys()][quality[1]]
    for alb, id_, type_ in zip(albums, ids, types):
        for al in alb:
            downloader.download_id_by_type(
                Qz,
                id_[al[1]],
                path,
                quality,
                True if type_[al[1]] else False,
                embed_art,
            )


def fromUrl(Qz, id, path, quality, album=True, embed_art=False):
    downloader.download_id_by_type(Qz, id, path, str(quality), album, embed_art)


def handle_urls(url, client, path, quality, embed_art=False):
    possibles = {
        "playlist": {"func": client.get_plist_meta, "iterable_key": "tracks"},
        "artist": {"func": client.get_artist_meta, "iterable_key": "albums"},
        "label": {"func": client.get_label_meta, "iterable_key": "albums"},
        "album": {"album": True, "func": None, "iterable_key": None},
        "track": {"album": False, "func": None, "iterable_key": None},
    }
    try:
        url_type = url.split("/")[3]
        type_dict = possibles[url_type]
        item_id = get_id(url)
    except (KeyError, IndexError):
        print('Invalid url: "{}". Use urls from https://play.qobuz.com!'.format(url))
        return
    if type_dict["func"]:
        content = [item for item in type_dict["func"](item_id)]
        content_name = content[0]["name"]
        print(
            "\nDownloading all the music from {} ({})!".format(content_name, url_type)
        )
        new_path = musicDir(os.path.join(path, sanitize_filename(content_name)))
        items = [item[type_dict["iterable_key"]]["items"] for item in content][0]
        for item in items:
            fromUrl(
                client,
                item["id"],
                new_path,
                quality,
                True if type_dict["iterable_key"] == "albums" else False,
                embed_art,
            )
    else:
        fromUrl(client, item_id, path, quality, type_dict["album"], embed_art)


def interactive(Qz, path, limit, tracks=True, embed_art=False):
    while True:
        Albums, Types, IDs = [], [], []
        try:
            while True:
                query = input("\nEnter your search: [Ctrl + c to quit]\n- ")
                print("Searching...")
                if len(query.strip()) == 0:
                    break
                start = Search(Qz, query, limit)
                start.getResults(tracks)
                if len(start.Total) == 0:
                    break
                Types.append(start.Types)
                IDs.append(start.IDs)

                title = (
                    "Select [space] the item(s) you want to download "
                    "(zero or more)\nPress Ctrl + c to quit\n"
                )
                Selected = pick(
                    start.Total, title, multiselect=True, min_selection_count=0
                )
                if len(Selected) > 0:
                    Albums.append(Selected)

                    y_n = pick(
                        ["Yes", "No"],
                        "Items were added to queue to be downloaded. Keep searching?",
                    )
                    if y_n[0][0] == "N":
                        break
                else:
                    break

            if len(Albums) > 0:
                desc = (
                    "Select [intro] the quality (the quality will be automat"
                    "ically\ndowngraded if the selected is not found)"
                )
                Qualits = ["320", "Lossless", "Hi-res =< 96kHz", "Hi-Res > 96 kHz"]
                quality = pick(Qualits, desc, default_index=1)
                processSelected(Qz, path, Albums, IDs, Types, quality, embed_art)
        except KeyboardInterrupt:
            sys.exit("\nBye")


def download_by_txt_file(Qz, txt_file, path, quality, embed_art=False):
    with open(txt_file, "r") as txt:
        try:
            urls = txt.read().strip().split()
        except Exception as e:
            print("Invalid text file: " + str(e))
            return
        print(
            'qobuz-dl will download {} urls from file: "{}"\n'.format(
                len(urls), txt_file
            )
        )
        for url in urls:
            handle_urls(url, Qz, path, quality, embed_art)


def download_lucky_mode(Qz, mode, query, limit, path, quality, embed_art=False):
    if len(query) < 3:
        sys.exit("Your search query is too short or invalid!")

    print(
        'Searching {}s for "{}".\n'
        "qobuz-dl will attempt to download the first {} results.".format(
            mode, query, limit
        )
    )

    WEB_URL = "https://play.qobuz.com/"
    possibles = {
        "album": {
            "func": Qz.search_albums,
            "album": True,
            "key": "albums",
        },
        "artist": {
            "func": Qz.search_artists,
            "album": True,
            "key": "artists",
        },
        "track": {
            "func": Qz.search_tracks,
            "album": False,
            "key": "tracks",
        },
        "playlist": {
            "func": Qz.search_playlists,
            "album": False,
            "key": "playlists",
        },
    }

    try:
        mode_dict = possibles[mode]
        results = mode_dict["func"](query, limit)
        iterable = results[mode_dict["key"]]["items"]
        # Use handle_urls as everything is already handled there :p
        urls = ["{}{}/{}".format(WEB_URL, mode, i["id"]) for i in iterable]
        print("Found {} results!".format(len(urls)))
        for url in urls:
            handle_urls(url, Qz, path, quality, embed_art)
    except (KeyError, IndexError):
        sys.exit("Invalid mode: " + str(mode))


def main():
    if not os.path.isdir(CONFIG_PATH) or not os.path.isfile(CONFIG_FILE):
        try:
            os.makedirs(CONFIG_PATH, exist_ok=True)
        except FileExistsError:
            pass
        reset_config(CONFIG_FILE)

    if len(sys.argv) < 2:
        sys.exit(qobuz_dl_args().print_help())

    email = None
    password = None
    app_id = None
    secrets = None

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    try:
        email = config["DEFAULT"]["email"]
        password = base64.b64decode(config["DEFAULT"]["password"]).decode()
        default_folder = config["DEFAULT"]["default_folder"]
        default_limit = config["DEFAULT"]["default_limit"]
        default_quality = config["DEFAULT"]["default_quality"]
        app_id = config["DEFAULT"]["app_id"]
        secrets = [
            secret for secret in config["DEFAULT"]["secrets"].split(",") if secret
        ]
        arguments = qobuz_dl_args(
            default_quality, default_limit, default_folder
        ).parse_args()
    except (KeyError, UnicodeDecodeError):
        arguments = qobuz_dl_args().parse_args()
        if not arguments.reset:
            print("Your config file is corrupted! Run 'qobuz-dl -r' to fix this\n")
    if arguments.reset:
        sys.exit(reset_config(CONFIG_FILE))

    directory = musicDir(arguments.directory)

    Qz = qopy.Client(email, password, app_id, secrets)

    try:
        quality_str = QUALITIES[int(arguments.quality)]
        print("Quality set: " + quality_str)
    except KeyError:
        sys.exit("Invalid quality!")

    if arguments.command == "fun":
        sys.exit(
            interactive(
                Qz,
                directory,
                arguments.limit,
                not arguments.albums_only,
                arguments.embed_art,
            )
        )
    if arguments.command == "dl":
        for url in arguments.SOURCE:
            if os.path.isfile(url):
                download_by_txt_file(
                    Qz, url, directory, arguments.quality, arguments.embed_art
                )
            else:
                handle_urls(url, Qz, directory, arguments.quality, arguments.embed_art)
    else:
        download_lucky_mode(
            Qz,
            arguments.type,
            " ".join(arguments.QUERY),
            arguments.number,
            directory,
            arguments.quality,
            arguments.embed_art,
        )


if __name__ == "__main__":
    sys.exit(main())
