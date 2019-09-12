import os
import pickle
import re
import time
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
    # Attributes to save between runs.
    PICKLE_ATTRS = [
        "command_history",
        "previous_tracks",
        "current_context",
        "current_device"
    ]

    # Enums for repeat state.
    REPEAT_OFF, REPEAT_CONTEXT, REPEAT_TRACK = range(3)

    # List of backspace keys.
    BACKSPACE_KEYS = [uc.KEY_BACKSPACE, 8]

    # List of enter keys.
    ENTER_KEYS = [uc.KEY_ENTER, 10, 13]

    # List of keys for cancling.
    CANCEL_KEYS = [uc.KEY_EXIT, 27] + BACKSPACE_KEYS

    # How often to sync the player state.
    SYNC_PLAYER_PERIOD = 60 * 5

    # How often to sync the available devices.
    SYNC_DEVICES_PERIOD = 1

    def __init__(self, api, config):
        self.lock = Lock()
        """Lock for the class."""

        self.api = api
        """SpotifyApi object to make Spotify API calls."""

        self.config = config
        """The Config parameters."""

        self.sync_period = common.PeriodicCallback(self.SYNC_PLAYER_PERIOD,
                                                   self.sync_player_state)
        """Periodic for syncing the player."""

        self.sync_devices = common.PeriodicCallback(self.SYNC_DEVICES_PERIOD,
                                                    self.sync_available_devices,
                                                    active=False)
        """Periodic for syncing the available devices."""

        self.periodics = [
            self.sync_period,
            self.sync_devices
        ]
        """All Periodics."""

        self.user_list = List("user")
        self.tracks_list = List("tracks")
        self.player_list = List("player")
        self.search_list = List("search_results", header="Search")
        self.device_list = List("devices")
        self.confirm_list = List("confirm", header="Are you sure?")
        self.artist_list = List("artists", header="Select an artist")

        self.previous_tracks = []
        """Keeps track of previously displayed Tracks."""

        self.current_context = None
        """The currently playing context."""

        self.current_device = UnableToFindDevice
        """The current Device."""

        self.available_devices = []
        """The list of available devices."""

        self.playing = False
        """Whether the play is playing or not."""

        self.progress = None
        """Progress into the track."""

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

        self.prev_command = ["exit"]
        """The previous command that was executed."""

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

        self.current_state = None
        """Current state of the applicaiton."""

        self.prev_state = None
        """Previous state of the applicaiton."""

        self.futures = []
        """List of futures to execute."""

        self.last_update_time = time.time()
        """The last time we were called to update."""

        # Build the state machine and transition to the first state.
        start_state = self.build_state_machine()
        self.switch_to_state(self.build_state_machine())

    def switch_to_state(self, new_state):
        """Transition to a new State.

        Args:
            new_state (State): The new State to transition to.
        """
        logger.debug("State transition: %s -> %s", self.current_state, new_state)
        self.prev_state = self.current_state
        self.current_state = new_state

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
        self.player_list.update_list([
            PlayerAction("(S)", self._toggle_shuffle),
            PlayerAction("<< ", self._play_previous),
            PlayerAction("(P)", self._toggle_play),
            PlayerAction(" >>", self._play_next),
            PlayerAction("(R)", self._toggle_repeat),
            PlayerAction(" --", self._decrease_volume),
            PlayerAction(" ++", self._increase_volume),
        ])

        self.confirm_list.update_list([Option("Yes"),
                                       Option("No")])

        # Get current player state.
        player_state = self.sync_player_state()

        # Get the users playlists.
        playlists = self.api.get_user_playlists(self.user)
        if not playlists:
            print("Could not load playlists. Try again.")
            exit(1)
        playlists = list(playlists)

        # Add the Saved tracks playlist.
        saved = Playlist({
            "name": "Saved",
            "uri": common.SAVED_TRACKS_CONTEXT_URI,
            "id": "",
            "owner_id": self.api.get_id()
        })
        playlists.insert(0, saved)
        self.user_list.update_list(tuple(playlists))

        # Initialize track list.
        if player_state:
            context = player_state['context']
            self._set_context(context)
        else:
            if not self.restore_previous_tracks(0):
                logger.debug("Loading the Saved track list")
                self._set_playlist(self.user_list[0])

    def sync_player_state(self):
        player_state = self.api.get_player_state()
        if player_state:
            self.currently_playing_track = Track(player_state['item']) \
                if player_state['item'] else NoneTrack
            self.playing = player_state['is_playing']

            self.current_device = Device(player_state['device'])
            self.volume = self.current_device['volume_percent']

            self._set_player_repeat(player_state['repeat_state'])
            self._set_player_shuffle(player_state['shuffle_state'])

            duration = player_state['progress_ms']
            if self.currently_playing_track and duration:
                self.progress = [duration, self.currently_playing_track['duration_ms']]

            return player_state
        else:
            self.progress = None
            self.currently_playing_track = NoneTrack
            self.current_device = UnableToFindDevice

    def sync_available_devices(self):
        self.available_devices = self.api.get_devices()
        self.device_list.update_list(self.available_devices,
                                     reset_index=False)

    def process_key(self, key):
        action = self.current_state.process_key(key)
        if action:
            # Kinda gross, but easiest way to deal with passing in the key that was presed
            # and not forcing all functions to take in a positional argument.
            try:
                action(key)
            except TypeError:
                action()

        if key is not None and action is None:
            logger.info("Unrecognized key: %d", key)

        self._run_calcs()

        # We probably just selected a Track, let's plan
        # to re-sync in 5s.
        if key in self.ENTER_KEYS:
            self.sync_period.call_in(5)

    def _run_calcs(self):
        """Run any calculations that we need to do at the end of the update."""
        #TODO: Should be handled in the CommandProcessor
        self.command_cursor_i = common.clamp(self.command_cursor_i,
                                             0,
                                             len(self.get_command_query()))

        # Run all Periodics.
        for periodic in self.periodics:
            periodic.update(time.time())

        # Make sure sync_devices is only active when selecting a device.
        # TODO: Should be handled on state changes
        if not self.in_select_device_menu():
            if self.sync_devices.is_active():
                self.sync_devices.deactivate()

        # Calculate track progress.
        time_delta = 1000*(time.time() - self.last_update_time)
        if self.progress and self.playing:
            self.progress[0] = self.progress[0] + time_delta

            # Song is done. Let's plan to re-sync in 1 second.
            percent = float(self.progress[0])/self.progress[1]
            if percent > 1.0:
                logger.debug("Reached end of song. Re-syncing in 2s.")
                self.sync_period.call_in(2)
                self.progress = None

        # Save off this last time.
        self.last_update_time = time.time()

    def _process_command(self, command_input):
        logger.debug("Processing command: %s", command_input)

        # Convert everything to string first
        if not isinstance(command_input, str):
            command_input = "".join(command_input).strip()

        if not command_input:
            return

        # Convert special commands.
        if command_input[0] == ":":
            if command_input == ":":
                return
            elif command_input.lower().startswith(":q"):
                command_string = "exit"
            else:
                command_string = command_input[1::]
        elif command_input[0] == '"':
            if command_input == '"' or command_input == '""':
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

        self.switch_to_state(self.search_state)

    def _execute_find(self, i, *query):
        query = " ".join(query)
        logger.debug("find:%s", query)
        search_list = self.prev_state.get_list()

        found = []
        for index, item in enumerate(search_list):
            if query.lower() in str(item).lower():
                found.append(index)

        if found:
           search_list.set_index(found[int(i) % len(found)])

        self.switch_to_state(self.prev_state)

    def _execute_shuffle(self, state):
        state = state.lower().strip()
        state = True if state == "true" else False
        self._set_player_shuffle(state)
        self.api.shuffle(state)

    def _execute_repeat(self, state):
        state = state.lower().strip()
        if state in ["off", "context", "track"]:
            self._set_player_repeat(state)
            self.api.repeat(state)

    def _execute_volume(self, volume):
        volume = common.clamp(int(volume), 0, 100)
        if 0 <= volume and volume <= 100:
            self.volume = volume
            self.api.volume(self.volume)

    def _execute_play(self):
        self.playing = True
        self._play(None, None)

    def _execute_pause(self):
        self.playing = False
        self.api.pause()

    def _execute_exit(self):
        self.current_state = self.exit_state

    def _play(self, track, context):
        context_uri = None
        uris = None
        track_id = None

        if track:
            self.currently_playing_track = track
            self.progress = [0, track['duration_ms']]
            track_id = track['uri']

        # The Saved Tracks playlist in Spotify doesn't have a Context.
        # So we have to give the API a list of Tracks to play
        # to mimic a context.
        if context:
            if context['uri'] == common.SAVED_TRACKS_CONTEXT_URI:
                uris = [t['uri'] for t in
                        self.api.get_tracks_from_playlist(self.user_list[0])]
                track_id = self.tracks_list.i
            elif context.get('type') == 'artist':
                uris = [s['uri']
                        for s in self.api.get_selections_from_artist(self.current_context)
                        if s['type'] == 'track']
                track_id = self.tracks_list.i
            elif common.is_all_tracks_context(context):
                uris = [t['uri'] for t in self.tracks_list.list]
                track_id = self.tracks_list.i
            else:
                context_uri = context['uri']

        # If using a custom context, limit it to 750 tracks.
        if uris:
            n = 750
            offset_i = max(track_id - (n//2) + 1, 0)
            uris = uris[offset_i:offset_i + n]
            track_id -= offset_i

        self.api.play(track_id, context_uri, uris, self.current_device)

    def _play_next(self):
        def wait_and_sync():
            time.sleep(2)
            self.sync_player_state()

        future = Future(target=self.api.next,
                        result=wait_and_sync,
                        progress=False)
        self.execute_future(future)

    def _play_previous(self):
        def wait_and_sync():
            time.sleep(2)
            self.sync_player_state()

        future = Future(target=self.api.previous,
                        result=wait_and_sync,
                        progress=False)
        self.execute_future(future)

    def _toggle_play(self):
        if self.playing:
            self._process_command("pause")
        else:
            self._process_command("play")

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
        self.track_to_add = None
        self.playlist_to_add = None

    def _set_playlist(self, playlist):
        future = Future(target=(self.api.get_tracks_from_playlist, playlist),
                        result=(self._choose_tracks, (playlist, playlist['name'])))
        self.execute_future(future)

    def _set_artist(self, artist):
        future = Future(target=(self.api.get_selections_from_artist, artist),
                        result=(self._choose_tracks, (artist, artist['name'])))
        self.execute_future(future)

    def _set_artist_all_tracks(self, artist):
        future = Future(target=(self.api.get_all_tracks_from_artist, artist),
                        result=(self._choose_tracks, (common.get_all_tracks_context(artist),
                                                   "All tracks from " + artist['name'])))
        self.execute_future(future)

    def _set_album(self, album):
        future = Future(target=(self.api.get_tracks_from_album, album),
                        result=(self._choose_tracks, (album, album['name'])))
        self.execute_future(future)

    def _set_context(self, context):
        if context is None:
            context = {
                "type":"playlist",
                "uri": common.SAVED_TRACKS_CONTEXT_URI
            }

        target_api_call = {
            "artist": self.api.get_selections_from_artist,
            "playlist": self.api.get_tracks_from_playlist,
            "album": self.api.get_tracks_from_album,
            common.ALL_ARTIST_TRACKS_CONTEXT_TYPE: self.api.get_all_tracks_from_artist,
        }[context["type"]]

        context = self.api.convert_context(context)

        future = Future(target=(target_api_call, context),
                        result=(self._choose_tracks, (context, context['name'])))
        self.execute_future(future)

    def _choose_tracks(self, tracks, context, header):
        with self.lock:
            # Save the track listing.
            self.previous_tracks.append((tracks, context, header))

            # Set the new track listing.
            self.current_context = context
            self.tracks_list.update_list(tracks)
            self.tracks_list.header = header

            # Go to the tracks pane.
            self.tracks_list.set_index(0)
            self.switch_to_state(self.tracks_state)

    def _choose_artist(self, artists):
        self.artist_menu["artists"].update_list(artists)
        self.artist_menu["artists"].set_index(0)
        self.switch_to_state(self.select_artist_state)

    def _set_player_device(self, new_device, play):
        self.sync_player_state()
        self.current_device = new_device
        self.api.transfer_playback(new_device, play)

    def _set_command_query(self, text):
        self.command_query = list(text)

    def _set_player_repeat(self, state):
        self.repeat = self._get_repeat_enum(state)
        self.player_list[4].title = "({})".format(['x', 'o', '1'][self.repeat])

    def _set_player_shuffle(self, state):
        self.shuffle = state
        self.player_list[0].title = "({})".format(
            {True: "S", False: "s"}[self.shuffle]
        )

    def restore_previous_tracks(self, i=1):
        if len(self.previous_tracks) > i:
            last = None
            for _ in range(i+1):
                last = self.previous_tracks.pop()

            self._choose_tracks(*last)
            return True
        else:
            return False

    def is_creating_command(self):
        return self.is_in_state(self.creating_command_state)

    def in_search_menu(self):
        return self.is_in_state(self.search_state)

    def in_main_menu(self):
        return self.is_in_state(self.tracks_state, self.user_state, self.player_state)

    def in_select_device_menu(self):
        return self.is_in_state(self.device_state)

    def is_loading(self):
        return self.is_in_state(self.loading_state)

    def is_adding_track_to_playlist(self):
        return self.is_in_state(self.a2p_select_state, self.a2p_confirm_state)

    def is_selecting_artist(self):
        return self.is_in_state(self.select_artist_state)

    def is_running(self):
        return not self.is_in_state(self.exit_state)

    def is_in_state(self, *states):
        return self.current_state in states

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
            self.switch_to_state(self.loading_state)
            future.run()

    def get_loading_progress(self):
        if self.futures:
            return self.futures[0].get_progress()

    def get_track_progress(self):
        return self.progress

    def build_state_machine(self):
        """Builds all of the states and binds all of the keys to alter the State.

        Returns:
            State: The initial State to start in.
        """
        # Common functions used to move around list and states
        def move_up_current_list():
            self.current_state.get_list().decrement()

        def move_down_current_list():
            self.current_state.get_list().increment()

        def switch_to_tracks_state():
            self.switch_to_state(self.tracks_state)

        def swtch_to_player_state():
            self.switch_to_state(self.player_state)

        def switch_to_user_state():
            self.switch_to_state(self.user_state)

        def switch_to_prev_state():
            self.switch_to_state(self.prev_state)

        #
        # User State - Handles commands while in the user pane
        #
        user_state = State("user", self.user_list)
        user_state.bind_key(uc.KEY_UP, move_up_current_list)
        user_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        user_state.bind_key(uc.KEY_RIGHT, switch_to_tracks_state)

        def enter():
            playlist = self.user_list.get_current_entry()
            if playlist:
                self._set_playlist(playlist)
        user_state.bind_key(self.ENTER_KEYS, enter)

        self.user_state = user_state

        #
        # Track State - Handles commands while in the tracks listing pane
        #
        tracks_state = State("tracks", self.tracks_list)
        tracks_state.bind_key(uc.KEY_UP, move_up_current_list)
        tracks_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        tracks_state.bind_key(uc.KEY_LEFT, switch_to_user_state)
        tracks_state.bind_key(uc.KEY_RIGHT, swtch_to_player_state)

        def dec():
            self.tracks_list.decrement(15)
        tracks_state.bind_key(uc.KEY_PPAGE, dec)

        def inc():
            self.tracks_list.increment(15)
        tracks_state.bind_key(uc.KEY_NPAGE, inc)

        def enter():
            entry = self.tracks_list.get_current_entry()
            if entry:
                if entry['type'] == 'artist':
                    self._set_artist(entry)
                elif entry['type'] == 'album':
                    self._set_album(entry)
                elif entry['type'] == 'track':
                    self._play(entry, context=self.current_context)
        tracks_state.bind_key(self.ENTER_KEYS, enter)

        def add_to_playlist():
            entry = self.tracks_list.get_current_entry()
            if entry['type'] == 'track':
                self.track_to_add = entry
                self.switch_to_state(self.a2p_select_state)
        tracks_state.bind_key(self.config.add_track, add_to_playlist)

        def goto_artist():
            entry = self.tracks_list.get_current_entry()
            if entry['type'] == 'track':
                artists = entry['artists']
                if len(artists) == 1:
                    self._set_artist(artists[0])
                else:
                    self._choose_artist(artists)
        tracks_state.bind_key(self.config.goto_artist, goto_artist)

        def goto_album():
            entry = self.tracks_list.get_current_entry()
            if entry['type'] == 'track':
                album = entry['album']
                self._set_album(album)
            elif entry['type'] == 'album':
                self._set_album(entry)
        tracks_state.bind_key(self.config.goto_album, goto_album)

        self.tracks_state = tracks_state

        #
        # Player State - Handles commands while in the player pane
        #
        player_state = State("player", self.player_list)
        player_state.bind_key(uc.KEY_UP, switch_to_tracks_state)
        player_state.bind_key(uc.KEY_RIGHT, move_down_current_list)
        def left():
            if self.current_state.get_list().i == 0:
                switch_to_user_state()
            else:
                move_up_current_list()
        player_state.bind_key(uc.KEY_LEFT, left)

        def enter():
            self.player_list.get_current_entry().action()
        player_state.bind_key(self.ENTER_KEYS, enter)

        self.player_state = player_state


        #
        # Creaintg Command State - Handles commands while user is typing in a command
        #
        creating_command_state = State("creating_command")
        def left():
            self.command_cursor_i -= 1
        def right():
            self.command_cursor_i += 1
        creating_command_state.bind_key(uc.KEY_LEFT, left)
        creating_command_state.bind_key(uc.KEY_RIGHT, right)

        def up():
            if self.command_history:
                self.command_history_i = common.clamp(self.command_history_i-1,
                                                      0,
                                                      len(self.command_history)-1)
                self._set_command_query(self.command_history[self.command_history_i])
        creating_command_state.bind_key(uc.KEY_UP, up)

        def down():
            if self.command_history:
                self.command_history_i = common.clamp(self.command_history_i+1,
                                                      0,
                                                      len(self.command_history)-1)
                self._set_command_query(self.command_history[self.command_history_i])
        creating_command_state.bind_key(uc.KEY_DOWN, down)

        def backspace():
            if self.command_cursor_i > 0:
                self.get_command_query().pop(self.command_cursor_i - 1)
                self.command_cursor_i -= 1
            else:
                switch_to_prev_state()
        creating_command_state.bind_key(self.BACKSPACE_KEYS, backspace)

        def ascii_key(key):
            char = chr(key)
            self.get_command_query().insert(self.command_cursor_i, char)
            self.command_cursor_i += 1
        creating_command_state.bind_key(list(range(32, 128)), ascii_key)

        def enter():
            self._process_command(self.get_command_query())
        creating_command_state.bind_key(self.ENTER_KEYS, enter)

        creating_command_state.bind_key([uc.KEY_EXIT, 27], switch_to_prev_state)

        self.creating_command_state = creating_command_state

        #
        # Search State - Handles commands while user is searching
        #
        search_state = State("search", self.search_list)
        search_state.bind_key(uc.KEY_UP, move_up_current_list)
        search_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        search_state.bind_key(self.BACKSPACE_KEYS + [uc.KEY_EXIT, 27], switch_to_prev_state)

        def right():
            entry = self.search_list.get_current_entry()
            if entry['type'] == 'album':
                self.current_state = tracks_state
                self._set_album(entry)
            elif entry['type'] == 'artist':
                albums = self.api.get_albums_from_artist(entry)
                if albums:
                    self.search_menu['results'].update_list(albums)
        search_state.bind_key(uc.KEY_RIGHT, right)

        def enter():
            entry = self.search_list.get_current_entry()
            if entry:
                if entry['type'] == 'artist':
                    self._set_artist(entry)
                elif entry['type'] == 'album':
                    self._set_album(entry)
                elif entry['type'] == 'track':
                    self._play(entry, context=None)
            self.current_state = tracks_state
        search_state.bind_key(self.ENTER_KEYS, enter)

        self.search_state = search_state

        #
        # Device State - Handles commands while user is searching for a device
        #
        device_state = State("device", self.device_list)
        device_state.bind_key(uc.KEY_UP, move_up_current_list)
        device_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        device_state.bind_key(self.BACKSPACE_KEYS + [uc.KEY_EXIT, 27], switch_to_prev_state)

        def enter():
            new_device = self.device_list.get_current_entry()
            if new_device:
                self._set_player_device(new_device, self.playing)
                switch_to_tracks_state()
        device_state.bind_key(self.ENTER_KEYS, enter)

        self.device_state = device_state

        #
        # Command commands for all of the main states
        #
        main_states = [user_state, tracks_state, player_state]

        bind_to_all(main_states, self.BACKSPACE_KEYS, self.restore_previous_tracks)

        def start_generic_command(key):
            char = chr(key)
            self._set_command_query(char)
            self.command_cursor_i = 1
            self.switch_to_state(self.creating_command_state)
        bind_to_all(main_states, [ord('/'), ord(':')], start_generic_command)

        def start_search_command():
            self._set_command_query("\"\"")
            self.command_cursor_i = 1
            self.switch_to_state(self.creating_command_state)
        bind_to_all(main_states, ord('"'), start_search_command)

        def find_next():
            if self.prev_command[0] in ["find"]:
                i = int(self.prev_command[1])
                command = self.prev_command
                command[1] = str(i + 1)
                self._process_command(" ".join(command))
        bind_to_all(main_states, self.config.find_next, find_next)

        def find_prev():
            if self.prev_command[0] in ["find"]:
                i = int(self.prev_command[1])
                command = self.prev_command
                command[1] = str(i - 1)
                self._process_command(" ".join(command))
        bind_to_all(main_states, self.config.find_previous, find_prev)

        def show_devices():
            self.switch_to_state(self.device_state)
            self.sync_devices.activate()
        bind_to_all(main_states, self.config.show_devices, show_devices)

        bind_to_all(main_states, self.config.refresh, self.sync_player_state)

        def current_artist():
            entry = self.currently_playing_track
            if entry:
                artists = entry['artists']
                if len(artists) == 1:
                    self._set_artist(artists[0])
                else:
                    self._choose_artist(artists)
        bind_to_all(main_states, self.config.current_artist, current_artist)

        def current_album():
            entry = self.currently_playing_track
            if entry:
                album = entry['album']
                self._set_album(album)
        bind_to_all(main_states, self.config.current_album, current_album)

        def current_context():
            state = self.api.get_player_state()
            if state:
                context = state['context']
                self._set_context(context)
        bind_to_all(main_states, self.config.current_context, current_context)

        def all_tracks():
            if self.current_context:
                if common.is_all_tracks_context(self.current_context):
                    artist = self.current_context['artist']
                    self._set_artist(artist)
                elif self.current_context.get("type") == "artist":
                    self._set_artist_all_tracks(self.current_context)
        bind_to_all(main_states, ord('\t'), all_tracks)

        bind_to_all(main_states, self.config.play, self._toggle_play)
        bind_to_all(main_states, self.config.next_track, self._play_next)
        bind_to_all(main_states, self.config.previous_track, self._play_previous)

        def volume():
            config_param = self.config.get_config_param(key)
            volume = 10*int(config_param.split("_")[1])
            self._process_command("volume {}".format(volume))
        #TODO: fix
        #bind_to_all(main_states, self.config.volume_keys, volume)

        def volume_down():
            self._process_command("volume {}".format(self.volume - 5))
        def volume_up():
            self._process_command("volume {}".format(self.volume + 5))
        bind_to_all(main_states, self.config.volume_down, volume_down)
        bind_to_all(main_states, self.config.volume_up, volume_up)

        #
        # Loading State - The loading state when the program is making a long query
        #
        loading_state = State("loading")

        def loading():
            # Get the current Future.
            future = self.futures[0]

            # If it's done, leave the loading_state.
            # But if there are more Futures to execute, continue to run them.
            if future.is_done():
                self.futures.pop(0)
                if self.futures:
                    self.futures[0].run()
        loading_state.set_default_action(loading)
        self.loading_state = loading_state


        #
        # Adding to Playlist - The collection of states that handle adding a new song to a playlist
        #
        # State for selecting which playing to add the track
        a2p_select_state = State("a2p_select", self.user_list)
        a2p_select_state.bind_key(uc.KEY_UP, move_up_current_list)
        a2p_select_state.bind_key(uc.KEY_DOWN, move_down_current_list)

        def cancel():
            self.track_to_add = None
            self.playlist_to_add = None
            switch_to_tracks_state()
        a2p_select_state.bind_key(self.CANCEL_KEYS, cancel)

        def enter():
            self.playlist_to_add = self.user_list.get_current_entry()
            self.swtch_to_player_state(self.a2p_confirm_state)
        a2p_select_state.bind_key(self.ENTER_KEYS, enter)
        self.a2p_select_state = a2p_select_state

        # State for confirming yes or no
        a2p_confirm_state = State("a2p_confirm", self.confirm_list)
        a2p_confirm_state.bind_key(uc.KEY_UP, move_up_current_list)
        a2p_confirm_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        a2p_confirm_state.bind_key(self.CANCEL_KEYS, cancel)

        def enter():
            entry = self.confirm_list.get_current_entry()
            if entry.get().lower() == "yes":
                self._add_track_to_playlist(self.track_to_add, self.playlist_to_add)
            else:
                self.track_to_add = None
                self.playlist_to_add = None
            switch_to_tracks_state()
        a2p_confirm_state.bind_key(self.ENTER_KEYS, enter)
        self.a2p_confirm_state = a2p_confirm_state

        #
        # Select Artist - State for chossing an artist when there are multiple artist for a track
        #
        select_artist_state = State("select_artist", self.artist_list)
        select_artist_state.bind_key(uc.KEY_UP, move_up_current_list)
        select_artist_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        select_artist_state.bind_key(self.CANCEL_KEYS, switch_to_prev_state)

        def enter():
            artist = self.artist_list.get_current_entry()
            if artist:
                self._set_artist(artist)
                switch_to_prev_state()
        select_artist_state.bind_key(self.ENTER_KEYS, enter)
        self.select_artist_state = select_artist_state

        #
        # Exit State - Does nothing, indicates program should exit.
        #
        self.exit_state = State("exit")

        # Let's always start in the tracks_state.
        return tracks_state


class List(object):
    """Represents a list of selectable items.

    Spotify Terminal treats most things as a list
    that the user traverses through to make actions.
    """

    def __init__(self, name=None, header=""):
        self.i = 0
        """Currently selected index."""

        self.list = tuple()
        """List of entries."""

        self.name = name or "None"
        """Name of List."""

        self.header = header
        """Header."""

    def update_list(self, l, reset_index=True):
        """Update the list.

        Args:
            l (iter): The list ot update to.
        """
        self.list = tuple(l)
        if reset_index:
            self.i = 0
        self.set_index(self.i)

    def get_current_entry(self):
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

    def increment(self, amount=None):
        self.update_index(amount or 1)

    def decrement(self, amount=None):
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


class Future(object):
    """Execute a function asynchronously then execute the callback when done.

    Also has information about the progress of the call.
    """

    def __init__(self, target, result=(), progress=True):
        """Constructor.

        Args:
            target (func, tuple): Contains the target function, args, and kwargs.
                The target function must accept a keyword argument 'progress'
                that is a Progress object.
            result (tuple): Contains the result function, args and kwargs.
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

        self.event = Event()
        """An Event for the Future to signal when it's done."""

        self.progress = Progress()
        """Percent done."""

        if progress:
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
            if result:
                self.result_func(result, *self.result_args, **self.result_kwargs)
            else:
                self.result_func(*self.result_args, **self.result_kwargs)

        # Notify that we're done.
        self.event.set()

    def wait(self):
        self.event.wait()

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
        "current_context": ord("?"),
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
                if isinstance(param, str):
                    try:
                        logger.debug("\t%s: %s (%s)", param, chr(key), key)
                    except:
                        logger.debug("\t%s: %s", param, key)
        else:
            self.keys = self.default

        # Reverse map the params and keys.
        for key, value in list(self.keys.items()):
            self.keys[value] = key

    def is_volume_key(self, key):
        return bool(re.match(r"volume_[0-9]+", self.get_config_param(key)))

    def get_config_param(self, key):
        return self.keys.get(key, "")

    def __getattr__(self, attr):
        return self.keys[attr]

    def __contains__(self, key):
        return key in self.keys

    def _parse_and_validate_config_file(self):
        """Initializes the users settings based on the config file."""
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

                # Make sure this param wasn't defined twice.
                if param in new_keys:
                    print("The following line is redefining a param:")
                    print(line)
                    return False

                # Make sure this code wasn't defined twice.
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
            ("current_context", "Go to the currently playing context."),
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
            msg = msg + "%20s - %s (Default=\"%s\")\n" % (key, help_msg, chr(Config.default[key]))

        msg = msg + "\nEach key should be defined by a single character in quotes.\n"
        msg = msg + "Example:\n next_track: \">\"\n\n"
        msg = msg + "Alternatively, you can define a special key code not in quotes.\n"
        msg = msg + "Example:\n next_track: 67\n\n"

        return msg


def bind_to_all(states, key, func):
    """Bind a a key or keys to a function for a given set of states.

    Args:
        states (list): The list of States.
        key (int, list): The key or keys.
        func (callable): The callable to bind.
    """
    for state in states:
        state.bind_key(key, func)


class Action(object):
    def __init__(self, func, desc):
        self.func = func
        """The function to call."""

        self.desc = desc
        """A description of the action."""

    def __call__(self, *args, **kwargs):
        self.func(*args, **kwargs)


class State(object):
    """Base class for a state in the program.

    A State manages any logic for when a key is pressed and manages a List.
    """

    def __init__(self, name, state_list=None):
        self._name = name
        """Name of this state."""

        self._actions = {}
        """Mapping of keys to Actions."""

        self._default_action = None
        """The default action if nothing is found."""

        self._list = state_list if state_list is not None else List()
        """The List that this state manages."""

    def set_default_action(self, func, desc=None):
        """Sets the default action of this state.

        Args:
            action (Action): The default Action.
        """
        self._default_action = Action(func, desc)

    def bind_key(self, key, func, desc=None):
        """Bind a key or ketys to a function.

        Args:
            key (int, collection): The key orkeys to bind.
            func (callable): The callable to bind to.
            desc (str): The description (optional).
        """
        if not isinstance(key, (list, tuple)):
            key = [key]
        for k in key:
            self._actions[k] = Action(func, desc)

    def process_key(self, key):
        """Process a key that was pressed.

        Args:
            key (int): The key that was pressed.

        Returns:
            Action: The action to call based on the key.
        """
        return self._actions.get(key, self._default_action)

    def get_list(self):
        """Return the List that this State manages.

        Returns:
            List: The List that this state manages.
        """
        return self._list

    def __str__(self):
        return self._name
