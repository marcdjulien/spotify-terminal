import urllib
import json

from authentication import authenticate
from globals import *
from util import *
from model import (
    Artist,
    Album,
    Track,
    NoneTrack,
    Playlist
)

import requests


logger = logging.getLogger(__name__)


def needs_authentication(func):
    """Decorator for call that need authentications.msg

    Re-authenticate if the API call fails.
    """
    def retry(self, *args, **kwargs):
        """Call then function and retry on authentication failure."""
        try:
            return func(self, *args, **kwargs)
        except requests.HTTPError as e:
            msg = str(e)
            if "Unauthorized" in msg or "Expired" in msg:
                logger.warning("Failed to make request. Re-authenticating.")
                self.auth_from_web()
                try:
                    return func(*args, **kwargs)
                except Exception:
                    logger.warning("Failed again after re-authenticating. "
                                   "Giving up on the following:")
                    logger.warning("\t%s %s", args, kwargs)
                    logger.warning("\t %s", e)
            else:
                logger.warning("Failed to make API call:")
                logger.warning("\t%s %s", args, kwargs)
                logger.warning("\t %s", e)
        except requests.ConnectionError as e:
            logger.warning("Connection Error:")
            logger.warning("\t %s", str(e))

    return retry


def uri_cache(func):
    """Use the cache to fetch a URI."""
    def try_cache(self, obj, *args, **kwargs):
        """USe the cache to fetch the URI."""
        key = func.__name__ + str(obj['uri'])
        result = self._uri_cache.get(key)
        if result:
            logger.debug("Cache hit: %s(%s %s %s)",
                         func.__name__, obj, str(args), str(kwargs))
            return result
        else:
            logger.debug("Cache miss: %s(%s %s %s)",
                         func.__name__, obj, str(args), str(kwargs))
            result = func(self, obj, *args, **kwargs)
            self._uri_cache[key] = result
            return result

    return try_cache


class SpotifyApi(object):
    """Interface to make API calls."""

    def __init__(self, username):
        self.username = username
        """The Spotify username."""

        self.api_token_type = None
        """API token type."""

        self.api_access_token = None
        """API access token."""

        self._uri_cache = {}
        """Cache of Spotify URIs."""

        # Try to use the saved access token.
        # If that fails, re-authenticate from the web.
        if not self.auth_from_file():
            self.auth_from_web()

    def get_username(self):
        """Returns the current username.

        Returns:
            str: The current username.
        """
        return self.username

    def play(self, track_uri=None, context_uri=None):
        """Play a Spotify track.

        Args:
            track_uri (str): The track uri.
            context_uri (str): The context uri.

        Returns:
            Reponse: The reponse if successful, otherwise None.
        """
        params = {}
        if context_uri:
            params = {"context_uri": context_uri}
            if track_uri is None:
                # No track given, play the first one.
                params["offset"] = {"position": 0}
            else:
                # Play the requested track within the context.
                if is_int(track_uri):
                    params["offset"] = {"position": track_uri}
                else:
                    params["offset"] = {"uri": track_uri}

        # No context given, just play the track.
        if track_uri and not context_uri:
            if track_uri.startswith("spotify:track:"):
                params['uris'] = [track_uri]

        return self.put_api_v1("me/player/play", params)

    def pause(self):
        """Pause the player.

        Returns:
            Reponse: The reponse if successful, otherwise None.
        """
        return self.put_api_v1("me/player/pause")

    def next(self):
        """Play the next song.

        Returns:
            Reponse: The reponse if successful, otherwise None.
        """
        return self.post_api_v1("me/player/next")

    def previous(self):
        """Play the previous song.

        Returns:
            Reponse: The reponse if successful, otherwise None.
        """
        return self.post_api_v1("me/player/previous")

    def shuffle(self, shuffle):
        """Set the player to shuffle.

        Args:
            shuffle (bool): Whether to shuffle or not.

        Returns:
            Reponse: The reponse if successful, otherwise None.
        """
        p = urllib.urlencode({"state": shuffle})
        return self.put_api_v1("me/player/shuffle?" + p)

    def repeat(self, repeat):
        """Set the player to repeat.

        Args:
            repeat (bool): Whether to repeat or not.

        Returns:
            Reponse: The reponse if successful, otherwise None.
        """
        p = urllib.urlencode({"state": repeat})
        return self.put_api_v1("me/player/repeat?" + p)

    def volume(self, volume):
        """Set the player volume.

        Args:
            volume (int): Volume level. 0 - 100 (inclusive).

        Returns:
            Reponse: The reponse if successful, otherwise None.
        """
        p = urllib.urlencode({"volume_percent": volume})
        return self.put_api_v1("me/player/volume?" + p)

    def get_player_state(self):
        """Returns the player state.

        The following information is returned:
            device, repeat_state, shuffle_state, context,
            timestamp, progress_ms, is_playing, item.

        Returns:
            dict: Information containing the player state.
        """
        return self.get_api_v1("me/player")

    def get_currently_playing(self):
        """Get the currently playing Track.

        Returns:
            Track: The currently playing Track or NoneTrack.
        """
        playing = self.get_api_v1("me/player/currently-playing")
        if playing:
            track = playing['item']
            if track:
                playing.update(track)
                return Track(playing)
            else:
                return NoneTrack
        else:
            return NoneTrack

    def get_user_info(self, username):
        """Returns a dict of the a users info.

        The following information is returned:
            display_name, external_urls, followers, href, id,
            images, type, uri.

        username (str): The username.

        Returns:
            dict: Users information.
        """
        return self.get_api_v1("users/{}".format(username))

    def search(self, types, query, limit=20):
        """Calls Spotify's search api.

        Args:
            types (tuple): Strings of the type of search (i.e, 'artist',
                'track', 'album')
            query (str): The search query.
            limit (int): Limit of the amount of results to return per
                type of search in 'types'.

        Returns:
            dict: Collection of 'artist', 'album', and 'track' objects.
        """
        type_str = ",".join(types)
        params = {'type': type_str,
                  'q': query,
                  'limit': limit}

        result = self.get_api_v1("search", params)

        cast = {
            'artist': Artist,
            'track': Track,
            'album': Album,
        }

        combined = []
        for type in types:
            # Results are plural (i.e, 'artists', 'albums', 'tracks')
            type = type + 's'
            combined.extend([cast[type](info) for info in result[type]['items']])

        return combined

    @uri_cache
    def get_albums_from_artist(self, artist,
                               type=("album", "single", "appears_on", "compilation"), market="US"):
        """Get Albums from a certain Artist.

        Args:
            artist (Artist): The Artist.
            type (iter): Which types of albums to return.

        Returns:
            tuple: The Albums.
        """
        params = {"include_groups": ",".join(type),
                  "market": market}
        page = self.get_api_v1("artists/{}/albums".format(artist['id']), params)
        albums = self.extract_page(page)

        return tuple([Album(album) for album in albums])

    @uri_cache
    def get_tracks_from_album(self, album):
        """Get Tracks from a certain Album.

        Args:
            album (Album): The Album to get Tracks from.

        Returns:
            tuple: The Tracks.
        """
        page = self.get_api_v1("albums/{}/tracks".format(album['id']))
        tracks = []
        for track in self.extract_page(page):
            track['album'] = album
            tracks.append(Track(track))
        return tuple(tracks)

    @uri_cache
    def get_tracks_from_playlist(self, playlist):
        """Get Tracks from a certain Playlist.

        Args:
            playlist (Playlist): The Playlist to get Tracks from.

        Returns:
            tuple: The Tracks.
        """
        # Special case for the "Saved" Playlist
        if playlist['uri'] is None:
            return self.get_saved_tracks()
        else:
            url = "users/{}/playlists/{}/tracks".format(playlist['owner']['id'],
                                                        playlist['id'])
            page = self.get_api_v1(url)
            result = [Track(track["track"]) for track in self.extract_page(page)]

        return tuple(result)

    def get_saved_tracks(self):
        """Get the Tracks from the "Saved" songs.

        Returns:
            tuple: The Tracks.
        """
        page = self.get_api_v1("me/tracks")
        return tuple([Track(saved["track"]) for saved in self.extract_page(page)])

    def get_user_playlists(self):
        """Get the Playlists from the current user.

        Return:
            tuple: The Plalists.
        """
        url = "users/{}/playlists".format(self.username)
        page = self.get_api_v1(url)
        return tuple([Playlist(p) for p in self.extract_page(page)])

    def extract_page(self, page):
        """Extract all items from a page.

        Args:
            page (dict): The page object.

        Returns:
            list: All of the items.
        """
        lists = []
        lists.extend(page['items'])
        while page['next'] is not None:
            page = self.get_api_v1(page['next'].split('/v1/')[-1])
            lists.extend(page['items'])
        return lists

    @needs_authentication
    def get_api_v1(self, endpoint, params=None):
        """Spotify v1 GET request.

        Args:
            endpoint (str): The API endpoint.
            params (dict): Query parameters (Default is None).

        Returns:
            Reponse: The HTTP Reponse.
        """
        headers = {"Authorization": "%s %s" % (self.api_token_type, self.api_access_token)}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        return self.get_json(api_url, headers=headers, params=params)

    @needs_authentication
    def put_api_v1(self, endpoint, params=None):
        """Spotify v1 PUT request.

        Args:
            endpoint (str): The API endpoint.
            params (dict): Query parameters (Default is None).

        Returns:
            Reponse: The HTTP Reponse.
        """
        headers = {"Authorization": "%s %s" % (self.api_token_type, self.api_access_token),
                   "Content-Type": "application/json"}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        resp = requests.put(api_url, headers=headers, json=params)
        self.check_response(resp)
        return resp

    @needs_authentication
    def post_api_v1(self, endpoint, params=None):
        """Spotify v1 POST request.

        Args:
            endpoint (str): The API endpoint.
            params (dict): Data parameters (Default is None).

        Returns:
            Reponse: The HTTP Reponse.
        """
        headers = {"Authorization": "%s %s" % (self.api_token_type, self.api_access_token),
                   "Content-Type": "application/json"}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        resp = requests.post(api_url, headers=headers, json=params)
        self.check_response(resp)
        return ascii(resp.text)

    def get_json(self, url, params={}, headers={}):
        """Return a JSON from a GET request.

        Args:
            url (str): The URL.
            params (dict): Query parameters.
            headers (dict): HTTP headers.

        Returns:
            dict: The resulting JSON.
        """
        resp = requests.get(url, params=params, headers=headers)
        self.check_response(resp)
        return json.loads(ascii(resp.text)) if resp.text else {}

    def check_response(self, resp):
        """Check a HTTP Reponse.

        Args:
            resp (Reponse): The Reponse to check.
        """
        resp.raise_for_status()

    def auth_from_file(self):
        """Authenticate from the saved file.

        Returns:
            bool: True on success.
        """
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
        """Authenticate from the web.

        Returns:
            bool: True on success.
        """
        auth_data = authenticate()
        if auth_data:
            for k, v in auth_data.items():
                setattr(self, "api_{}".format(k), v)
            return True
        else:
            return False
