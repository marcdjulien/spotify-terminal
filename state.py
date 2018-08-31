import os
import pickle
import re
from threading import Lock, Thread, Event

import unicurses as uc
from model import (
    UnableToFindDevice,
    NoneTrack,
    Playlist,
    PlayerAction,
    Track,
    Device,
    Option
)
import common


logger = common.logging.getLogger(__name__)


class SpotifyState(object):
    """Represents the programs internal state of Spotify and menus.

    User input will alter this state.
    """
    PICKLE_ATTRS = [
        "command_history",
        "previous_tracks",
        "current_context",
        "current_device"
    ]

    REPEAT_OFF, REPEAT_CONTEXT, REPEAT_TRACK = range(3)

    MAIN_MENU_STATE = "main_menu_state"

    SEARCH_MENU_STATE = "search_menu_state"

    PLAYER_MENU_STATE = "player_menu_state"

    LOAD_STATE = "load_state"

    EXIT_STATE = "exit_state"

    ADD_TO_PLAYLIST_SELECT = "add_to_playlist_select"

    ADD_TO_PLAYLIST_CONFIRM = "add_to_playlist_confirm"

    def __init__(self, api, config):
        self.lock = Lock()
        """Lock for the class."""

        self.api = api
        """SpotifyApi object to make Spotify API calls."""

        self.config = config
        """The Config parameters."""

        self.main_menu = ListCollection("main",
                                        [List("user"),
                                         List("tracks"),
                                         List("player")])

        self.search_menu = ListCollection("search",
                                          [List("search_results")])

        self.select_player_menu = ListCollection("select_player",
                                                 [List("players")])

        self.confirm_menu = ListCollection("confirm", [List("confirm")])

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

        self.futures = []
        """List of futures to execute."""

    def save_state(self):
        """Save the state to disk."""
        ps = {
            attr_name: getattr(self, attr_name)
            for attr_name in self.PICKLE_ATTRS
        }
        state_filename = common.get_file_from_cache(self.api.get_username(), "state")
        with open(state_filename, "wb") as file:
            logger.debug("Saving %s state", self.api.get_username())
            pickle.dump(ps, file)

    def load_state(self):
        """Load part of the state from disk."""
        state_filename = common.get_file_from_cache(self.api.get_username(), "state")
        if os.path.isfile(state_filename):
            with open(state_filename, "rb") as file:
                logger.debug("Loading %s state", self.api.get_username())
                ps = pickle.load(file)

            for attr in self.PICKLE_ATTRS:
                setattr(self, attr, ps[attr])

    def init(self):
        # Get the User info.
        self.user = self.api.get_user()

        if not self.user:
            print("Could not load user {}".format(self.api.get_username()))
            exit(1)

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

        self.confirm_menu['confirm'].update_list([Option("Yes"),
                                                  Option("No")])

        # Get current player state.
        self.sync_player_state()

        # Get the users playlists.
        playlists = self.api.get_user_playlists(self.user)
        if not playlists:
            print("Could not load playlists. Try again.")
            exit(1)
        playlists = list(playlists)

        # Add the Saved tracks playlist.
        saved = Playlist({"name": "Saved",
                          "uri": common.SAVED_TRACKS_CONTEXT_URI,
                          "id": "",
                          "owner_id": self.api.get_id()})
        playlists.insert(0, saved)
        self.main_menu['user'].update_list(tuple(playlists))

        # Initialize track list.
        if not self.restore_previous_tracks(0):
            logger.debug("Loading the last track list")
            self._set_playlist(self.main_menu['user'][0])

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
        else:
            self.currently_playing_track = NoneTrack
            self.current_device = UnableToFindDevice

    def process_key(self, key):
        # First check loading state.
        if self.is_loading():
            # Get the current Future.
            future = self.futures[0]

            # If it's done, leave the LOAD_STATE.
            # But if there are more Futures to execute, run them.
            if future.is_done():
                self.futures.pop(0)
                if not self.futures:
                    self.current_state = future.get_end_state()
                else:
                    self.futures[0].run()
            else:
                return

        if key:
            # Adding to a playlist
            if self.current_state == self.ADD_TO_PLAYLIST_SELECT:
                if key == uc.KEY_UP:
                    self.main_menu.get_list("user").decrement_index()
                elif key == uc.KEY_DOWN:
                    self.main_menu.get_list("user").increment_index()
                elif key in [uc.KEY_EXIT, 27]:
                    self.track_to_add = None
                    self.current_state = self.MAIN_MENU_STATE
                elif key in [uc.KEY_ENTER, 10, 13]:
                    self.playlist_to_add = self.main_menu.get_current_list_entry()
                    self.current_state = self.ADD_TO_PLAYLIST_CONFIRM
            elif self.current_state == self.ADD_TO_PLAYLIST_CONFIRM:
                if key == uc.KEY_LEFT:
                    self.confirm_menu.get_list("confirm").decrement_index()
                elif key == uc.KEY_RIGHT:
                    self.confirm_menu.get_list("confirm").increment_index()
                elif key in [uc.KEY_EXIT, 27]:
                    self.track_to_add = None
                    self.playlist_to_add = None
                    self.current_state = self.MAIN_MENU_STATE
                elif key in [uc.KEY_ENTER, 10, 13]:
                    entry = self.confirm_menu.get_current_list_entry()
                    if entry.get().lower() == "yes":
                        self._add_track_to_playlist(self.track_to_add, self.playlist_to_add)
                    else:
                        self.track_to_add = None
                        self.playlist_to_add = None
                        self.current_state = self.MAIN_MENU_STATE
            # In another menu.
            else:
                # Process keys.
                self._update_state(key)

                if self.in_search_menu():
                    self.current_menu = self.search_menu
                elif self.in_select_player_menu():
                    self.current_menu = self.select_player_menu
                else:
                    self.current_menu = self.main_menu

                self._clamp_values()

    def _update_state(self, key):
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
                    self.main_menu.get_current_list().increment_index()
                else:
                    self.main_menu.get_current_list().increment_index()
            elif self.in_search_menu() or self.in_select_player_menu():
                self.current_menu.get_current_list().increment_index()

        elif key in [uc.KEY_BACKSPACE, 8]:
            if self.is_creating_command():
                if self.command_cursor_i > 0:
                    self.get_command_query().pop(self.command_cursor_i - 1)
                    self.command_cursor_i -= 1
                else:
                    self.current_state = self.MAIN_MENU_STATE
                    self.creating_command = False
            elif self.in_main_menu():
                self.restore_previous_tracks()
            elif self.in_search_menu():
                self.current_state = self.MAIN_MENU_STATE
            elif self.in_select_player_menu():
                self.current_state = self.MAIN_MENU_STATE

        elif key == uc.KEY_NPAGE:
            if not self.is_creating_command():
                self.current_menu.get_current_list().increment_index(15)

        elif key == uc.KEY_PPAGE:
            if not self.is_creating_command():
                self.current_menu.get_current_list().decrement_index(15)

        # ASCII character pressed
        elif (0 <= key <= 256) or self.config.has_key(key):
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

            elif key == self.config.find_next:
                if self.prev_command[0] in ["find"]:
                    i = int(self.prev_command[1])
                    command = self.prev_command
                    command[1] = str(i + 1)
                    self._process_command(" ".join(command))

            elif key == self.config.find_previous:
                if self.prev_command[0] in ["find"]:
                    i = int(self.prev_command[1])
                    command = self.prev_command
                    command[1] = str(i - 1)
                    self._process_command(" ".join(command))

            elif key == self.config.add_track:
                entry = self.current_menu.get_current_list_entry()
                if entry['type'] == 'track':
                    self.track_to_add = entry
                    self.main_menu.set_current_list('user')
                    self.main_menu.get_list('user').set_index(0)
                    self.current_state = self.ADD_TO_PLAYLIST_SELECT

            elif key == self.config.show_devices:
                self.current_state = self.PLAYER_MENU_STATE
                devices = self.api.get_devices()
                self.select_player_menu['players'].update_list(devices)

            elif key == self.config.refresh:
                self.sync_player_state()

            elif key == self.config.goto_artist:
                entry = self.current_menu.get_current_list_entry()
                if entry['type'] == 'track':
                    artist = entry['artists'][0]
                    self._set_artist(artist)

            elif key == self.config.current_artist:
                entry = self.currently_playing_track
                if entry:
                    artist = entry['artists'][0]
                    self._set_artist(artist)

            elif key == self.config.goto_album:
                entry = self.current_menu.get_current_list_entry()
                if entry['type'] == 'track':
                    album = entry['album']
                    self._set_album(album)
                elif entry['type'] == 'album':
                    self._set_album(entry)

            elif key == self.config.current_album:
                entry = self.currently_playing_track
                if entry:
                    album = entry['album']
                    self._set_album(album)

            elif char == '\t':
                if self.current_context and self.current_menu.get_current_list().name == "tracks":
                    if common.is_all_tracks_context(self.current_context):
                        artist = self.current_context['artist']
                        self._set_artist(artist)
                    elif self.current_context.get("type") == "artist":
                        self._set_artist_all_tracks(self.current_context)

            elif key == self.config.play:
                self._toggle_play()

            elif key == self.config.next_track:
                self.api.next()

            elif key == self.config.previous_track:
                self.api.previous()

            elif self.config.is_volume_key(key):
                config_param = self.config.get_config_param(key)
                volume = 10*int(config_param.split("_")[1])
                self._process_command("volume {}".format(volume))

            elif key == self.config.volume_down:
                self._process_command("volume {}".format(self.volume - 5))

            elif key == self.config.volume_up:
                self._process_command("volume {}".format(self.volume + 5))

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
            elif command_input.lower().startswith(":q"):
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

    def _execute_shuffle(self, state):
        state = state.lower().strip()
        state = True if state == "true" else False
        self._set_shuffle(state)
        self.api.shuffle(state)

    def _execute_repeat(self, state):
        state = state.lower().strip()
        if state in ["off", "context", "track"]:
            self._set_repeat(state)
            self.api.repeat(state)

    def _execute_volume(self, volume):
        volume = common.clamp(int(volume), 0, 100)
        if 0 <= volume and volume <= 100:
            self.volume = volume
            self.api.volume(self.volume)

    def _execute_play(self):
        self.paused = False
        self._play(None, None)

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
            elif context.get('type') == 'artist':
                uris = [s['uri']
                        for s in self.api.get_selections_from_artist(self.current_context)
                        if s['type'] == 'track']
                track = self.main_menu['tracks'].i
            elif common.is_all_tracks_context(context):
                uris = [t['uri'] for t in self.main_menu['tracks'].list]
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

    def _add_track_to_playlist(self, track, playlist):
        self.api.add_track_to_playlist(track, playlist)
        self._set_playlist(playlist)

    def _set_playlist(self, playlist):
        future = Future(target=(self.api.get_tracks_from_playlist, playlist),
                        result=(self._set_tracks, (playlist, playlist['name'])),
                        end_state=self.MAIN_MENU_STATE)
        self.execute_future(future)

    def _set_artist(self, artist):
        future = Future(target=(self.api.get_selections_from_artist, artist),
                        result=(self._set_tracks, (artist, artist['name'])),
                        end_state=self.MAIN_MENU_STATE)
        self.execute_future(future)

    def _set_artist_all_tracks(self, artist):
        future = Future(target=(self.api.get_all_tracks_from_artist, artist),
                        result=(self._set_tracks, (common.get_all_tracks_context(artist),
                                                   "All tracks from " + artist['name'])),
                        end_state=self.MAIN_MENU_STATE)
        self.execute_future(future)

    def _set_album(self, album):
        future = Future(target=(self.api.get_tracks_from_album, album),
                        result=(self._set_tracks, (album, album['name'])),
                        end_state=self.MAIN_MENU_STATE)
        self.execute_future(future)

    def _set_tracks(self, tracks, context, header):
        with self.lock:
            # Save the track listing.
            self.previous_tracks.append((tracks, context, header))

            # Set the new track listing.
            self.current_context = context
            self.main_menu.get_list('tracks').update_list(tracks)
            self.main_menu.get_list('tracks').header = header

            # Go to the tracks pane.
            self.main_menu.set_current_list('tracks')
            self.main_menu.get_list('tracks').set_index(0)

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

    def restore_previous_tracks(self, i=1):
        if len(self.previous_tracks) > i:
            last = None
            for _ in range(i+1):
                last = self.previous_tracks.pop()

            self._set_tracks(*last)
            return True
        else:
            return False

    def is_creating_command(self):
        return self.creating_command

    def in_search_menu(self):
        return self.is_in_state(self.SEARCH_MENU_STATE)

    def in_main_menu(self):
        return self.is_in_state(self.MAIN_MENU_STATE)

    def in_select_player_menu(self):
        return self.is_in_state(self.PLAYER_MENU_STATE)

    def is_loading(self):
        return self.is_in_state(self.LOAD_STATE)

    def is_running(self):
        return not self.is_in_state(self.EXIT_STATE)

    def is_in_state(self, state):
        return self.current_state == state

    def poll_currently_playing_track(self):
        track = self.api.get_currently_playing()
        if track != NoneTrack:
            self.currently_playing_track = track

    def get_cursor_i(self):
        return self.command_cursor_i

    def get_display_name(self):
        return self.api.get_display_name()

    def get_command_query(self):
        return self.command_query

    def get_currently_playing_track(self):
        return self.currently_playing_track

    def execute_future(self, future):
        # If we're not already executing one, run it.
        # Otherwise, it will be added to the queue and executed later.
        logger.debug("Adding Future: %s", future)
        self.futures.append(future)
        if not self.is_loading():
            self.current_state = self.LOAD_STATE
            future.run()

    def get_loading_progress(self):
        if self.futures:
            return self.futures[0].get_progress()


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


class Future(object):
    """Execute a function asynchronously then execute the callback when done.

    Also has information about the progress of the call.
    """

    def __init__(self, target, result=(), end_state=None):
        """Constructor.

        Args:
            target (func, tuple): Contains the target function, args, and kwargs.
                The target function must accept a keyword argument 'progress'
                that is a Progress object.
            result (tuple): Contains the result function, args and kwargs.
            end_state (int): The end state to return to after completing the call.
        """
        def to_iter(obj):
            if isinstance(obj, (tuple, list)):
                return obj
            else:
                return (obj,)

        target = to_iter(target)

        result = to_iter(result)

        self.target_func = target[0]
        """The target fucntion."""

        self.target_args = list(to_iter(target[1])) if len(target) > 1 else []
        """The target args."""

        self.target_kwargs = target[2] if len(target) > 2 else {}
        """The target kwargs."""

        self.result_func = result[0] if result else None
        """The result fucntion."""

        self.result_args = list(to_iter(result[1])) if len(result) > 1 else []
        """The result args."""

        self.result_kwargs = result[2] if len(result) > 2 else {}
        """The target kwargs."""

        self.end_state = end_state
        """The end state."""

        self.event = Event()
        """An Event for the Future to signal when it's done."""

        self.progress = Progress()
        """Percent done."""

        self.target_kwargs['progress'] = self.progress

    def run(self):
        Thread(target=self.execute).start()

    @common.catch_exceptions
    def execute(self):
        # Make the main call.
        logger.debug(
            "Executing Future Target: %s",
            str((self.target_func.__name__, self.target_args, self.target_kwargs))
        )
        result = self.target_func(*self.target_args, **self.target_kwargs)

        # Execute the call back with the results.
        if self.result_func:
            logger.debug(
                "Executing Future Callback: %s",
                str((self.result_func.__name__, self.result_args, self.result_kwargs))
            )
            self.result_func(result, *self.result_args, **self.result_kwargs)\

        # Notify that we're done.
        self.event.set()

    def wait(self):
        self.event.wait()

    def get_end_state(self):
        return self.end_state

    def get_progress(self):
        return self.progress.get_percent()

    def is_done(self):
        return self.event.is_set()

    def __str__(self):
        return str((self.target_func.__name__, self.target_args, self.target_kwargs)) + \
            str((self.result_func.__name__, self.result_args, self.result_kwargs))


class Progress(object):
    """Represents the amount of work complete."""

    def __init__(self):
        """Constructor."""
        self.percent_done = 0.0
        """The amount done."""

        self.lock = Lock()
        """A lock for the object."""

    def set_percent(self, percent):
        with self.lock:
            self.percent_done = percent

    def get_percent(self):
        with self.lock:
            return self.percent_done


class Config(object):
    """Read and store config parameters."""
    default = {
        "find_next": ord("n"),
        "find_previous": ord("p"),
        "add_track": ord("P"),
        "show_devices": ord("W"),
        "refresh": ord("R"),
        "goto_artist": ord("D"),
        "goto_album": ord("S"),
        "current_artist": ord("C"),
        "current_album": ord("X"),
        "next_track": ord(">"),
        "previous_track": ord("<"),
        "play": ord(" "),
        "volume_0": ord("~"),
        "volume_1": ord("!"),
        "volume_2": ord("@"),
        "volume_3": ord("#"),
        "volume_4": ord("$"),
        "volume_5": ord("%"),
        "volume_6": ord("^"),
        "volume_7": ord("&"),
        "volume_8": ord("*"),
        "volume_9": ord("("),
        "volume_10": ord(")"),
        "volume_up": ord("+"),
        "volume_down": ord("_")
    }

    def __init__(self, config_filename=None):
        self.config_filename = config_filename
        """The full path to the config file."""

        self.keys = {}
        """Mapping of config keys to key codes and the reverse."""

        if self.config_filename:
            if not self._parse_and_validate_config_file():
                raise RuntimeError("Unable to parse config file. See above for details.")

            logger.debug("The following config parameters are being used:")
            for param, key in self.keys.items():
                if isinstance(param, basestring):
                    try:
                        logger.debug("\t%s: %s (%s)", param, chr(key), key)
                    except:
                        logger.debug("\t%s: %s", param, key)
        else:
            self.keys = self.default

        # Reverse map the params and keys.
        for key, value in self.keys.items():
            self.keys[value] = key

    def has_key(self, code):
        return code in self.keys

    def is_volume_key(self, key):
        return bool(re.match(r"volume_[0-9]+", self.get_config_param(key)))

    def get_config_param(self, key):
        return self.keys.get(key, "")

    def __getattr__(self, attr):
        return self.keys[attr]

    def _parse_and_validate_config_file(self):
        """Initializes the users settings based on the stermrc file"""
        rc_file = open(self.config_filename, "r")

        new_keys = {}

        for line in rc_file:
            # Strip whitespace and comments.
            line = line.strip()
            line = line.split("#")[0]
            try:
                param, code = line.split(":")
                code = code.strip()
                if common.is_int(code):
                    code = int(code)
                else:
                    code = ord(eval(code))

                # Make sure this is a valid config param.
                if param not in self.default:
                    print("The following parameter is not recognized: {}".format(param))

                # Make sure this wasn't defined twice.
                if param in new_keys:
                    print("The following line is redefining a param:")
                    print(line)
                    return False

                # Make sure this wasn't defined twice.
                if code in new_keys.values():
                    print("The following line is redefining a key code:")
                    print(line)
                    return False

                new_keys[param] = code
            except:
                print("The following line is not formatted properly:")
                print(line)
                return False

        # Copy over the defaults.
        for param in set(self.default.keys()) - set(new_keys.keys()):
            new_keys[param] = self.default[param]

        # Make sure there's no collision.
        if len(set(new_keys.values())) != len(new_keys):
            print("A conflicting parameter was found with the default configuration!")
            print("Check the help message (-h) for the defaults and make sure")
            print("you aren't using the same keys.")
            return False

        # Success!
        self.keys = new_keys

        return True

    @staticmethod
    def help():
        key_help = [
            ("find_next", "Find the next entry matching the previous expression."),
            ("find_previous", "Find the previous entry matching the previous expression."),
            ("add_track", "Add a track to a playlist."),
            ("show_devices", "Show available devices"),
            ("refresh", "Refresh the player."),
            ("goto_artist", "Go to the artist page of the highlighted track."),
            ("goto_album", "Go to the album page of the highlighted track."),
            ("current_artist", "Go to the artist page of the currently playing track."),
            ("current_album", "Go to the album page of the currently playing track."),
            ("next_track", "Play the next track."),
            ("previous_track", "Play the previous track."),
            ("play", "Toggle play/pause."),
            ("volume_0", "Mute volume."),
            ("volume_1", "Set volume to 10%."),
            ("volume_2", "Set volume to 20%."),
            ("volume_3", "Set volume to 30%."),
            ("volume_4", "Set volume to 40%."),
            ("volume_5", "Set volume to 50%."),
            ("volume_6", "Set volume to 60%."),
            ("volume_7", "Set volume to 70%."),
            ("volume_8", "Set volume to 80%."),
            ("volume_9", "Set volume to 90%."),
            ("volume_10", "Set volume to 100%."),
            ("volume_up", "Increase volume by 5%."),
            ("volume_down", "Decrease volume by 5%.")
        ]

        msg = "The following keys can be specified in the config file:\n\n"
        for key, help_msg in key_help:
            msg = msg + "%20s - %s (Default=%s)\n" % (key, help_msg, Config.default[key])

        msg = msg + "\nEach key should be defined by a single character in quotes.\n"
        msg = msg + "Example:\n next_track: \">\"\n\n"
        msg = msg + "Alternatively, you can define a special key code not in quotes.\n"
        msg = msg + "Example:\n next_track: 67\n\n"

        return msg
