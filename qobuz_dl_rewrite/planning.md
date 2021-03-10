# Qobuz-dl rewrite planning



## API

### Track

> handles downloading and tagging of tracks

Public methods:

- download
- tag
- classmethod `from_album_meta`



### Album(Tracklist)

`__init__(self, id, client)`

> qobuz album

Public methods:

- download

- tag

  

### TrackMetadata

- parses metadata





## Internals

**New features:**

- Tidal support





## Clients

### ClientInterface

> base class that contains all of the basic methods

- `search(query, type)`
- `get_file_url()`
- `get_metadata(id, type)`



### SecureClientInterface(ClientInterface)

> for clients that need authentication

- `login(email, pwd, *secrets)`



### QobuzClient(SecureClientInterface)

> implement for qobuz

### TidalClient(SecureClientInterface)

> implement for tidal

### DeezerClient(ClientInterface)

> repurpose from deezrip



### Ideal Usage of clients

```python
from clients import QobuzClient, TidalClient, DeezerClient
from secrets import secrets
# this code should be able to run
for i, client in enumerate((QobuzClient, TidalClient, DeezerClient)):
    client.login(secrets[i])
    res = client.search('fleetwood mac rumours')
    res[0].download(quality=(24, 48))

```

