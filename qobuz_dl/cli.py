import base64
import configparser
import logging
import os
import sys

import qobuz_dl.spoofbuz as spoofbuz
from qobuz_dl.color import CYAN, DF, GREEN, RED, YELLOW
from qobuz_dl.commands import qobuz_dl_args
from qobuz_dl.core import QobuzDL

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)

if os.name == "nt":
    OS_CONFIG = os.environ.get("APPDATA")
else:
    OS_CONFIG = os.path.join(os.environ["HOME"], ".config")

CONFIG_PATH = os.path.join(OS_CONFIG, "qobuz-dl")
CONFIG_FILE = os.path.join(CONFIG_PATH, "config.ini")


def reset_config(config_file):
    logging.info(f"{YELLOW}Creating config file: {config_file}")
    config = configparser.ConfigParser()
    config["DEFAULT"]["email"] = input(f"{CYAN}Enter your email:\n-{DF} ")
    config["DEFAULT"]["password"] = base64.b64encode(
        input(f"{CYAN}Enter your password\n-{DF} ").encode()
    ).decode()
    config["DEFAULT"]["default_folder"] = (
        input(
            f"{CYAN}Folder for downloads (leave empy for default 'Qobuz Downloads')\n-{DF} "
        )
        or "Qobuz Downloads"
    )
    config["DEFAULT"]["default_quality"] = (
        input(
            f"{CYAN}Download quality (5, 6, 7, 27) "
            "[320, LOSSLESS, 24B <96KHZ, 24B >96KHZ]"
            f"\n(leave empy for default '6')\n-{DF} "
        )
        or "6"
    )
    config["DEFAULT"]["default_limit"] = "20"
    config["DEFAULT"]["no_m3u"] = "false"
    config["DEFAULT"]["albums_only"] = "false"
    config["DEFAULT"]["no_fallback"] = "false"
    config["DEFAULT"]["og_cover"] = "false"
    config["DEFAULT"]["embed_art"] = "false"
    config["DEFAULT"]["no_cover"] = "false"
    logging.info(f"{YELLOW}Getting tokens. Please wait...")
    spoofer = spoofbuz.Spoofer()
    config["DEFAULT"]["app_id"] = str(spoofer.getAppId())
    config["DEFAULT"]["secrets"] = ",".join(spoofer.getSecrets().values())
    with open(config_file, "w") as configfile:
        config.write(configfile)
    logging.info(
        f"{GREEN}Config file updated. Edit more options in {config_file}"
        "\nso you don't have to call custom flags every time you run "
        "a qobuz-dl command."
    )


def main():
    if not os.path.isdir(CONFIG_PATH) or not os.path.isfile(CONFIG_FILE):
        os.makedirs(CONFIG_PATH, exist_ok=True)
        reset_config(CONFIG_FILE)

    if len(sys.argv) < 2:
        sys.exit(qobuz_dl_args().print_help())

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    try:
        email = config["DEFAULT"]["email"]
        password = base64.b64decode(config["DEFAULT"]["password"]).decode()
        default_folder = config["DEFAULT"]["default_folder"]
        default_limit = config["DEFAULT"]["default_limit"]
        default_quality = config["DEFAULT"]["default_quality"]
        no_m3u = config["DEFAULT"]["no_m3u"]
        albums_only = config["DEFAULT"]["albums_only"]
        no_fallback = config["DEFAULT"]["no_fallback"]
        og_cover = config["DEFAULT"]["og_cover"]
        embed_art = config["DEFAULT"]["embed_art"]
        no_cover = config["DEFAULT"]["no_cover"]
        app_id = config["DEFAULT"]["app_id"]
        secrets = [
            secret for secret in config["DEFAULT"]["secrets"].split(",") if secret
        ]
        arguments = qobuz_dl_args(
            default_quality, default_limit, default_folder
        ).parse_args()
    except (KeyError, UnicodeDecodeError, configparser.Error):
        arguments = qobuz_dl_args().parse_args()
        if not arguments.reset:
            sys.exit(
                f"{RED}Your config file is corrupted! Run 'qobuz-dl -r' to fix this"
            )
    if arguments.reset:
        sys.exit(reset_config(CONFIG_FILE))

    qobuz = QobuzDL(
        arguments.directory,
        arguments.quality,
        arguments.embed_art or embed_art,
        ignore_singles_eps=arguments.albums_only or albums_only,
        no_m3u_for_playlists=arguments.no_m3u or no_m3u,
        quality_fallback=not arguments.no_fallback or not no_fallback,
        cover_og_quality=arguments.og_cover or og_cover,
        no_cover=arguments.no_cover or no_cover,
    )

    qobuz.initialize_client(email, password, app_id, secrets)

    try:
        if arguments.command == "dl":
            qobuz.download_list_of_urls(arguments.SOURCE)
        elif arguments.command == "lucky":
            query = " ".join(arguments.QUERY)
            qobuz.lucky_type = arguments.type
            qobuz.lucky_limit = arguments.number
            qobuz.lucky_mode(query)
        else:
            qobuz.interactive_limit = arguments.limit
            qobuz.interactive()
    except KeyboardInterrupt:
        logging.info(
            f"{RED}Interrupted by user\n{YELLOW}Already downloaded items will "
            "be skipped if you try to download the same releases again"
        )


if __name__ == "__main__":
    sys.exit(main())
