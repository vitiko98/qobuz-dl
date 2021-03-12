import logging
import sys
from pprint import pprint

from qobuz_dl.cli import main
from qobuz_dl_rewrite.clients import (
    DeezerClient,
    QobuzClient,
    SecureClientInterface,
    TidalClient,
)

qobuz_email, qobuz_pwd = None, None

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

client = QobuzClient()
client.login(qobuz_email, qobuz_pwd)

# searches for albums by default
search_results = client.search('fleetwood mac rumours')
# search_results is a generator of Album objects

search_results = list(search_results)  # convert it to list
print(search_results)

# before downloading and tagging, we can change some of the tags
choice = search_results[0]  # the one we want to download

# right now, `choice` only contains rudimentary data from the search result
# we need to load the rest of it with a new API request

choice.load_meta()  # sends a get album API request and loads the info into the tracks

# now all of the tracks have the necessary metadata
# we can change some of that

first_track = choice[0]  # because Album is subclass of list, this returns the first track
first_track['title'] = 'our custom title'  # when we subscript Track with [], we are accessing its TrackMetadata object
first_track['artist'] = 'not fleetwood mac'

# ------- a bunch of edits later --------


choice.download(quality=6)  # download the Album in CD quality
