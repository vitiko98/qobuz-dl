from requests import get
from sys import argv
from os import mkdir, system
from timeit import default_timer as time
from math import ceil, floor

class Deezrip:
    def __init__(self, download_dir):
        self.init_time = time()
        self.download_dir = download_dir

    def downloadTrack(self, r):
        link = r['link']
        artist = r['artist'].replace('/', '\uff0f')
        title = r['title'].replace('/', '\uff0f')
        path = f'{self.download_dir}/{artist}'
        try:
            mkdir(path)
        except:
            pass

        track_init_time = time()
        download_url = f'http://dz.loaderapp.info/deezer/1411/{link}'
        try:
            size = round(8 * int(get(download_url, stream=True).headers['Content-length']) / 1000000, 2)
        except:
            size = 0

        track_file = get(download_url)
        track_path = f'{path}/{title}'
        time_elapsed = self.formatTime(time() - track_init_time)
        open(track_path, 'wb').write(track_file.content)

        return {'time_elapsed': time_elapsed, 'size': size, 'speed': round(size / time_elapsed, 2)}

    def formatTime(self, time):
        min_elapsed = round(time / 60)
        sec_elapsed = time - min_elapsed * 60
        return sec_elapsed

    def searchAlbum(self, query):

        r = get(f'https://api.deezer.com/search/album?q="{query}"').json()['data']
        results = []
        for i in range(len(r)):
            curr_result = {
                'title':  r[i]['title'],
                'artist': r[i]['artist']['name'],
                'explicit': r[i]['explicit_lyrics'],
                'tracklist':    r[i]['tracklist']
            }
            results.append(curr_result)
        return results

    def searchTrack(self, query):
        url = f'https://api.deezer.com/search?q=track:"{query}"'
        r = get(url).json()['data']
        results = []

        for i in range(len(r)):
            curr_result = {
                'title':  r[i]['title'],
                'artist': r[i]['artist']['name'],
                'explicit': r[i]['explicit_lyrics'],
                'link': r[i]['link']
            }
            results.append(curr_result)
        return results

    def parseTracklist(self, tracklist_url):
        r = get(tracklist_url).json()
        self.total = r['total']
        num_pages = floor(self.total / 25)
        self.pages = [tracklist_url]
        if num_pages > 0:
            for i in range(1, num_pages):
                self.pages.append(f'{tracklist_url}?index={25 * i}')
        return self.pages

    def tracksFromTracklist(self, pages):
        self.tracks = []
        for url in pages:
            tracklist = get(url).json()['data']

            for i in range(len(tracklist)):
                track =  tracklist[i]
                curr_track = {
                    'title': track['title'].replace('/', '\uff0f'),
                    'artist': track['artist']['name'],
                    'link': track['link']
                }
                self.tracks.append(curr_track)
        return self.tracks

    def alac(self, download_dir):
        system(f'zsh /Users/nathan/General/scripts/conver_alac_v2.sh "{download_dir}"')

    def rip(self, query):
        results = self.searchAlbum(query)
        counter = 0
        for item in results:
            if item['explicit']:
                e = '(EXPLICIT)'
            else:
                e = ''
            title, artist = item['title'], item['artist']
            print(f'{counter}. {artist} | {title} {e}')
            counter += 1
        choice = int(input('Which one would you like?\n'))
        choice = results[choice]
        title, artist = choice['title'], choice['artist']
        print(f'Downloading {title} by {artist}')
        p = self.parseTracklist(choice['tracklist'])
        tracks = self.tracksFromTracklist(p)
        path = f'{self.download_dir}/{title}'
        try:
            mkdir(path)
        except:
            pass

        total_size = 0
        for item in tracks:
            track_title = item['title']
            print(f'Downloading {track_title} ({tracks.index(item) + 1}/{len(tracks)})', end=' ')
            print(item['link'])
            stats = self.downloadTrack(item['link'], f'{path}/{track_title}.flac')
            print(str(stats['speed']) + ' Mbps')
            total_size += stats['size']

        self.alac(path)
        total_time = time() - self.init_time
        f_time = formatTime(total_time)
        print(f'Average Speed: {total_size/f_time}')


d = Deezrip('deezer_downloads')
d.rip('fleetwood mac rumours')
