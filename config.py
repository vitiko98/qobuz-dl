import os
from dotenv import load_dotenv
load_dotenv()
# Qobuz credentials (Don't remove the quotes!)
email = os.getenv('QOBUZ_EMAIL')
password = os.getenv('QOBUZ_PW')

# Default folder where the releases are downloaded
default_folder = os.getenv('QOBUZ_FOLDER', "Qobuz Downloads")

# Default per type results limit
default_limit = os.getenv('QOBUZ_LIMIT', 10)

# Default quality for url input mode. This will be ignored in interactive mode
# (5, 6, 7, 27) [320, LOSSLESS, 24B <96KHZ, 24B >96KHZ]
default_quality = os.getenv('QOBUZ_QUALITY', 6)
