import os
import requests
from qo_utils import metadata
from tqdm import tqdm


def req_tqdm(url, fname, track_name):
    r = requests.get(url, allow_redirects=True, stream=True)
    total = int(r.headers.get('content-length', 0))
    with open(fname, 'wb') as file, tqdm(
        total=total,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
        desc=track_name,
        bar_format='{n_fmt}/{total_fmt} /// {desc}',
    ) as bar:
        for data in r.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)


def mkDir(dirn):
    try:
        os.mkdir(dirn)
    except FileExistsError:
        print('Warning: folder already exists. Overwriting...')


def getDesc(u, mt):
    return '{} [{}/{}]'.format(mt['title'], u['bit_depth'], u['sampling_rate'])


def getCover(i, dirn, id):
    # req_tqdm(i, dirn + f'/{id}.jpg', 'Downloading cover art')
    req_tqdm(i, dirn + '/cover.jpg', 'Downloading cover art')


# Download and tag a file
def downloadItem(dirn, count, parse, meta, album, url, type, mp3, *arg):
    if mp3:
        fname = '{}/{:02}.mp3'.format(dirn, count)
        func = metadata.tag_mp3
    else:
        fname = '{}/{:02}.flac'.format(dirn, count)
        func = metadata.tag_flac
    desc = getDesc(parse, meta)
    req_tqdm(url, fname, desc)
    func(fname, dirn, meta, album, type, arg[0])


# Iterate over IDs by type calling downloadItem
def iterateIDs(client, id, path, quality, type='track'):
    count = 0

    if type=='album':
        meta = client.get_album_meta(id)
        print('\nDownloading: {}\n'.format(meta['title']))
        dirT = (meta['artist']['name'],
                meta['title'],
                meta['release_date_original'].split('-')[0])
        dirn = path + '{} - {} [{}]'.format(*dirT)
        mkDir(dirn)
        
        for i in meta['tracks']['items']:
            parse = client.get_track_url(i['id'], quality)
            url = parse['url']

            if 'sample' not in parse:
                if int(quality) == 5:
                    downloadItem(dirn, count, parse, i, meta, url, "album", True)
                else:
                    downloadItem(dirn, count, parse, i, meta, url, "album", False)
            else:
                print('Demo. Skipping')

            count = count + 1
    
    elif type=='playlist':
        meta = client.get_playlist_meta(id)
        print('\nDownloading: {}\n'.format(meta['name']))
        dirn = path + '{}'.format(meta['name'])
        mkDir(dirn)
        for i in meta['tracks']['items']:
            getCover(i['album']['image']['large'], dirn, i['album']['id'])
            parse = client.get_track_url(i['id'], quality,)
            url = parse['url']

            if 'sample' not in parse:
                if int(quality) == 5:
                    downloadItem(dirn, count, parse, i, meta, url, "playlist", True, count)
                else:
                    downloadItem(dirn, count, parse, i, meta, url, "playlist", False, count)
            else:
                print('Demo. Skipping')

            count = count + 1

    elif type=='track':
        parse = client.get_track_url(id, quality)
        url = parse['url']

        if 'sample' not in parse:
            meta = client.get_track_meta(id)
            print('\nDownloading: {}\n'.format(meta['title']))
            dirT = (meta['album']['artist']['name'],
                    meta['title'],
                    meta['album']['release_date_original'].split('-')[0])
            dirn = path + '{} - {} [{}]'.format(*dirT)
            mkDir(dirn)
            getCover(meta['album']['image']['large'], dirn, meta['id'])
            if int(quality) == 5:
                downloadItem(dirn, count, parse, meta, meta, url, "track", True)
            else:
                downloadItem(dirn, count, parse, meta, meta, url, "track", False)
        else:
            print('Demo. Skipping')

    print('\nCompleted\n')
