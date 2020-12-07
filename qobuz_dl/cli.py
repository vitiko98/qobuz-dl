import argparse
import configparser
import os
import re
import sys

from pick import pick

import qobuz_dl.spoofbuz as spoofbuz
from qobuz_dl import downloader, qopy
from qobuz_dl.search import Search

if os.name == "nt":
    OS_CONFIG = os.environ.get("APPDATA")
else:
    OS_CONFIG = os.path.join(os.environ["HOME"], ".config")

CONFIG_PATH = os.path.join(OS_CONFIG, "qobuz-dl")
CONFIG_FILE = os.path.join(CONFIG_PATH, "config.ini")


def reset_config(config_file):
    print("Creating config file: " + config_file)
    config = configparser.ConfigParser()
    config["DEFAULT"]["email"] = input("\nEnter your email:\n- ")
    config["DEFAULT"]["password"] = input("\nEnter your password\n- ")
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


def getArgs(default_quality=6, default_limit=10, default_folder="Qobuz Downloads"):
    parser = argparse.ArgumentParser(prog="qobuz-dl")
    parser.add_argument("-a", action="store_true", help="enable albums-only search")
    parser.add_argument("-r", action="store_true", help="create/reset config file")
    parser.add_argument(
        "-i",
        metavar="album/track/artist/label/playlist URL",
        help="run qobuz-dl on URL input mode (download by url)",
    )
    parser.add_argument(
        "-q",
        metavar="int",
        default=default_quality,
        help="quality for url input mode (5, 6, 7, 27) (default: 6)",
    )
    parser.add_argument(
        "-l",
        metavar="int",
        default=default_limit,
        help="limit of search results by type (default: 10)",
    )
    parser.add_argument(
        "-d",
        metavar="PATH",
        default=default_folder,
        help="custom directory for downloads (default: '{}')".format(default_folder),
    )
    return parser.parse_args()


def musicDir(dir):
    fix = os.path.normpath(dir)
    if not os.path.isdir(fix):
        os.mkdir(fix)
    return fix


def get_id(url):
    return re.match(
        r"https?://(?:w{0,3}|play|open)\.qobuz\.com/(?:(?:album|track|artist"
        "|playlist|label)/|[a-z]{2}-[a-z]{2}/album/-?\w+(?:-\w+)*-?/|user/library/favorites/)(\w+)",
        url,
    ).group(1)


def processSelected(Qz, path, albums, ids, types, quality):
    q = ["5", "6", "7", "27"]
    quality = q[quality[1]]
    for alb, id_, type_ in zip(albums, ids, types):
        for al in alb:
            downloader.iterateIDs(
                Qz, id_[al[1]], path, quality, True if type_[al[1]] else False
            )


def fromUrl(Qz, id, path, quality, album=True):
    downloader.iterateIDs(Qz, id, path, str(quality), album)


def handle_urls(url, client, path, quality):
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
        print("Downloading {}...".format(url_type))
    except KeyError:
        print("Invalid url. Use urls from https://play.qobuz.com!")
        return
    if type_dict["func"]:
        items = [
            item[type_dict["iterable_key"]]["items"]
            for item in type_dict["func"](item_id)
        ][0]
        for item in items:
            fromUrl(
                client,
                item["id"],
                path,
                quality,
                True if type_dict["iterable_key"] == "albums" else False,
            )
    else:
        fromUrl(client, item_id, path, quality, type_dict["album"])


def interactive(Qz, path, limit, tracks=True):
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
                processSelected(Qz, path, Albums, IDs, Types, quality)
        except KeyboardInterrupt:
            sys.exit("\nBye")


def main():
    if not os.path.isdir(CONFIG_PATH) or not os.path.isfile(CONFIG_FILE):
        try:
            os.mkdir(CONFIG_PATH)
        except FileExistsError:
            pass
        reset_config(CONFIG_FILE)

    email = None
    password = None
    app_id = None
    secrets = None

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    try:
        email = config["DEFAULT"]["email"]
        password = config["DEFAULT"]["password"]
        default_folder = config["DEFAULT"]["default_folder"]
        default_limit = config["DEFAULT"]["default_limit"]
        default_quality = config["DEFAULT"]["default_quality"]
        app_id = config["DEFAULT"]["app_id"]
        secrets = [
            secret for secret in config["DEFAULT"]["secrets"].split(",") if secret
        ]
        arguments = getArgs(default_quality, default_limit, default_folder)
    except KeyError:
        print("Your config file is corrupted! Run 'qobuz-dl -r' to fix this\n")
        arguments = getArgs()

    if arguments.r:
        sys.exit(reset_config(CONFIG_FILE))

    directory = musicDir(arguments.d) + "/"
    Qz = qopy.Client(email, password, app_id, secrets)

    if not arguments.i:
        interactive(Qz, directory, arguments.l, not arguments.a)
    else:
        handle_urls(arguments.i, Qz, directory, arguments.q)


if __name__ == "__main__":
    sys.exit(main())
