import unicurses as uc
import string

from util import *
from globals import *


logger = logging.getLogger(__name__)


class SpotifyObject(object):
    """A SpotifyObject represents a collection of data in Spotify."""

    def __init__(self, info):
        self.info = info

    def __getitem__(self, key):
        return self.info[key]

    def __setitem__(self, key, value):
        self.info[key] = value


class Playlist(SpotifyObject):
    """Represents a Spotify Playlist."""

    def __init__(self, playlist):
        super(Playlist, self).__init__(playlist)

    def __str__(self):
        return ascii(self.info['name'])

    def str(self, cols):
        return self.__str__()


class Track(SpotifyObject):
    """Represents a Spotify Track."""

    def __init__(self, track):
        super(Track, self).__init__(track)
        self.track_tuple = (ascii(track['name']),
                            ascii(track['album']['name']),
                            ascii(", ".join(artist['name'] for artist in track['artists'])))
        self.track, self.album, self.artist = self.track_tuple

    def __str__(self):
        return "%s %s %s"%self.track_tuple

    def str(self, cols):
        nchrs = cols-3
        fmt = "%{0}s%{0}s%{0}s".format(nchrs/3)
        return fmt%(self.track_tuple[0][0:nchrs/3-2],
                    self.track_tuple[1][0:nchrs/3-2],
                    self.track_tuple[2][0:nchrs/3-2])

NoneTrack = Track({"name":"None",
                   "artists":[{"name":"None"}],
                   "album":{"name":"None"},
                   "progress_ms":0})


class Artist(SpotifyObject):
    def __init__(self, artist):
        super(Artist, self).__init__(artist)

    def __str__(self):
        return ascii(self.info['name'])

    def str(self, cols):
        return self.__str__()


class Album(SpotifyObject):
    def __init__(self, album):
        super(Album, self).__init__(album)

    def __str__(self):
        return ascii(self.info['name'])

    def str(self, cols):
        return self.__str__()


class PlayerAction(object):
    """Represents a media player action (pause, play, etc.)"""
    def __init__(self, title, action):
        self.title = title
        self.action = action

    def __str__(self):
        return self.title

    def str(self, cols):
        return self.__str__()



class List(object):
    """Represents a collection of selections."""

    def __init__(self, name=None):
        self.i = 0
        """Currently selected index."""

        self.list = tuple()
        """List of entries."""

        self.name = name
        """Name of List."""

        self.header = ""
        """Header."""

    def update_list(self, l):
        self.list = tuple(l)
        self.i = clamp(self.i, 0, len(self.list)-1)

    def current_entry(self):
        return self.list[self.i]

    def set_selection(self, i):
        self.i = clamp(i, 0, len(self.list)-1)

    def get_selection(self):
        return self.i

    def update_selection(self, delta):
        self.set_selection(self.i + delta)

    def increment_selection(self, amount=None):
        self.update_selection(amount or 1)

    def decrement_selection(self, amount=None):
        self.update_selection((-amount if amount else None) or -1)

    def __len__(self):
        return len(self.list)

    def __iter__(self):
        return self.list.__iter__()

    def __next__(self):
        return self.list.__next__()

    def __getitem__(self, i):
        return self.list[i]

    def __equals__(self, other_list):
        return this.name == other_list.name


class Model(object):

    def __init__(self, name, lists):
        self.name = name
        self.ordered_lists = lists
        self.lists = {l.name: l for l in lists}
        self.list_i = 0

    def decrement_list(self):
        self.list_i = clamp(self.list_i-1, 0, len(self.ordered_lists)-1)

    def increment_list(self):
        self.list_i = clamp(self.list_i+1, 0, len(self.ordered_lists)-1)

    def get_current_list(self):
        return self.ordered_lists[self.list_i]

    def get_current_list_entry(self):
        return self.get_current_list().current_entry()

    def get_list_current_entry_i(self, list_name):
        return self.lists[list_name].i

    def get_list(self, list_name):
        return self.lists[list_name]

    def set_current_list(self, list_name):
        self.list_i = self.ordered_lists.index(self.lists[list_name])

    def __getitem__(self, key):
        return self.lists[key]


class SpotifyState(object):
    """Represents the programs internal state of Spotify.

    User input will alter this state.
    """

    REPEAT_OFF, REPEAT_CONTEXT, REPEAT_TRACK = range(3)

    def __init__(self, api):
        self.api = api
        """Used ot make API calls."""

        self.env_info = {}
        """Environment information."""

        self.shortcuts = {}
        """Shorcuts."""

        self.main_model = Model("main",
                                [List("playlists"),
                                 List("tracks"),
                                 List("player")])

        self.search_model = Model("search",
                                  [List("results")])

        self.current_model = self.main_model

        self.previous_tracks = []

        self.paused = True
        """Whether the play is paused or not."""

        self.shuffle = False
        """Whether to shuffle or not."""

        self.volume = 0
        """Volume of the player."""

        self.repeat = self.REPEAT_CONTEXT
        """Whether to repeat or not. Default is context."""

        self.current_track = None

        self.creating_command = False
        self.command_cursor_i = 0
        self.command_query = []

        self.searching = False
        self.search_query = ""

        self.running = True

        self.commands = {
            "search": self._execute_search,
            "find": self._execute_find,
            "volume": self._execute_volume,
            "play": self._execute_play,
            "pause": self._execute_pause,
            "exit": self._execute_exit,
        }

        # Initialize some things.
        self.init()

    def configure(self):
        """Initializes the users settings based on the stermrc file"""
        try:
            rc_file = open(CONFIG_FILENAME,"r")
        except:
            print "No configuration file '%s'"%(CONFIG_FILENAME)
            return

        for line in rc_file:
            line = line.strip()
            line = line.split("#")[0] # Ignore comments
            if "<-" in line:
                toks = line.split("<-")
                if len(toks) != 2:
                    logger.error("Error in line: %s"%(line))
                    exit()
                self.env_info[toks[0]] = toks[1]
                continue
            elif "=" in line:
                toks = line.split("=")
                if len(toks) != 2:
                    logger.error("Error in line: %s"%(line))
                    exit()
                self.shortcuts[toks[0]] = toks[1]

    def init(self):
        # Configure from stermrc file
        self.configure()

        # Get the users playlists.
        # Get the playlists from the API and convert it to our Playlist objects.
        playlists = [Playlist(playlist)
                    for playlist in self.api.get_user_playlists()]

        saved = Playlist({"name": "Saved",
                          "uri": None,
                          "id": "",
                          "owner_id":""})
        playlists.insert(0, saved)
        self.main_model['playlists'].update_list(playlists)

        # Initialize track list to first playlist.
        self._select_playlist(self.main_model['playlists'][0])

        # Initialize PlayerActions
        self.main_model['player'].update_list([
                PlayerAction("(S)", self.toggle_shuffle),
                PlayerAction("<<", self.api.previous),
                PlayerAction("(P)", self.toggle_play),
                PlayerAction(">>", self.api.next),
                PlayerAction("(R)", self.toggle_repeat),
                PlayerAction("--", self.decrease_volume),
                PlayerAction("++", self.increase_volume),
            ])

        # Get current player state
        player = self.api.get_player_state()
        if not player:
            print("No Spotify player found.")
            print("Please open the Spotify app on your Desktop, mobile, etc.")
            print("before starting the terminal application.")
            exit(1)

        # Get the current track (if there is one)
        self.currently_playing_track = Track(player['item']) if player['item'] else NoneTrack

        repeat = {"off": self.REPEAT_OFF,
                  "track": self.REPEAT_TRACK,
                  "context": self.REPEAT_CONTEXT}[player['repeat_state']]
        self._set_repeat(repeat)

        self.shuffle = player['shuffle_state']

        self.paused = not player['is_playing']

        self.volume = player['device']['volume_percent']

    def get_username(self):
        return self.api.get_username()

    def is_creating_command(self):
        return self.creating_command

    def is_searching(self):
        return self.searching

    def get_command_query(self):
        return self.command_query

    def set_command_query(self, text):
        self.command_query = list(text)

    def is_running(self):
        return self.running

    def get_currently_playing_track(self):
        return self.currently_playing_track

    def poll_currently_playing_track(self):
        # TODO: Maybe instead we should raise an exception with empty content
        track = self.api.get_currently_playing()
        if track:
            self.currently_playing_track = Track(track)

    def get_cursor_i(self):
        return self.command_cursor_i

    def process_key(self, key):
        self._process_key(key)
        self._clamp_values()

    def in_main_menu(self):
        return self.current_model.name == "main"

    def in_search_menu(self):
        return self.current_model.name == "search"

    def _process_key(self, key):
        # Left Key
        if key in [uc.KEY_LEFT, 391]:
            # Typing in a command -> move cursor left
            if self.is_creating_command():
                self.command_cursor_i -= 1
            else:
                if self.in_main_menu():
                    # In the Player section -> move selection left
                    if self.main_model.get_current_list().name == "player":
                        # At the first entry -> so move to previous section
                        if self.main_model["player"].get_selection() == 0:
                            self.main_model.decrement_list()
                        else:
                            self.main_model.get_current_list().decrement_selection()
                    # In another section -> move to previous section
                    else:
                        self.main_model.decrement_list()

        # Right Key
        elif key in [uc.KEY_RIGHT, 400]:
            if self.in_main_menu():
                # Same as Left Key but in the other direction
                if self.is_creating_command():
                    self.command_cursor_i += 1
                else:
                    if self.in_main_menu():
                        if self.main_model.get_current_list().name == "player":
                            self.main_model.get_current_list().increment_selection()
                        else:
                            self.main_model.increment_list()

            if self.in_search_menu():
                entry = self.search_model.get_current_list_entry()
                if isinstance(entry, Album):
                    self.searching = False
                    self._select_album(entry)


        # Up Key
        elif key in [uc.KEY_UP, 547]:
            if self.in_main_menu():
                # In the Player section -> move to previous section
                if self.main_model.get_current_list().name == "player":
                    self.main_model.decrement_list()
                # In another section -> Move selection up
                else:
                   self.main_model.get_current_list().decrement_selection(10 if key == 547 else None)

            if self.in_search_menu():
                self.search_model.get_current_list().decrement_selection()

        # Down Key
        elif key in [uc.KEY_DOWN, 548]:
            if self.in_main_menu():
                # Same as Up but in other sirection
                if self.main_model.get_current_list().name == "player":
                    self.main_model.increment_list()
                elif self.main_model.get_current_list().name == "tracks":
                    # Last selection in Track section -> Move to next section
                    if self.main_model.get_list_current_entry_i("tracks") == len(self.main_model.get_list("tracks"))-1:
                        self.main_model.increment_list()
                    # Not last selection -> Move selection down
                    else:
                        self.main_model.get_current_list().increment_selection(10 if key == 548 else None)
                else:
                    self.main_model.get_current_list().increment_selection(10 if key == 548 else None)
            elif self.in_search_menu():
                self.search_model.get_current_list().increment_selection()

        # Backspace
        elif key in [uc.KEY_BACKSPACE, 8]:
            # Creating a command -> Treat as a normal backspace
            if self.is_creating_command():
                if self.command_cursor_i > 0:
                    self.get_command_query().pop(self.command_cursor_i-1)
                    self.command_cursor_i-=1
                # No text to delete -> Stop creating command
                else:
                    self.creating_command = False

            if self.in_main_menu():
                if self.previous_tracks:
                    header, tracks = self.previous_tracks.pop()
                    self._register_tracks(tracks)
                    self.main_model.get_list('tracks').header = header

        # ASCII character pressed
        elif 0 <= key <= 256:
            # Convert to character
            char = chr(key)

            # Creating a command -> Construct text
            if self.is_creating_command():
                if 32 <= key and key <= 126:
                    self.get_command_query().insert(self.command_cursor_i, char)
                    self.command_cursor_i += 1
                    return

            if char in ['/', ':', '#']:
                # Start creating command
                if not self.is_creating_command():
                    self.set_command_query(char)
                    self.command_cursor_i = 1
                    self.creating_command = True
                    return

            if char == "n":
                if self.prev_command[0] in ["find", "playlist"]:
                    i = int(self.prev_command[1])
                    command = self.prev_command
                    command[1] = str(i+1)
                    self._process_command(" ".join(command))

            if char == "p":
                if self.prev_command[0] in ["find", "playlist"]:
                    i = int(self.prev_command[1])
                    command = self.prev_command
                    command[1] = str(i-1)
                    self._process_command(" ".join(command))

            # Hit enter.
            if key in [13, 10]:
                if self.is_creating_command():
                    self._process_command(self.get_command_query())
                elif self.in_search_menu():
                    entry = self.search_model.get_current_list_entry()
                    if isinstance(entry, Artist):
                        albums = self.api.get_albums_from_artist(entry)
                        self.search_model['results'].update_list(albums)
                    elif isinstance(entry, Album):
                        self.searching = False
                        self._select_album(entry)
                        self.api.play(None, context_uri=entry['uri'])
                    elif isinstance(entry, Track):
                        self.searching = False
                        self.api.play(entry['uri'], context_uri=None)
                elif self.in_main_menu():
                    # Playlist was selected.
                    if self.main_model.get_current_list().name == "playlists":
                        # Playlist selected
                        playlist = self.main_model.get_current_list_entry()
                        self._select_playlist(playlist)

                    # Track was selected
                    elif self.main_model.get_current_list().name == "tracks":
                        # Track selected
                        track = self.main_model.get_current_list_entry()
                        self.api.play(track['uri'], context_uri=self.context)

                    # PlayerAction was selected
                    elif self.main_model.get_current_list().name == "player":
                        self.main_model.get_current_list_entry().action()

            # Hit space -> Toggle play
            if char == " ":
                self.toggle_play()
        #else:
        #    raise Exception(key)

        if self.is_searching():
            self.current_model = self.search_model
        else:
            self.current_model = self.main_model


    def _clamp_values(self):
        # Clamp values.
        self.command_cursor_i = clamp(self.command_cursor_i,
                                      0, len(self.get_command_query()))

    def _process_command(self, command_input):
        logger.debug("Processing command: %s", command_input)

        # Convert everything to string first
        if not isinstance(command_input, basestring):
            command_input = "".join(command_input).strip()

        # Convert special commands.
        if command_input[0] == ":":
            if command_input == ":":
                return
            elif command_input == ":q":
                command_input = "exit"
            else:
                command_input = command_input[1::]
        elif command_input[0] == "#":
            if command_input == "#":
                return
            else:
                command_input = "search {}".format(command_input[1::])
        elif command_input[0] == "/":
            command_input = "find 0 {}".format(command_input[1::])

        # Get tokens
        toks = command_input.split()

        # Get the command.
        command = toks[0]
        if command not in self.commands:
            return

        logger.debug("Final command: %s", toks)

        # Get the arguments for the command.
        command_args = toks[1::] if len(toks) > 1 else []

        # Save as the last command.
        self.prev_command = toks

        # Execute the appropriate command.
        self.commands[command](*command_args)
        self.creating_command = False

    def _execute_search(self, *query):
        query = " ".join(query)
        logger.debug("search %s", query)
        results = self.api.search(("artists","tracks","albums"), query)
        self.search_model["results"].update_list(results)
        self.searching = True

    def _execute_find(self, i, *query):
        query = " ".join(query)
        logger.debug("find:%s", query)
        cur_list = self.current_model.get_current_list()

        i = int(i) % len(cur_list)

        found = -1
        for index, item in enumerate(cur_list):
            logger.debug("(%s) in (%s)", query.lower(), str(item).lower())
            if query.lower() in str(item).lower():
                found += 1
            if found == i:
                self.main_model.get_current_list().set_selection(index)
                return

    def _execute_volume(self, volume):
        volume = int(volume)
        self.volume = clamp(volume, 0, 100)
        self.api.volume(self.volume)

    def _execute_play(self):
        self.paused = False
        self.api.play(None, None)

    def _execute_pause(self):
        self.paused = True
        self.api.pause()

    def _execute_exit(self):
        self.running = False

    def _select_playlist(self, playlist):
        self.context = playlist['uri']
        self.main_model.set_current_list('tracks')
        self.main_model.get_current_list().set_selection(0)
        self._register_tracks(self.api.get_tracks_from_playlist(playlist))
        self.main_model.get_list('tracks').header = playlist['name']

    def _select_album(self, album):
        self.context = album['uri']
        self.main_model.set_current_list('tracks')
        self.main_model.get_current_list().set_selection(0)
        self._register_tracks(self.api.get_tracks_from_album(album))
        self.main_model.get_list('tracks').header = album['name']

    def _register_tracks(self, tracks):
        if self.main_model.get_list('tracks').list:
            self.previous_tracks.append((self.main_model.get_list('tracks').header,
                                         self.main_model.get_list('tracks').list))
        self.main_model.get_list('tracks').update_list(tracks)

    def _set_repeat(self, state):
        self.repeat = state
        self.main_model.get_list('player')[4].title = "({})".format(['x','o','1'][self.repeat])

    def toggle_play(self):
        if self.paused:
            self._process_command("play")
        else:
            self._process_command("pause")

    def toggle_shuffle(self):
        # TODO: convert to command
        self.shuffle = not self.shuffle
        self.api.shuffle(self.shuffle)

    def toggle_repeat(self):
        # TODO: convert to commmand
        self._set_repeat((self.repeat+1)%3)
        self.api.repeat(['off', 'context', 'track'][self.repeat])

    def decrease_volume(self):
        self._process_command("volume {}".format(self.volume - 5))

    def increase_volume(self):
        self._process_command("volume {}".format(self.volume + 5))

