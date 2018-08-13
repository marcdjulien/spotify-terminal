from threading import Lock, Thread
import unicurses as uc

from model import (
    UnableToFindDevice,
    NoneTrack,
    Playlist,
    PlayerAction,
    Track,
    Device
)
import common


logger = common.logging.getLogger(__name__)


class List(object):
    """Represents a list of selectable items.

    Spotify Terminal treats most things as a list
    that the user traverses through to make actions.
    """

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
        """Update the list.

        Args:
            l (iter): The list ot update to.
        """
        self.list = tuple(l)
        self.i = 0

    def current_entry(self):
        """Return the currently selected entry.

        Returns:
            object: The currently selected entry.
        """
        return self.list[self.i] if self.list else None

    def set_index(self, i):
        """Set the selection to 'i'.

        Args:
            i (int): The index.
        """
        self.i = common.clamp(i, 0, len(self.list) - 1)

    def get_index(self):
        """Get the current index.

        Returns:
            int: The index.
        """
        return self.i

    def update_index(self, delta):
        """Set the index to the current index + delta.

        Args:
            delta (int): The delta.
        """
        self.set_index(self.i + delta)

    def increment_index(self, amount=None):
        self.update_index(amount or 1)

    def decrement_index(self, amount=None):
        self.update_index((-amount if amount else None) or -1)

    def __len__(self):
        return len(self.list)

    def __iter__(self):
        return self.list.__iter__()

    def __next__(self):
        return self.list.__next__()

    def __getitem__(self, i):
        return self.list[i]

    def __equals__(self, other_list):
        return self.name == other_list.name


class ListCollection(object):
    """A collection of Lists."""

    def __init__(self, name, lists):
        self.name = name
        self.ordered_lists = lists
        self.lists = {l.name: l for l in lists}
        self.list_i = 0

    def decrement_list(self):
        """Decrement the currently List."""
        self.list_i = common.clamp(self.list_i - 1, 0, len(self.ordered_lists) - 1)

    def increment_list(self):
        """Increment the currently List."""
        self.list_i = common.clamp(self.list_i + 1, 0, len(self.ordered_lists) - 1)

    def get_current_list(self):
        """Get the currently selected List.

        Returns:
            List: The current List.
        """
        return self.ordered_lists[self.list_i]

    def get_current_list_entry(self):
        """Return the current entry of the current list.

        Returns:
            object: The current entry.
        """
        return self.get_current_list().current_entry()

    def get_list(self, list_name):
        """Return a list byu its name.

        Args:
            list_name (str): The name of the list.

        Returns:
            List: The List with the requested name.
        """
        return self.lists[list_name]

    def set_current_list(self, list_name):
        """Set the current List by its name.

        Args:
            list_name (str): The name of the List to set.
        """
        self.list_i = self.ordered_lists.index(self.lists[list_name])

    def __getitem__(self, key):
        return self.lists[key]


def async(func):
    """Execute the function asynchronously."""

    @common.catch_exceptions
    def wrapper(*args, **kwargs):
        with args[0].lock:
            Thread(target=func, args=args, kwargs=kwargs).start()

    return wrapper


class SpotifyState(object):
    """Represents the programs internal state of Spotify and menus.

    User input will alter this state.
    """

    REPEAT_OFF, REPEAT_CONTEXT, REPEAT_TRACK = range(3)

    MAIN_MENU_STATE = "main_menu_state"

    SEARCH_MENU_STATE = "search_menu_state"

    PLAYER_MENU_STATE = "player_menu_state"

    EXIT_STATE = "exit_state"

    def __init__(self, api):
        self.lock = Lock()
        """Lock for the class."""

        self.api = api
        """SpotifyApi object to make Spotify API calls."""

        self.main_menu = ListCollection("main",
                                        [List("user"),
                                         List("tracks"),
                                         List("player")])

        self.search_menu = ListCollection("search",
                                          [List("search_results")])

        self.select_player_menu = ListCollection("select_player",
                                                 [List("players")])

        self.current_menu = self.main_menu
        """The current model that we are acting on."""

        self.previous_tracks = []
        """Keeps track of previously displayed Tracks."""

        self.current_context = None
        """The currently playing context."""

        self.current_device = UnableToFindDevice
        """The current Device."""

        self.paused = True
        """Whether the play is paused or not."""

        self.shuffle = False
        """Whether to shuffle or not."""

        self.volume = 0
        """Volume of the player."""

        self.repeat = self.REPEAT_CONTEXT
        """Whether to repeat or not. Default is context."""

        self.currently_playing_track = NoneTrack
        """The currently playing track."""

        self.command_cursor_i = 0
        """The cursor location of the command."""

        self.command_query = []
        """The command being typed."""

        self.command_history = []
        self.command_history_i = 0
        """History of commands."""

        self.running = True
        """Whether we're running or not."""

        self.player_state_synced = False
        """True if the Spotify player's state is synced to the application."""

        self.commands = {
            "search": self._execute_search,
            "find": self._execute_find,
            "volume": self._execute_volume,
            "play": self._execute_play,
            "pause": self._execute_pause,
            "shuffle": self._execute_shuffle,
            "repeat": self._execute_repeat,
            "exit": self._execute_exit
        }
        """Dictionary of commands and their execution functions."""

        self.current_state = self.MAIN_MENU_STATE
        """Current state of the applicaiton."""

        self.creating_command = False
        """Whether we're typing a command or not."""

        # Initialize the state.
        self.init()

    def init(self):
        # Get the User info.
        self.user = self.api.get_user(self.get_username())

        if not self.user:
            print("Could not load user {}".format(self.get_username()))
            exit(1)

        # Get the users playlists.
        playlists = self.api.get_user_playlists(self.user)
        if not playlists:
            print("Could not load playlists. Try again later.")
            exit(1)
        playlists = list(playlists)

        # Add the Saved tracks playlist.
        saved = Playlist({"name": "Saved",
                          "uri": common.SAVED_TRACKS_CONTEXT_URI,
                          "id": "",
                          "owner_id": self.get_username()})
        playlists.insert(0, saved)
        self.main_menu['user'].update_list(tuple(playlists))

        # Initialize track list to first playlist.
        self._set_playlist(self.main_menu['user'][0])

        # Initialize PlayerActions.
        self.main_menu['player'].update_list([
            PlayerAction("(S)", self._toggle_shuffle),
            PlayerAction("<< ", self.api.previous),
            PlayerAction("(P)", self._toggle_play),
            PlayerAction(" >>", self.api.next),
            PlayerAction("(R)", self._toggle_repeat),
            PlayerAction(" --", self._decrease_volume),
            PlayerAction(" ++", self._increase_volume),
        ])

        # Get current player state.
        self.sync_player_state()

    def _read_rc_file(self):
        """Initializes the users settings based on the stermrc file"""
        try:
            rc_file = open(common.CONFIG_FILENAME, "r")
        except IOError:
            logger.debug("No configuration file '%s'" % (common.CONFIG_FILENAME))
            return

        for line in rc_file:
            # Strip whitespace and comments.
            line = line.strip()
            line = line.split("#")[0]

    @async
    def sync_player_state(self):
        player_state = self.api.get_player_state()
        if player_state:
            self.currently_playing_track = Track(player_state['item']) \
                if player_state['item'] else NoneTrack
            self.paused = not player_state['is_playing']

            self.current_device = Device(player_state['device'])
            self.volume = self.current_device['volume_percent']

            self._set_repeat(player_state['repeat_state'])
            self._set_shuffle(player_state['shuffle_state'])

            self.player_state_synced = True
        else:
            self.currently_playing_track = NoneTrack
            self.player_state_synced = False

    def process_key(self, key):
        self._process_key(key)

        if self.in_search_menu():
            self.current_menu = self.search_menu
        elif self.in_select_player_menu():
            self.current_menu = self.select_player_menu
        else:
            self.current_menu = self.main_menu

        self._clamp_values()

    def _process_key(self, key):
        if key == uc.KEY_LEFT:
            if self.is_creating_command():
                self.command_cursor_i -= 1
            elif self.in_main_menu():
                if self.main_menu.get_current_list().name == "player":
                    if self.main_menu.get_current_list().get_index() == 0:
                        self.main_menu.list_i = 0
                    else:
                        self.main_menu.get_current_list().decrement_index()
                else:
                    self.main_menu.list_i = 0

        elif key == uc.KEY_RIGHT:
            if self.is_creating_command():
                self.command_cursor_i += 1
            elif self.in_main_menu():
                if self.main_menu.get_current_list().name == "player":
                    self.main_menu.get_current_list().increment_index()
                elif self.main_menu.get_current_list().name in ["user", "tracks"]:
                    self.main_menu.increment_list()
            elif self.in_search_menu():
                entry = self.search_menu.get_current_list_entry()
                if entry['type'] == 'album':
                    self.current_state = self.MAIN_MENU_STATE
                    self._set_album(entry)
                elif entry['type'] == 'artist':
                    albums = self.api.get_albums_from_artist(entry)
                    if albums:
                        self.search_menu['results'].update_list(albums)

        elif key == uc.KEY_UP:
            if self.is_creating_command():
                if self.command_history:
                    self.command_history_i = common.clamp(self.command_history_i-1,
                                                          0,
                                                          len(self.command_history)-1)
                    self._set_command_query(self.command_history[self.command_history_i])
            elif self.in_main_menu():
                if self.main_menu.get_current_list().name == "player":
                    self.main_menu.decrement_list()
                else:
                    self.main_menu.get_current_list().decrement_index()
            elif self.in_search_menu() or self.in_select_player_menu():
                self.current_menu.get_current_list().decrement_index()

        elif key == uc.KEY_DOWN:
            if self.is_creating_command():
                if self.command_history:
                    self.command_history_i = common.clamp(self.command_history_i+1,
                                                          0,
                                                          len(self.command_history)-1)
                    self._set_command_query(self.command_history[self.command_history_i])
            elif self.in_main_menu():
                if self.main_menu.get_current_list().name == "player":
                    self.main_menu.increment_list()
                elif self.main_menu.get_current_list().name == "tracks":
                    if self.main_menu["tracks"].i == len(self.main_menu.get_list("tracks")) - 1:
                        self.main_menu.increment_list()
                    else:
                        self.main_menu.get_current_list().increment_index()
                else:
                    self.main_menu.get_current_list().increment_index()
            elif self.in_search_menu() or self.in_select_player_menu():
                self.current_menu.get_current_list().increment_index()

        elif key == uc.KEY_BACKSPACE:
            if self.is_creating_command():
                if self.command_cursor_i > 0:
                    self.get_command_query().pop(self.command_cursor_i - 1)
                    self.command_cursor_i -= 1
                else:
                    self.current_state = self.MAIN_MENU_STATE
            elif self.in_main_menu():
                if self.previous_tracks:
                    header, tracks, context = self.previous_tracks.pop()
                    self.current_context = context
                    self._set_tracks(tracks, save_list=False)
                    self.main_menu.get_list('tracks').header = header
            elif self.in_search_menu():
                self.current_state = self.MAIN_MENU_STATE
            elif self.in_select_player_menu():
                self.current_state = self.MAIN_MENU_STATE

        # ASCII character pressed
        elif 0 <= key <= 256:
            char = chr(key)

            if self.is_creating_command():
                if 32 <= key and key <= 126:
                    self.get_command_query().insert(self.command_cursor_i, char)
                    self.command_cursor_i += 1
                elif key in [uc.KEY_ENTER, 10, 13]:
                    self._process_command(self.get_command_query())
                return

            elif key in [uc.KEY_EXIT, 27]:
                if self.in_search_menu():
                    self.current_state = self.MAIN_MENU_STATE
                elif self.in_select_player_menu():
                    self.current_state = self.MAIN_MENU_STATE
                elif self.is_creating_command():
                    self.current_state = self.MAIN_MENU_STATE

            elif char in ['/', ':', '"']:
                # Start creating command
                if not self.is_creating_command():
                    if char == '"':
                        self._set_command_query("\"\"")
                        self.command_cursor_i = 1
                    else:
                        self._set_command_query(char)
                        self.command_cursor_i = 1
                    self.creating_command = True

            elif char == "n":
                if self.prev_command[0] in ["find"]:
                    i = int(self.prev_command[1])
                    command = self.prev_command
                    command[1] = str(i + 1)
                    self._process_command(" ".join(command))

            elif char == "p":
                if self.prev_command[0] in ["find"]:
                    i = int(self.prev_command[1])
                    command = self.prev_command
                    command[1] = str(i - 1)
                    self._process_command(" ".join(command))

            elif char == 'W':
                self.current_state = self.PLAYER_MENU_STATE
                devices = self.api.get_devices()
                self.select_player_menu['players'].update_list(devices)

            elif char == 'R':
                self.sync_player_state()

            elif char == 'D':
                entry = self.current_menu.get_current_list_entry()
                if entry['type'] == 'track':
                    artist = entry['artists'][0]
                    self._set_artist(artist)

            elif char == 'S':
                entry = self.current_menu.get_current_list_entry()
                if entry['type'] == 'track':
                    album = entry['album']
                    self._set_album(album)
                elif entry['type'] == 'album':
                    self._set_album(entry)

            elif char == " ":
                self._toggle_play()

            elif char == ">":
                self.api.next()

            elif char == "<":
                self.api.previous()

            elif char in ["~", "!", "@", "#", "$", "%", "^", "&", "*", "(", ")"]:
                volume = {
                    "~": 0, "!": 10, "@": 20, "#": 30, "$": 40, "%": 50, "^": 60, "&": 70,
                    "*": 80, "(": 90, ")": 100
                }[char]
                self._process_command("volume {}".format(volume))

            elif char == "_":
                self._process_command("volume {}".format(self.volume - 1))

            elif char == "+":
                self._process_command("volume {}".format(self.volume + 1))

            elif key in [uc.KEY_ENTER, 10, 13]:
                if self.in_search_menu():
                    entry = self.search_menu.get_current_list_entry()
                    if entry:
                        if entry['type'] == 'artist':
                            self._set_artist(entry)
                        elif entry['type'] == 'album':
                            self._set_album(entry)
                        elif entry['type'] == 'track':
                            self._play(entry['uri'], context=None)
                    self.current_state = self.MAIN_MENU_STATE

                elif self.in_main_menu():
                    if self.main_menu.get_current_list().name == "user":
                        playlist = self.main_menu.get_current_list_entry()
                        if playlist:
                            self._set_playlist(playlist)
                    elif self.main_menu.get_current_list().name == "tracks":
                        entry = self.main_menu.get_current_list_entry()
                        if entry:
                            if entry['type'] == 'artist':
                                self._set_artist(entry)
                            elif entry['type'] == 'album':
                                self._set_album(entry)
                            elif entry['type'] == 'track':
                                self._play(entry['uri'], context=self.current_context)
                    elif self.main_menu.get_current_list().name == "player":
                        self.main_menu.get_current_list_entry().action()

                elif self.in_select_player_menu():
                    current_device = self.select_player_menu.get_current_list_entry()
                    if current_device:
                        self.current_device = current_device
                        self.api.transfer_playback(self.current_device)
                        self.current_state = self.MAIN_MENU_STATE

        else:
            logger.debug("Unregistered key: %d", key)

        logger.debug("Key: %d", key)
    def _clamp_values(self):
        self.command_cursor_i = common.clamp(self.command_cursor_i,
                                             0,
                                             len(self.get_command_query()))

    def _process_command(self, command_input):
        logger.debug("Processing command: %s", command_input)

        # Convert everything to string first
        if not isinstance(command_input, basestring):
            command_input = "".join(command_input).strip()

        if not command_input:
            self.creating_command = False
            return

        # Convert special commands.
        if command_input[0] == ":":
            if command_input == ":":
                self.creating_command = False
                return
            elif command_input.lower() == ":q":
                command_string = "exit"
            else:
                command_string = command_input[1::]
        elif command_input[0] == '"':
            if command_input == '"' or command_input == '""':
                self.creating_command = False
                return
            else:
                command_string = "search {}".format(command_input[1::])
                if command_string[-1] == '"':
                    command_string = command_string[:-1]
        elif command_input[0] == "/":
            command_string = "find 0 {}".format(command_input[1::])
        else:
            command_string = command_input

        # Get tokens
        toks = command_string.split()

        # Get the command.
        command = toks[0]

        # Execute the command if it exists.
        if command not in self.commands:
            logger.debug("%s is not a valid command", command)
        else:
            logger.debug("Final command: %s", toks)
            # Get the arguments for the command.
            command_args = toks[1::] if len(toks) > 1 else []

            # Save as the last command.
            self.prev_command = toks

            # Execute the appropriate command.
            self.commands[command](*command_args)

        self.command_history.append(command_input)
        self.command_history_i = len(self.command_history)
        self.creating_command = False

    def _execute_search(self, *query):
        query = " ".join(query)
        logger.debug("search %s", query)
        results = self.api.search(("artist", "album", "track"), query)
        if results:
            self.search_menu["search_results"].update_list(results)
            self.search_menu["search_results"].header = "Search results for \"{}\"".format(query)
        else:
            self.search_menu["search_results"].update_list([])
            self.search_menu["search_results"].header = "No results found for \"{}\"".format(query)

        self.current_state = self.SEARCH_MENU_STATE

    @async
    def _execute_find(self, i, *query):
        query = " ".join(query)
        logger.debug("find:%s", query)
        cur_list = self.current_menu.get_current_list()

        found = []
        for index, item in enumerate(cur_list):
            if query.lower() in str(item).lower():
                found.append(index)

        if found:
            self.current_menu.get_current_list().set_index(found[int(i) % len(found)])

    @async
    def _execute_shuffle(self, state):
        state = state.lower().strip()
        state = True if state == "true" else False
        self._set_shuffle(state)
        self.api.shuffle(state)

    @async
    def _execute_repeat(self, state):
        state = state.lower().strip()
        if state in ["off", "context", "track"]:
            self._set_repeat(state)
            self.api.repeat(state)

    @async
    def _execute_volume(self, volume):
        volume = common.clamp(int(volume), 0, 100)
        if 0 <= volume and volume <= 100:
            self.volume = volume
            self.api.volume(self.volume)

    @async
    def _execute_play(self):
        self.paused = False
        self._play(None, None)

    @async
    def _execute_pause(self):
        self.paused = True
        self.api.pause()

    def _execute_exit(self):
        self.current_state = self.EXIT_STATE

    def _play(self, track, context):
        context_uri = None
        uris = None

        # The Saved Tracks playlist in Spotify doesn't have a Context.
        # So we have to give the API a list of Tracks to play
        # to mimic a context.
        if context:
            if context['uri'] == common.SAVED_TRACKS_CONTEXT_URI:
                uris = [t['uri'] for t in
                        self.api.get_tracks_from_playlist(self.main_menu['user'][0])]
                track = self.main_menu['tracks'].i

            elif context['type'] == 'artist':
                uris = [s['uri'] for s in
                        self.api.get_selections_from_artist(self.current_context)
                        if s['type'] == 'track']
                track = self.main_menu['tracks'].i
            else:
                context_uri = context['uri']

        self.api.play(track, context_uri, uris, self.current_device)

    def _toggle_play(self):
        if self.paused:
            self._process_command("play")
        else:
            self._process_command("pause")

    def _toggle_shuffle(self):
        self._process_command("shuffle {}".format(not self.shuffle))

    def _toggle_repeat(self):
        self._process_command("repeat {}".format(
            ['off', 'context', 'track'][(self.repeat + 1) % 3]
        ))

    def _decrease_volume(self):
        self._process_command("volume {}".format(self.volume - 5))

    def _increase_volume(self):
        self._process_command("volume {}".format(self.volume + 5))

    def _get_repeat_enum(self, repeat):
        return {"off": self.REPEAT_OFF,
                "track": self.REPEAT_TRACK,
                "context": self.REPEAT_CONTEXT}[repeat]

    def _set_playlist(self, playlist):
        tracks = self.api.get_tracks_from_playlist(playlist)
        if tracks:
            self._set_tracks(tracks, playlist)
            self.main_menu.get_list('tracks').header = playlist['name']

    def _set_artist(self, artist):
        self.current_state = self.MAIN_MENU_STATE
        selections = self.api.get_selections_from_artist(artist)
        if selections:
            self._set_tracks(selections, artist)
            self.main_menu.get_list('tracks').header = artist['name']

    def _set_album(self, album):
        self.current_state = self.MAIN_MENU_STATE
        tracks = self.api.get_tracks_from_album(album)
        if tracks:
            self._set_tracks(tracks, album)
            self.main_menu.get_list('tracks').header = album['name']

    def _set_tracks(self, tracks, context=None, save_list=True):
        self.main_menu.set_current_list('tracks')
        self.main_menu.get_list('tracks').set_index(0)

        if save_list and self.main_menu.get_list('tracks').list:
            self.previous_tracks.append((self.main_menu.get_list('tracks').header,
                                         self.main_menu.get_list('tracks').list,
                                         self.current_context))

        self.current_context = context
        self.main_menu.get_list('tracks').update_list(tracks)

    def _set_command_query(self, text):
        self.command_query = list(text)

    def _set_repeat(self, state):
        self.repeat = self._get_repeat_enum(state)
        self.main_menu.get_list('player')[4].title = "({})".format(['x', 'o', '1'][self.repeat])

    def _set_shuffle(self, state):
        self.shuffle = state
        self.main_menu.get_list('player')[0].title = "({})".format(
            {True: "S", False: "s"}[self.shuffle]
        )

    def is_creating_command(self):
        return self.creating_command

    def in_search_menu(self):
        return self.current_state == self.SEARCH_MENU_STATE

    def in_main_menu(self):
        return self.current_state == self.MAIN_MENU_STATE

    def in_select_player_menu(self):
        return self.current_state == self.PLAYER_MENU_STATE

    def is_running(self):
        return self.current_state != self.EXIT_STATE

    def poll_currently_playing_track(self):
        track = self.api.get_currently_playing()
        if track != NoneTrack:
            self.currently_playing_track = track

    def get_cursor_i(self):
        return self.command_cursor_i

    def get_username(self):
        return self.api.get_username()

    def get_command_query(self):
        return self.command_query

    def get_currently_playing_track(self):
        return self.currently_playing_track
