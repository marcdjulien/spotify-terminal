"""
Modified from Carl Bystrom
http://cgbystrom.com/articles/deconstructing-spotifys-builtin-http-server/
https://github.com/cgbystrom/spotify-local-http-api
"""

import ssl
import string
import urllib
import urllib2
import json
import time
import sys

from string import ascii_lowercase
from random import choice


class SpotifyRemote(object):

    def __init__(self, token_type=None, access_token=None):
        self.api_token_type = token_type
        self.api_access_token = access_token

    def play(self, track_uri=None, context_uri=None):
        """Play a Spotify track.

        Args:
            track_uri (str): The track uri.
            context_uri (str): The context uri.
        """
        params = {}
        if context_uri:
            params = {"context_uri": context_uri}
            if track_uri is None:
                params["offset"] = {"position": 0}
            else:                
                params["offset"] = {"uri": track_uri}
        
        if track_uri and not context_uri:
            if track_uri.startswith("spotify:track:"):
                params['uris'] = [track_uri]

        endpoint = "me/player/play"
        print params
        self.put_api_v1(endpoint, params)

    def next(self):
        self.post_api_v1("me/player/next")

    def previous(self):
        self.post_api_v1("me/player/previous")

    def pause(self):
        self.put_api_v1("me/player/pause")

    def get_currently_playing(self):
        """Return the currently playing track."""
        return self.get_api_v1("me/player/currently-playing")

    def get_user_info(self, username):
        """Returns a dict of the a users info.
        
        username (str): The username.

        Returns:
            dict: The JSON dictionary containing the users information.
        """
        return self.get_api_v1("users/{}".format(username))

    def search(self, types, query, limit=20):
        """Calls Spotify's search api.

        Args:
            types (list): Strings of the type of search (i.e, 'artist', 
                'track', 'album')
            query (str): What to search for
            limit (int): Limit on the amount of results te return per 
                type of search in 'types'
        
        Returns:
            dict: Collection of 'artist', 'album', and 'track' objects. 
        """
        # The API returns these with 's' at the end.
        # But the query doesn't use 's'. 
        # Strip them so we can chain calls together.
        for i in xrange(len(types)): 
            types[i] = types[i][:-1]

        type_str = string.join(types,",")
        params = {'type':type_str,
                  'q':query,
                  'limit':limit}
        
        result = self.get_api_v1("search", params)
        ret = {}
        for type in types:
            ret[type+'s'] = result[type+'s']['items']
        return ret

    def get_albums_from_artist(self, id1, type=("album","single")):
        """Get a list of albums from a certain artist
        
        id1 (str): The id of the artist
        type (iter): Which types of albums to return
        """
        albums = []
        page = self.get_api_v1("artists/{}/albums".format(id1))
        albums.extend(page['items'])
        while page['next'] != None:
            page = self.get_api_v1(page['next'].split('/v1/')[-1])
            albums.extend(page['items'])
        titles = []
        final = []
        for album in albums:
            if album['name'] not in titles and album["album_type"] in type:
                final.append(album)
                titles.append(album['name'])
        return final

    def get_tracks_from_album(self, id):
        """Get a list of tracks from a certain album."""
        return self.get_api_v1("albums/{}/tracks".format(id))['items']

    def get_tracks_from_playlist(self, owner_id, id):
        url = "users/{}/playlists/{}/tracks".format(owner_id, id)
        playlist_tracks = self.get_api_v1(url)['items']
        tracks = []
        for ptrack in playlist_tracks:
            tracks.append(ptrack['track'])
        return tracks

    def get_artists_from_track(self, track_id):
        return self.get_api_v1("tracks/{}".format(track_id))['artists']

    def get_artists_from_album(self, album_id):
        return self.get_api_v1("albums/{}".format(album_id))['artists']

    def get_saved_tracks(self, offset, limit):
        params = {"offset": offset, "limit":limit}
        tracks = []
        for track in self.get_api_v1("me/tracks", params=params)["items"]:
            tracks.append(track['track'])
        return tracks

    def get_user_playlists(self, username):
        """Get a list of playlists from a certain user."""
        url = "users/{}/playlists".format(username)
        page = self.get_api_v1(url)
        lists = []
        lists.extend(page['items'])
        while page['next'] != None:
            page = self.get_api_v1(page['next'].split('/v1/')[-1])
            lists.extend(page['items'])
        return lists

    def get_api_v1(self, endpoint, params=None):
        headers = {"Authorization": "%s %s"%(self.api_token_type, self.api_access_token)}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        return self.get_json(api_url, headers=headers, params=params)

    def put_api_v1(self, endpoint, params=None):
        headers = {"Authorization": "%s %s"%(self.api_token_type, self.api_access_token),
                   "Content-Type": "application/json",
                   "Accept": "application/json"}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        request = urllib2.Request(api_url, headers=headers, data=json.dumps(params))
        request.get_method = lambda: 'PUT'
        return urllib2.urlopen(request)

    def post_api_v1(self, endpoint, params=None):
        headers = {"Authorization": "%s %s"%(self.api_token_type, self.api_access_token)}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        request = urllib2.Request(api_url, headers=headers, data=json.dumps(params))
        request.get_method = lambda: 'POST'
        return urllib2.urlopen(request)

    def get_json(self, url, params={}, headers={}):
        """Return a JSON from a GET request.

        Args:
            url (str): The URL.
            params (dict): URL parameters.
            headers (dict): HTTP headers.

        Returns:
            dict: The resulting JSON.
        """ 
        if params:
            url += "?" + urllib.urlencode(params)
        request = urllib2.Request(url, headers=headers)
        return json.loads(urllib2.urlopen(request).read())