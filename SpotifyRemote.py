"""
Modified from Carl Bystrom
http://cgbystrom.com/articles/deconstructing-spotifys-builtin-http-server/
https://github.com/cgbystrom/spotify-local-http-api
"""
import ssl
from string import ascii_lowercase
import string
from random import choice
import urllib
import urllib2
import json
import time
import sys

PORT = 4370
DEFAULT_RETURN_ON = ['login', 'logout', 'play', 'pause', 'error', 'ap']
ORIGIN_HEADER = {'Origin': 'https://open.spotify.com'}

class SpotifyRemote(object):
    """docstring for SpotifyRemote"""
    # Default port that Spotify Web Helper binds to.
    def __init__(self, username="null"):
        super(SpotifyRemote, self).__init__()
        # For the SpotifyWebHelper 
        self.oauth_token = self.get_oauth_token()
        self.csrf_token = self.get_csrf_token()
        # For user info 



    # I had some troubles with the version of Spotify's SSL cert and Python 2.7 on Mac.
    # Did this monkey dirty patch to fix it. Your milage may vary.
    def new_wrap_socket(self, *args, **kwargs):
        kwargs['ssl_version'] = ssl.PROTOCOL_SSLv3
        return self.orig_wrap_socket(*args, **kwargs)

    orig_wrap_socket, ssl.wrap_socket = ssl.wrap_socket, new_wrap_socket

    def get_json(self, url, params={}, headers={}):
        if params:
            url += "?" + urllib.urlencode(params)
        request = urllib2.Request(url, headers=headers)
        return json.loads(urllib2.urlopen(request).read())


    def generate_local_hostname(self):
        """Generate a random hostname under the .spotilocal.com domain"""
        subdomain = ''.join(choice(ascii_lowercase) for x in range(10))
        return subdomain + '.spotilocal.com'


    def get_url(self, url):
        return "https://%s:%d%s" % (self.generate_local_hostname(), PORT, url)


    def get_version(self):
        return self.get_json(self.get_url('/service/version.json'), params={'service': 'remote'}, headers=ORIGIN_HEADER)


    def get_oauth_token(self):
        data = self.get_json('http://open.spotify.com/token')
        return data['t']

    def get_csrf_token(self):
        # Requires Origin header to be set to generate the CSRF token.
        return self.get_json(self.get_url('/simplecsrf/token.json'), headers=ORIGIN_HEADER)['token']


    def get_status(self, oauth_token, csrf_token, return_after=59, return_on=DEFAULT_RETURN_ON):
        params = {
            'oauth': self.oauth_token,
            'csrf': self.csrf_token,
            'returnafter': return_after,
            'returnon': ','.join(return_on)
        }
        return self.get_json(self.get_url('/remote/status.json'), params=params, headers=ORIGIN_HEADER)


    def pause(self, pause):
        params = {
            'oauth': self.oauth_token,
            'csrf': self.csrf_token,
            'pause': 'true' if pause else 'false'
        }
        self.get_json(self.get_url('/remote/pause.json'), params=params, headers=ORIGIN_HEADER)


    def unpause(self):
        self.pause(pause=False)


    def play(self, spotify_uri):
        params = {
            'oauth': self.oauth_token,
            'csrf': self.csrf_token,
            'uri': spotify_uri,
            'context': spotify_uri,
        }
        self.get_json(self.get_url('/remote/play.json'), params=params, headers=ORIGIN_HEADER)


    def open_spotify_client(self):
        return get(get_url('/remote/open.json'), headers=ORIGIN_HEADER).text
            
    ###################################
    ### Added by Marc-Daniel Julien ###
    ###################################

    """ 
    Returns a dict of the a users info
    """
    def get_user_info(self, username):
        url = "https://api.spotify.com/v1/users/"+username
        return self.get_json(url)

    """
    Calls Spotify's search api
    types: a list containing string of the type of search 
           (ie, 'artist', 'track', 'album')
    query: a string of what to search for
    limit: limit on the amount of results te return per type of search
           in 'types'
    """
    def search(self, types, query, limit=20):
        for i in xrange(len(types)): types[i] = types[i][:-1]
        type_str = string.join(types,",")
        params = {
                    'type':type_str,
                    'q':query,
                    'limit':limit
                 }
        url = "https://api.spotify.com/v1/search"
        url += "?" + urllib.urlencode(params)
        result = self.get_json(url)
        ret = {}
        for type in types:
            ret[type+'s'] = result[type+'s']['items']
        return ret

    """
    Calls Spotify's API to get a list of albums from a certain artist
    id1: the id of the artist
    type: which types of albums to return
    """
    def get_artist_albums(self, id1, type=["album","single"]):
        url = "https://api.spotify.com/v1/artists/{}/albums".format(id1)
        albums = []
        page = self.get_json(url)
        albums.extend(page['items'])
        while page['next'] != None:
            page = self.get_json(page['next'])
            albums.extend(page['items'])
        titles = []
        final = []
        for album in albums:
            if album['name'] not in titles and album["album_type"] in type:
                final.append(album)
                titles.append(album['name'])
        return final
    """
    Calls Spotify's API to get a list of tracks from a certain album
    id1: the id of the album
    """
    def get_album_tracks(self, id1):
        url = "https://api.spotify.com/v1/albums/{}/tracks".format(id1)
        return self.get_json(url)['items']

    """ Not working!
    Calls Spotify's API to get a list of playlists from a certain user
    username: user name of the user
    """
    def get_user_playlists(self, username):
        url = "https://api.spotify.com/v1/users/{}/playlists".format(username)
        results = self.get_json(url)
        return results