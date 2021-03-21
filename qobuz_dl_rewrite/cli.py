# For tests

import click
import os
import logging
from qobuz_dl_rewrite.config import Config
from qobuz_dl_rewrite.utils import init_log
from qobuz_dl_rewrite.core import QobuzDL

logger = logging.getLogger(__name__)


def _get_config(ctx):
    config = Config(ctx.obj.get("config"))
    config.load()
    config.update_from_cli(**ctx.obj)
    return config


# fmt: off
@click.group()
@click.option("--disable", metavar="PROVIDER,...", help="Disable following providers (comma separated)")
@click.option("-q","--quality",metavar="QUALITY",help="Quality integer ID (5, 6, 7, 27)")
@click.option("--embed-cover", is_flag=True, help="Embed cover art into files")
@click.option("--no-extras", is_flag=True, help="Ignore extras")
@click.option("--no-features", is_flag=True, help="Ignore features")
@click.option("--studio-albums", is_flag=True, help="Ignore non-studio albums")
@click.option("--remaster-only", is_flag=True, help="Ignore non-remastered albums")
@click.option("--albums-only", is_flag=True, help="Ignore non-album downloads")
@click.option("--large-cover", is_flag=True, help="Download large covers (it might fail with embed)")
@click.option("--remove-extra-tags", default=False, is_flag=True, help="Remove extra metadata from tags and files")
@click.option("--debug", default=False, is_flag=True, help="Enable debug logging")
@click.option("-f", "--folder", metavar="PATH", help="Custom download folder")
@click.option("--default-comment", metavar="COMMENT", help="Custom comment tag for audio files")
@click.option("-c", "--config", metavar="FILE", help="Custom config file")
@click.option("--db-file", metavar="FILE", help="Custom database file")
@click.option("--log-file", metavar="FILE", help="Custom logfile")
@click.option("--flush-cache", metavar="FILE", help="Flush the cache before running (only for extreme cases)")
@click.pass_context
# fmt: on
def cli(ctx, **kwargs):
    ctx.ensure_object(dict)

    for key in kwargs.keys():
        ctx.obj[key] = kwargs.get(key)

    if ctx.obj["debug"]:
        init_log(path=ctx.obj.get("log_file"))
    else:
        click.secho("Debug is not enabled", fg="yellow")


@click.command(name="dl")
@click.argument("items", nargs=-1)
@click.pass_context
def download(ctx, items):
    """
    Download an URL, space separated URLs or a text file with URLs.
    Mixed arguments are also supported.

    Examples:

        * `qobuz-dl dl https://some.url/some_type/some_id`

        * `qobuz-dl dl file_with_urls.txt`

        * `qobuz-dl dl URL URL URL`

    Supported sources and their types:

        * Deezer (album, artist, track, playlist)

        * Qobuz (album, artist, label, track, playlist)

        * Tidal (album, artist, track, playlist)
    """
    config = _get_config(ctx)
    core = QobuzDL(config)
    core.load_creds()
    for item in items:
        try:
            if os.path.isfile(item):
                core.from_txt(item)
                click.secho(f"File input found: {item}", fg="yellow")
            else:
                core.handle_url(item)
        except Exception as error:
            logger.error(error, exc_info=True)
            click.secho(
                f"{type(error).__name__} raised processing {item}: {error}", fg="red"
            )


if __name__ == "__main__":
    cli.add_command(download)
    cli(obj={})
