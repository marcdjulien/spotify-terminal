import urllib
import json
import requests
from threading import Thread

import common
from authentication import Authenticator
from cache import UriCache
from model import (
    Artist,
    Album,
    Device,
    Track,
    User,
    NoneTrack,
    Playlist
)


logger = common.logging.getLogger(__name__)


def needs_authentication(func):
    """Decorator for call that need authentications.msg

    Re-authenticate if the API call fails.
    """
    def is_auth_message(msg):
        keywords = ["Unauthorized",
                    "Expired"]
        return any([k in msg for k in keywords])

    @common.catch_exceptions
    def wrapper(self, *args, **kwargs):
        """Call then function and wrapper on authentication failure."""
        try:
            logger.debug("Executing: %s\n\t %s %s", func.__name__, args, kwargs)
            return func(self, *args, **kwargs)
        except requests.HTTPError as e:
            msg = str(e)
            if is_auth_message(msg):
                logger.warning("Failed to make request. Re-authenticating.")
                self.auth.refresh()
                try:
                    return func(self, *args, **kwargs)
                except Exception:
                    logger.warning("Failed again after re-authenticating. "
                                   "Giving up.")
            else:
                logger.warning("Failed to make API call")
        except requests.ConnectionError as e:
            logger.warning("Connection Error: %s", str(e))

    return wrapper


def uri_cache(func):
    """Use the cache to fetch a URI."""

    @common.catch_exceptions
    def wrapper(self, obj, *args, **kwargs):
        """Use the cache to fetch the URI."""
        key = func.__name__ + ":" + str(obj['uri'])

        # Get a fresh copy and clear the cache.
        if "force_clear" in kwargs:
            kwargs.pop("force_clear")
            self._uri_cache.clear(key)

        result = self._uri_cache.get(key)
        if result:
            return result
        else:
            logger.debug("Fetching data from the web...")
            result = func(self, obj, *args, **kwargs)
            self._uri_cache[key] = result
            return result

    return wrapper


def async(func):
    """Execute the function asynchronously"""

    @common.catch_exceptions
    def wrapper(*args, **kwargs):
        Thread(target=func, args=args, kwargs=kwargs).start()

    return wrapper


class SpotifyApi(object):
    """Interface to make API calls."""

    def __init__(self, username):
        self.username = username
        """The Spotify username."""

        self._uri_cache = UriCache(self.username)
        """Cache of Spotify URIs."""

        self.auth = Authenticator()
        """Handles OAuth 2.0 authentication."""

        self.auth.authenticate()

    def get_username(self):
        """Returns the current username.

        Returns:
            str: The current username.
        """
        return self.username

    @async
    def play(self, track=None, context_uri=None, uris=None, device=None):
        """Play a Spotify track.

        Args:
            track (str, int): The track uri or position.
            context_uri (str): The context uri.
            uris (iter): Collection of uris to play.
            device (Device): A device to play.
        """
        data = {}

        # Special case when playing a set of uris.
        if uris:
            data['uris'] = uris
            if common.is_int(track):
                data["offset"] = {"position": track}
        elif context_uri:
            # Set the context that we are playing in.
            data["context_uri"] = context_uri

            if common.is_int(track):
                data["offset"] = {"position": track}
            elif isinstance(track, basestring):
                data["offset"] = {"uri": track}

        # No context given, just play the track.
        elif track is not None and not context_uri:
            if isinstance(track, basestring) and track.startswith("spotify:track"):
                data['uris'] = [track]

        params = {}
        if device and device['id']:
            params["device_id"] = device['id']

        self.put_api_v1("me/player/play", params, data)

    @async
    def transfer_playback(self, device):
        """Transfer playback to a different Device.

        Args:
            device (Device): The Device to transfer playback to.
        """
        data = {"device_ids": [device['id']],
                "play": True}
        self.put_api_v1("me/player", data=data)

    @async
    def pause(self):
        """Pause the player."""
        self.put_api_v1("me/player/pause")

    @async
    def next(self):
        """Play the next song."""
        self.post_api_v1("me/player/next")

    @async
    def previous(self):
        """Play the previous song."""
        self.post_api_v1("me/player/previous")

    @async
    def shuffle(self, shuffle):
        """Set the player to shuffle.

        Args:
            shuffle (bool): Whether to shuffle or not.
        """
        q = urllib.urlencode({"state": shuffle})
        url = "me/player/shuffle"
        self.put_api_v1(url, q)

    @async
    def repeat(self, repeat):
        """Set the player to repeat.

        Args:
            repeat (bool): Whether to repeat or not.
        """
        q = urllib.urlencode({"state": repeat})
        url = "me/player/repeat"
        self.put_api_v1(url, q)

    @async
    def volume(self, volume):
        """Set the player volume.

        Args:
            volume (int): Volume level. 0 - 100 (inclusive).
        """
        q = urllib.urlencode({"volume_percent": volume})
        url = "me/player/volume"
        self.put_api_v1(url, q)

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

    def get_devices(self):
        """Return a list of devices with Spotify players running.

        Returns:
            list: The Devices.
        """
        results = self.get_api_v1("me/player/devices")
        if results and "devices" in results:
            return tuple(Device(device) for device in results['devices'])
        else:
            return []

    def search(self, types, query, limit=20):
        """Calls Spotify's search api.

        Args:
            types (tuple): Strings of the type of search (i.e, 'artist',
                'track', 'album')
            query (str): The search query.
            limit (int): Limit of the amount of results to return per
                type of search in 'types'.

        Returns:
            dict: Collection of Artist, Album, and Track objects.
        """
        type_str = ",".join(types)
        params = {'type': type_str,
                  'q': query,
                  'limit': limit}

        results = self.get_api_v1("search", params)

        cast = {
            'artists': Artist,
            'tracks': Track,
            'albums': Album,
        }

        combined = []
        if results:
            for type in types:
                # Results are plural (i.e, 'artists', 'albums', 'tracks')
                type = type + 's'
                combined.extend([cast[type](info) for info in results[type]['items']])

        return combined

    @uri_cache
    def get_albums_from_artist(self, artist,
                               type=("album", "single", "appears_on", "compilation"),
                               market=common.get_default_market()):
        """Get Albums from a certain Artist.

        Args:
            artist (Artist): The Artist.
            type (iter): Which types of albums to return.

        Returns:
            tuple: The Albums.
        """
        q = {"include_groups": ",".join(type),
             "market": market,
             "limit": 50}
        url = "artists/{}/albums".format(artist['id'])
        page = self.get_api_v1(url, q)
        albums = self.extract_page(page)

        return tuple(Album(album) for album in albums)

    @uri_cache
    def get_top_tracks_from_artist(self, artist, market=common.get_default_market()):
        """Get top tracks from a certain Artist.

        This also returns a pseudo-track to play the Artist context.

        Args:
            artist (Artist): The Artist to get Tracks from.

        Returns:
            tuple: The Tracks.
        """
        q = {"country": market}
        url = "artists/{}/top-tracks".format(artist['id'])
        result = self.get_api_v1(url, q)

        if result:
            return tuple(Track(t) for t in result["tracks"])
        else:
            return []

    @uri_cache
    def get_selections_from_artist(self, artist, progress=None):
        """Return the selection from an Artist.

        This includes the top tracks and albums from the artist.

        Args:
            artist (Artist): The Artist.
            progress (Progress): Progress associated with this call.

        Returns:
            iter: The Tracks and Albums.
        """
        selections = []

        selections.extend(self.get_top_tracks_from_artist(artist))
        if selections:
            progress.set_percent(0.5)

        selections.extend(self.get_albums_from_artist(artist))
        if progress:
            progress.set_percent(1)

        return selections

    @uri_cache
    def get_all_tracks_from_artist(self, artist, progress=None):
        """Return all tracks from an Artist.

        This includes the top tracks and albums from the artist.

        Args:
            artist (Artist): The Artist.
            progress (Progress): Progress associated with this call.

        Returns:
            iter: The Tracks.
        """
        albums = self.get_albums_from_artist(artist)
        if albums:
            n = len(albums)
            tracks = []
            for i, a in enumerate(albums):
                for t in self.get_tracks_from_album(a):
                    tracks.append(Track(t))
                if progress:
                    progress.set_percent(float(i)/n)
            tracks = (t for t in tracks if artist['name'] in str(t))
            return tuple(tracks)

    @uri_cache
    def get_tracks_from_album(self, album, progress=None):
        """Get Tracks from a certain Album.

        Args:
            album (Album): The Album to get Tracks from.

        Returns:
            tuple: The Tracks.
        """
        q = {"limit": 50}
        url = "albums/{}/tracks".format(album['id'])
        page = self.get_api_v1(url, q)
        tracks = []
        for track in self.extract_page(page, progress):
            track['album'] = album
            tracks.append(Track(track))
        return tuple(tracks)

    @uri_cache
    def get_tracks_from_playlist(self, playlist, progress=None):
        """Get Tracks from a certain Playlist.

        Args:
            playlist (Playlist): The Playlist to get Tracks from.
            progress (Progress): Progress associated with this call.

        Returns:
            tuple: The Tracks.
        """
        # Special case for the "Saved" Playlist
        if playlist['uri'] == common.SAVED_TRACKS_CONTEXT_URI:
            return self._get_saved_tracks(progress)
        else:
            q = {"limit": 50}
            url = "users/{}/playlists/{}/tracks".format(playlist['owner']['id'],
                                                         playlist['id'])
            page = self.get_api_v1(url, q)
            result = [Track(track["track"]) for track in self.extract_page(page, progress)]

        return tuple(result)

    def add_track_to_playlist(self, track, playlist):
        """Add a Track to a Playlist.

        Args:
            track (Track): The Track to add.
            playlist (Playlist): The Playlist to add the Track to.

        Returns:
            tuple: The new set of Tracks with the new Track added.
        """
        # Add the track.
        if playlist['uri'] == common.SAVED_TRACKS_CONTEXT_URI:
            q = {"ids": [track['id']]}
            url = "me/tracks"
            self.put_api_v1(url, q)
        else:
            q = {"uris": [track['uri']]}
            url = "playlists/{}/tracks".format(playlist['id'])
            self.post_api_v1(url, q)

        # Clear out current Cache.
        return self.get_tracks_from_playlist(playlist, force_clear=True)

    def _get_saved_tracks(self, progress=None):
        """Get the Tracks from the "Saved" songs.

        Args:
            progress (Progress): Progress associated with this call.

        Returns:
            tuple: The Tracks.
        """
        q = {"limit": 50}
        url = "me/tracks"
        page = self.get_api_v1(url, q)
        return tuple(Track(saved["track"]) for saved in self.extract_page(page, progress))

    def get_user(self, user_id):
        """Return a User from an id.

        Args:
            user_id (str): The user id.

        Returns:
            User: The User.
        """
        result = self.get_api_v1("users/{}".format(user_id))
        if result:
            return User(result)
        else:
            return {}

    @uri_cache
    def get_user_playlists(self, user, progress=None):
        """Get the Playlists from the current user.

        Args:
            user (User): The User.
            progress (Progress): Progress associated with this call.

        Return:
            tuple: The Playlists.
        """
        q = {"limit": 50}
        url = "users/{}/playlists".format(user['id'])
        page = self.get_api_v1(url, q)
        return tuple([Playlist(p) for p in self.extract_page(page, progress)])

    def extract_page(self, page, progress=None):
        """Extract all items from a page.

        Args:
            page (dict): The page object.
            progress (Progress): Progress associated with this call.

        Returns:
            list: All of the items.
        """

        if page and "items" in page:
            i, n = 0, page['total']
            lists = []
            lists.extend(page['items'])
            while page['next'] is not None:
                page = self.get_api_v1(page['next'].split('/v1/')[-1])
                lists.extend(page['items'])
                if progress:
                    progress.set_percent(float(len(lists))/n)
            return lists
        else:
            return {}

    @needs_authentication
    def get_api_v1(self, endpoint, params=None):
        """Spotify v1 GET request.

        Args:
            endpoint (str): The API endpoint.
            params (dict): Query parameters (Default is None).

        Returns:
            dict: The JSON information.
        """
        headers = {"Authorization": "%s %s" % (self.auth.token_type, self.auth.access_token)}
        url = "https://api.spotify.com/v1/{}".format(endpoint)
        resp = requests.get(url, params=params, headers=headers)
        self.check_response(resp)

        data = json.loads(common.ascii(resp.text)) if resp.text else {}
        if not data:
            logger.info("GET return no data")

        return data

    @needs_authentication
    def put_api_v1(self, endpoint, params=None, data=None):
        """Spotify v1 PUT request.

        Args:
            endpoint (str): The API endpoint.
            params (dict): Query parameters (Default is None).
            data (dict): Body data(Default is None).

        Returns:
            Reponse: The HTTP Reponse.
        """
        headers = {"Authorization": "%s %s" % (self.auth.token_type, self.auth.access_token),
                   "Content-Type": "application/json"}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        resp = requests.put(api_url, headers=headers, params=params, json=data)
        self.check_response(resp)
        return resp

    @needs_authentication
    def post_api_v1(self, endpoint, params=None):
        """Spotify v1 POST request.

        Args:
            endpoint (str): The API endpoint.
            params (dict): Query parameters (Default is None).

        Returns:
            Reponse: The HTTP Reponse.
        """
        headers = {"Authorization": "%s %s" % (self.auth.token_type, self.auth.access_token),
                   "Content-Type": "application/json"}
        api_url = "https://api.spotify.com/v1/{}".format(endpoint)
        resp = requests.post(api_url, headers=headers, params=params)
        self.check_response(resp)
        return common.ascii(resp.text)

    def check_response(self, resp):
        """Check a HTTP Reponse.

        Args:
            resp (Reponse): The Reponse to check.
        """
        resp.raise_for_status()

