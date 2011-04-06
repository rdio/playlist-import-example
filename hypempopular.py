#!/usr/bin/env python

URL='http://hypem.com/popular?ax=1'
PLAYLIST_NAME='Hype Machine Popular'
PLAYLIST_DESC='Hype Machine Popular tracks, see http://hypem.com/popular'

import sys, logging
logging.basicConfig(level=logging.ERROR)
from playlistcreator import PlaylistCreator
pc = PlaylistCreator()
if not pc.authenticated:
  print 'You need to authenticate by running ./authenticate.py first'
  sys.exit(0)

logging.basicConfig(level=logging.ERROR)

# the Hype Machine "popular" page includes a bunch of structures like:
#   <h3 class="track_name"><a>artist name</a> <a>track name</a></h3>
# we can parse that out into (artistname, trackname) pairs

from BeautifulSoup import BeautifulSoup
from urllib import urlopen

bs = BeautifulSoup(urlopen(URL))

tracks = []

for node in [tn for tn in bs.findAll('h3') if tn.get('class') == 'track_name']:
  artist, track = [a.text for a in node.findChildren('a')]
  tracks.append((artist, track))

# now build a playlist
pc.make_playlist(PLAYLIST_NAME, PLAYLIST_DESC, tracks)
