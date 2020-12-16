import base64
import configparser
import os
import sys

import qobuz_dl.spoofbuz as spoofbuz
from qobuz_dl.core import QobuzDL
from qobuz_dl.commands import qobuz_dl_args

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
    config["DEFAULT"]["default_limit"] = "20"
    print("Getting tokens. Please wait...")
    spoofer = spoofbuz.Spoofer()
    config["DEFAULT"]["app_id"] = str(spoofer.getAppId())
    config["DEFAULT"]["secrets"] = ",".join(spoofer.getSecrets().values())
    with open(config_file, "w") as configfile:
        config.write(configfile)
    print("Config file updated.")


def main():
    if not os.path.isdir(CONFIG_PATH) or not os.path.isfile(CONFIG_FILE):
        os.makedirs(CONFIG_PATH, exist_ok=True)
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

    qobuz = QobuzDL(
        arguments.directory,
        arguments.quality,
        arguments.embed_art,
        ignore_singles_eps=arguments.albums_only,
        no_m3u_for_playlists=arguments.no_m3u,
        quality_fallback=not arguments.no_fallback,
    )
    qobuz.initialize_client(email, password, app_id, secrets)

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


if __name__ == "__main__":
    sys.exit(main())
