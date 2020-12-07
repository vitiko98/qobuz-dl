# qobuz-dl
Seach and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/)

## Features

* Download FLAC and MP3 files from Qobuz
* Search and download music directly from your terminal with interactive mode
* Queue support
* Input url mode with download support for albums, tracks, artists, playlists and labels

## Getting started

> Note: `qobuz-dl` requires Python >3.6

> Note 2: You'll need an **active subscription**

#### Install qobuz-dl with pip
##### Linux / MAC OS / Windows
```
pip3 install --upgrade qobuz-dl
```
#### Run qobuz-dl and enter your credentials
##### Linux / MAC OS
```
qobuz-dl
```
##### Windows
```
qobuz-dl.exe
```

> If something fails, run `qobuz-dl -r` to reset your config file.

## Usage
```
usage: qobuz-dl [-h] [-a] [-r] [-i Album/track URL] [-q int] [-l int] [-d PATH]

optional arguments:
  -h, --help          show this help message and exit
  -r                  create/reset config file
  -a                  enable albums-only search
  -i album/track/artist/label/playlist URL  run qobuz-dl on URL input mode (download by url)
  -q int              quality (5, 6, 7, 27) (default: 6) [320, LOSSLESS, 24B <96KHZ, 24B >96KHZ]
  -l int              limit of search results by type (default: 10)
  -d PATH             custom directory for downloads (default: 'Qobuz Downloads')
```
## A note about Qo-DL
`qobuz-dl` is inspired in the discontinued Qo-DL-Reborn. This program uses two modules from Qo-DL: `qopy` and `spoofer`, both written by Sorrow446 and DashLt.
## Disclaimer
This tool was written for educational purposes. I will not be responsible if you use this program in bad faith.
Also, you are accepting this: https://static.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf
