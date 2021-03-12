import logging

from qobuz_dl_rewrite.core import QobuzDL

# to use, put urls in qobuz-dl/urls.txt, secrets in qobuz-dl/secrets

logger = logging.basicConfig(level=logging.DEBUG)

album_url = "https://www.qobuz.com/us-en/album/boogie-original-motion-picture-soundtrack-various-artists/v7fp96d7mr5sb"
urls_path = "urls.txt"

qobuz = QobuzDL()
# print(qobuz.from_txt('urls.txt'))
results = qobuz.search("fleetwood mac rumours", "album")
for r in results:
    print(r)
