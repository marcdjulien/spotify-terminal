import copy

from . import common

logger = common.logging.getLogger(__name__)


class SpotifyObject(object):
    """A SpotifyObject represents a collection of data in Spotify."""

    def __init__(self, info):
        self.info = copy.deepcopy(info)

    def __getitem__(self, key):
        item = self.info[key]
        if isinstance(item, str):
            return item or "[Unable to Render]"
        else:
            return item

    def __setitem__(self, key, value):
        self.info[key] = value

    def get(self, key, default=None):
        return self.info.get(key, default)

    def str(self, cols):
        return str(self)


class User(SpotifyObject):
    """Represents a Spotify user"""


class Playlist(SpotifyObject):
    """Represents a Spotify Playlist."""

    def __str__(self):
        return self['name']


class Artist(SpotifyObject):
    """Represents a Spotify Artist."""

    def __init__(self, artist):
        super(Artist, self).__init__(artist)

    def __str__(self):
        return self['name']

    def str(self, cols):
        fmt = "%{0}.{0}s".format(cols)
        return fmt % self['name']


class Track(SpotifyObject):
    """Represents a Spotify Track."""

    def __init__(self, track):
        super(Track, self).__init__(track)
        # Convert the Artists
        self['artists'] = [Artist(a) for a in self['artists']]

        self.track_tuple = (self['name'],
                            self['album']['name'],
                            ", ".join(artist['name'] for artist in self['artists']))
        self.track, self.album, self.artist = self.track_tuple

    def __str__(self):
        return "%s    %s    %s" % self.track_tuple

    def str(self, cols):
        # Account for 4 spaces.
        nchrs = cols - 4
        ar_chrs = nchrs//3
        al_chrs = nchrs//3
        tr_chrs = nchrs - al_chrs - ar_chrs
        fmt = "%{0}.{0}s  %{1}.{1}s  %{2}.{2}s".format(tr_chrs, al_chrs, ar_chrs)
        return fmt % (self.track_tuple[0],
                      self.track_tuple[1],
                      self.track_tuple[2])

    def __eq__(self, other_track):
        return str(self) == str(other_track)

NoneTrack = Track({"name": "---",
                   "artists": [{"name": "---"}],
                   "album": {"name": "---"}})


class Album(SpotifyObject):
    """Represents a Spotify Album."""

    def __init__(self, album):
        super(Album, self).__init__(album)
        self.artists = ", ".join(a['name'] for a in self['artists'])

        if "release_date" in self.info:
            year = self['release_date'][0:min(4, len(self['release_date']))]
        else:
            year = ""
        info = [self['album_type'].capitalize()]
        if year:
            info.append(year)

        self.extra_info = "[{}]".format(", ".join(info))

    def __str__(self):
        return "%s    %s    %s" % (self['name'],
                                  self.extra_info,
                                  self.artists)

    def str(self, cols):
        # Account for 4 spaces.
        nchrs = cols - 4
        tr_chrs = 2*nchrs//4
        ty_chrs = nchrs//4
        ar_chrs = nchrs - tr_chrs - ty_chrs
        fmt = "%{0}.{0}s  %{1}.{1}s  %{2}.{2}s".format(tr_chrs, ty_chrs, ar_chrs)
        return fmt % (self['name'], self.extra_info, self.artists)


class Device(SpotifyObject):
    """Represents a device with a Spotify player running."""

    def __str__(self):
        return "{}: {}".format(self['type'], self['name'])


UnableToFindDevice = Device({"type": "?",
                             "name": "Open the Devices menu to select a device.",
                             "id": None})


class PlayerAction(object):
    """Represents a media player action (pause, play, etc.)"""
    def __init__(self, title, action):
        self.title = title
        self.action = action

    def __str__(self):
        return self.title

    def str(self, cols):
        return self.__str__()


class Option(object):
    """A simple menu option."""

    def __init__(self, text):
        self.text = text

    def get(self):
        return self.text

    def __str__(self):
        return self.text

