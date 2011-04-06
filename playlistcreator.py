'''A Python class for creating and updating playlists based on track and artist names'''


import shelve, re, logging, json, time
from rdioapi import Rdio


def uniq(seq):
  '''return non-duplicate items from a sequence, in order'''
  u = []
  for i in seq:
    if i not in u: u.append(i)
  return u


class Fuzzy(unicode):
  '''a string where equality is defined as: edit distance as a percentage of the sum of the lengths of the inputs <= 25%'''
  def __eq__(self, other):
    from levenshtein_distance import levenshtein_distance as distance
    d = distance(self.lower(), other.lower())
    return int(100 * float(d) / len(self+other)) <= 25


class Term(unicode):
  '''a string that knows about fuzzy matching and simple transforms'''
  PAREN_RE = re.compile(r'\([^)]*\)') # remove text in parens
  FEATURE_RE = re.compile(r' (&|Feat\.|feat\.) .*') # remove & / Feat. / feat.
  @property
  def forms(self):
    return (self,
            Term.PAREN_RE.sub('', self), Term.FEATURE_RE.sub('', self),
            self.replace('!', ' '), # for Wakey Wakey!
            )
  def __eq__(self, other):
    fuzz = Fuzzy(other)
    return any((fuzz == f for f in self.forms))


class PlaylistCreator(object):
  def __init__(self):
    self.oauth_state = shelve.open('oauth_state')
    self.found_tracks = shelve.open('found_tracks')

  def __del__(self):
    self.oauth_state.close()
    self.found_tracks.close()

  __cached_rdio = None
  @property
  def rdio(self):
    if self.__cached_rdio is None:
      self.__cached_rdio = Rdio('7v2443fffahpt4fazmmh3hx7', '2nzyX96YAu', self.oauth_state)
    return self.__cached_rdio

  @property
  def authenticated(self):
    if not self.rdio.authenticated:
      return False
    try:
      return self.rdio.currentUser() is not None
    except BaseException, e:
      self.rdio.logout()
      return False

  def authenticate(self):
    # let's clear our old auth state
    for k in self.oauth_state.keys():
      del self.oauth_state[k]
    self.__cached_rdio = None

    # do a PIN based auth
    import webbrowser
    webbrowser.open(self.rdio.begin_authentication('oob'))
    verifier = raw_input('Enter the PIN from the Rdio site: ').strip()
    self.rdio.complete_authentication(verifier)

  def find_track(self, artist, title):
    '''try to find a track but apply various transfomations'''
    artist = Term(artist)
    title = Term(title)

    # for each of the forms, search...
    for a, t in uniq(zip(artist.forms, title.forms)):
      # query the API
      q = ('%s %s' % (a, t)).encode('utf-8')
      result = self.rdio.search(query=q, types='Track', never_or=True)

      # if there were no results then the search failed
      if not result['track_count']:
        logging.warning('  rdio.search failed for: '+q)
        continue

      # look through the results for a good match
      for track in result['results']:
        if artist == track['artist'] and \
            title == track['name']:
          return track
      # none found
      logging.warning('rdio.search succeeded but match failed: '+q)
      return None

  def make_playlist(self, name, desc, tracks):
    '''make or update a playlist named @name, with a description @desc, with the tracks specified in @tracks, a list of (artistname, trackname) pairs'''
    tracks_meta = []
    for artistname, trackname in tracks:
      key = json.dumps((artistname, trackname)).encode('utf-8')
      logging.info('Looking for: %s' % key)
      if key in self.found_tracks:
        logging.info(' found it in the cache: %s' % self.found_tracks[key]['key'])
        tracks_meta.append(self.found_tracks[key])
      else:
        track_meta = self.find_track(artistname, trackname)
        if track_meta is not None:
          logging.info(' found it in on the site: %s' % track_meta['key'])
          tracks_meta.append(track_meta)
          self.found_tracks[key] = track_meta
        else:
          logging.info(' not found')
          pass

    logging.info('Found %d / %d tracks' % (len(tracks_meta), len(tracks)))

    track_keys = [track['key'] for track in tracks_meta]

    # ask the server for playlists
    playlists = self.rdio.getPlaylists()
    for playlist in playlists['owned']:
      # look for a playlist with the right name
      if playlist['name'] == name:
        logging.info('Found the playlist')
        # when we find it, remove all of those tracks...
        playlist = self.rdio.get(keys=playlist['key'], extras='tracks')[playlist['key']]
        keys = [t['key'] for t in playlist['tracks']]
        self.rdio.removeFromPlaylist(playlist=playlist['key'],
                                     index=0, count=playlist['length'],
                                     tracks=','.join(keys))
        # now add all of th tracks we just got
        self.rdio.addToPlaylist(playlist=playlist['key'],
                                tracks=','.join(track_keys))
        logging.info('Updated the playlist')
        break
    else:
      # didn't find the playlist
      # create it!
      playlist = self.rdio.createPlaylist(name=name,
                                          description=desc,
                                          tracks=','.join(track_keys))
      logging.info('Created the playlist')
