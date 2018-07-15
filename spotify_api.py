import string
import urllib
import urllib2
import json
from collections import defaultdict

from authentication import authenticate
from util import *
from globals import *
from model import (
    Artist,
    Album,
    Track,
    NoneTrack
)

import requests

logger = logging.getLogger(__name__)

def authenticate_retry(func):
    def retry(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as e:
            msg = str(e)
            if "Unauthorized" in msg or "Expired" in msg:
                args[0].auth_from_web()
                try:
                    return func(*args, **kwargs)
                except:
                    logger.debug("%s %s", args, kwargs)
                    logger.debug(msg)
                    logger.debug(e)
            else:
                logger.debug("%s %s", args, kwargs)
                logger.debug(msg)

    return retry


def uri_cache(func):
    """Use the cache to fetch a URI"""

    def try_cache(self, obj, *args, **kwargs):
        """Check the cache first."""
        key = func.__name__+str(obj['uri'])
        result = self._uri_cache.get(key)
        if result:
            logger.debug("Cache hit: %s(%s %s %s)", func.__name__, obj, str(args), str(kwargs))
            return result
        else:
            logger.debug("Cache miss: %s(%s %s %s)", func.__name__, obj, str(args), str(kwargs))
            result = func(self, obj, *args, **kwargs)
            self._uri_cache[key] = result
            return result

    return try_cache


class SpotifyApi(object):
    """Interface to make API calls."""

    def __init__(self, username):
        self.username = username
        self.api_token_type = None
        self.api_access_token = None
        if not self.auth_from_file():
            self.auth_from_web()

        # caches
        self._uri_cache = {}

    def get_username(self):
        return self.username

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
                if is_int(track_uri):
                    params["offset"] = {"position": track_uri}
                else:
                    params["offset"] = {"uri": track_uri}

        if track_uri and not context_uri:
            if track_uri.startswith("spotify:track:"):
                params['uris'] = [track_uri]

        self.put_api_v1("me/player/play", params)

    def pause(self):
        self.put_api_v1("me/player/pause")

    def next(self):
        self.post_api_v1("me/player/next")

    def previous(self):
        self.post_api_v1("me/player/previous")

    def shuffle(self, shuffle):
        p = urllib.urlencode({"state":shuffle})
        self.put_api_v1("me/player/shuffle?"+p)

    def repeat(self, repeat):
        p = urllib.urlencode({"state":repeat})
        self.put_api_v1("me/player/repeat?"+p)

    def volume(self, volume):
        p = urllib.urlencode({"volume_percent":volume})
        self.put_api_v1("me/player/volume?"+p)

    def get_player_state(self):
        return self.get_api_v1("me/player")

    def get_currently_playing(self):
        obj = self.get_api_v1("me/player/currently-playing")
        track = obj['item']
        if track:
            obj.update(track)
            return Track(obj)
        else:
            return NoneTrack

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
        type_str = string.join([type[:-1] for type in types], ",")
        params = {'type':type_str,
                  'q':query,
                  'limit':limit}

        result = self.get_api_v1("search", params)

        cast = {
            'artists':Artist,
            'tracks':Track,
            'albums':Album,
        }

        ret = []
        for type in types:
            ret.extend([cast[type](info) for info in result[type]['items']])

        return ret

    @uri_cache
    def get_albums_from_artist(self, artist, type=("album","single")):
        """Get a list of albums from a certain artist

        Args:
            artist (Artist): The artist.
            type (iter): Which types of albums to return.

        Returns:
            list: The Albums.
        """
        page = self.get_api_v1("artists/{}/albums".format(artist['id']))
        albums = self.extract_page(page)

        titles = []
        final = []
        for album in albums:
            if album['name'] not in titles and album["album_type"] in type:
                final.append(Album(album))
                # TODO: Figure out why I ned the following
                titles.append(album['name'])
        return tuple(final)

    @uri_cache
    def get_tracks_from_album(self, album):
        """Get a list of tracks from a certain album."""
        page = self.get_api_v1("albums/{}/tracks".format(album['id']))
        tracks = []
        for track in self.extract_page(page):
            track['album'] = album
            track = Track(track)
            tracks.append(track)
        return tuple(tracks)

    @uri_cache
    def get_tracks_from_playlist(self, playlist):
        # Special case for the Saved Tracks Playlist
        if playlist['uri'] is None:
            result = self.get_saved_tracks()
        else:
            url = "users/{}/playlists/{}/tracks".format(playlist['owner']['id'],
                                                        playlist['id'])
            page = self.get_api_v1(url)
            result = [Track(track["track"]) for track in self.extract_page(page)]

        return tuple(result)

    def get_artists_from_track(self, track_id):
        return self.get_api_v1("tracks/{}".format(track_id))['artists']

    def get_artists_from_album(self, album_id):
        return self.get_api_v1("albums/{}".format(album_id))['artists']

    def get_saved_tracks(self):
        page = self.get_api_v1("me/tracks")
        return [Track(saved["track"]) for saved in self.extract_page(page)]

    def get_user_playlists(self):
        """Get a list of playlists from the current user."""
        url = "users/{}/playlists".format(self.username)
        page = self.get_api_v1(url)
        return self.extract_page(page)

    def extract_page(self, page):
        lists = []
        lists.extend(page['items'])
        while page['next'] != None:
            page = self.get_api_v1(page['next'].split('/v1/')[-1])
            lists.extend(page['items'])
        return lists

    @authenticate_retry
    def get_api_v1(self, endpoint, params=None):
        headers = {"Authorization": "%s %s"%(self.api_token_type, self.api_access_token)}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        return self.get_json(api_url, headers=headers, params=params)

    @authenticate_retry
    def put_api_v1(self, endpoint, params=None):
        headers = {"Authorization": "%s %s"%(self.api_token_type, self.api_access_token),
                   "Content-Type": "application/json"}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        resp = requests.put(api_url, headers=headers, json=params)
        self.check(resp)
        return resp.text

    @authenticate_retry
    def post_api_v1(self, endpoint, params=None):
        headers = {"Authorization": "%s %s"%(self.api_token_type, self.api_access_token),
                   "Content-Type": "application/json"}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        resp = requests.post(api_url, headers=headers, json=params)
        self.check(resp)
        return resp.text

    def get_json(self, url, params={}, headers={}):
        """Return a JSON from a GET request.

        Args:
            url (str): The URL.
            params (dict): URL parameters.
            headers (dict): HTTP headers.

        Returns:
            dict: The resulting JSON.
        """
        resp = requests.get(url, params=params, headers=headers)
        self.check(resp)
        if resp.text:
            return json.loads(resp.text)
        else:
            return defaultdict(lambda: "[Null]")

    def check(self, resp):
        resp.raise_for_status()

    def auth_from_file(self):
        if os.path.isfile(AUTH_FILENAME):
            auth_file = open(AUTH_FILENAME)
            for line in auth_file:
                line = line.strip()
                toks = line.split("=")
                setattr(self, "api_{}".format(toks[0]), toks[1])
            return True
        else:
            return False

    def auth_from_web(self):
        auth_data = authenticate()
        for k,v in auth_data.items():
            setattr(self, "api_{}".format(k), v)
        # Assuming this will work everytime for now
        return True

