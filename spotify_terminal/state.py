import os
import pickle
import re
import time
from threading import RLock, Thread, Event, current_thread, _MainThread

from . import common
from . import unicurses as uc
from .command import CommandProcessor, TextQuery
from .config import Config
from .model import (
    UnableToFindDevice,
    NoneTrack,
    Playlist,
    PlayerAction,
    Track,
    Device,
    Option
)
from .periodic import PeriodicCallback, PeriodicDispatcher


logger = common.logging.getLogger(__name__)


future_lock = RLock()


def with_future_lock(func):
    """Execute function with the future lock."""

    def future_lock_wrapper(*args, **kwargs):
        logger.info("Waiting for lock:%s", func.__name__)
        with future_lock:
            logger.info("Acquired lock:%s", func.__name__)
            return func(*args, **kwargs)

    return future_lock_wrapper


class SpotifyState(object):
    """Represents the programs internal state of Spotify and menus.

    User input will alter this state.
    """
    # Attributes to save between runs.
    PICKLE_ATTRS = [
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
    CANCEL_KEYS = [uc.KEY_EXIT, 27, ord('q')] + BACKSPACE_KEYS

    # How often to sync the player state.
    SYNC_PLAYER_PERIOD = 60 * 5

    # How often to sync the available devices.
    SYNC_DEVICES_PERIOD = 1

    def __init__(self, api, config):
        self.api = api
        """SpotifyApi object to make Spotify API calls."""

        self.config = config
        """The Config parameters."""

        self.sync_player = PeriodicCallback(self.SYNC_PLAYER_PERIOD,
                                            self.sync_player_state)
        """Periodic for syncing the player."""

        self.sync_devices = PeriodicCallback(self.SYNC_DEVICES_PERIOD,
                                             self.periodic_sync_devices,
                                             active=False)
        """Periodic for syncing the available devices."""

        self.sync_progress = PeriodicCallback(1, self.calculate_track_progress)
        """Periodic for calculating track progress."""

        self.dispatcher = PeriodicDispatcher([
            self.sync_player,
            self.sync_devices,
            self.sync_progress,
            PeriodicCallback(1, self.calculate_alert_timeout)
        ])
        """All Periodics."""

        self.user_list = List("user")
        self.tracks_list = List("tracks")
        self.player_list = List("player")
        self.search_list = List("search_results", header="Search")
        self.device_list = List("devices")
        self.help_list = List("help")
        self.confirm_list = List("confirm", header="Are you sure?")
        self.artist_list = List("artists", header="Select an artist")
        self.other_actions_list = List("other_actions")
        """The program state is built around Lists and manipulating them."""

        self.previous_tracks = []
        """Keeps track of previously displayed Tracks."""

        self.current_context = None
        """The currently playing context."""

        self.current_device = UnableToFindDevice
        """The current Device."""

        self.available_devices = []
        """The list of available devices."""

        self.playing = False
        """Whether the player is playing or not."""

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

        self.running = True
        """Whether we're running or not."""

        self.cmd = CommandProcessor(":", {
            "search": self._execute_search,
            "seek": self._execute_seek,
            "find": self._execute_find,
            "volume": self._execute_volume,
            "play": self._execute_play,
            "pause": self._execute_pause,
            "next": self._execute_next,
            "previous": self._execute_previous,
            "shuffle": self._execute_shuffle,
            "repeat": self._execute_repeat,
            "refresh": self._execute_refresh,
            "create_playlist": self._execute_create_playlist,
            "exit": self._execute_exit
        })
        """Processes commands."""

        # Bind useful shorthand commands.
        self.cmd.bind(['q', 'Q'], 'exit')
        self.cmd.bind_trigger('/', 'find 0')
        self.cmd.bind_trigger(['?'], 'search')

        self.key_queue = []
        """Queue of keys to process."""

        self.text_query = TextQuery()
        """A TextQuery for commands."""

        self.alert = Alert()
        """Current Alert."""

        self.current_state = None
        """Current state of the applicaiton."""

        self.prev_state = None
        """Previous state of the applicaiton."""

        self.next_future_state = None
        """The next state to go to after all Futures are done."""

        self.futures = []
        """List of futures to execute."""

        # Todo: Figure out a better way for periodics to handle their time
        self.track_progress_last_update_time = time.time()
        self.alert_last_update_time = time.time()
        """The last time we were called to update."""

        # Build the state machine and transition to the first state.
        start_state = self.build_state_machine()
        self.switch_to_state(start_state)

    def init(self):
        # Get the User info.
        user = self.api.get_user()
        if user is None:
            raise RuntimeError("Could not load user {}".format(self.api.user_username()))

        # Initialize PlayerActions.
        self.player_list.update_list([
            PlayerAction("(S)", self._toggle_shuffle),
            PlayerAction("<<", self._play_previous),
            PlayerAction("||", self._toggle_play),
            PlayerAction(">>", self._play_next),
            PlayerAction("(R)", self._toggle_repeat),
            PlayerAction("--", self._decrease_volume),
            PlayerAction("++", self._increase_volume),
        ])

        self.confirm_list.update_list([Option("Yes"), Option("No")])

        # Sync current player state.
        self.sync_player_state()

        self._load_playlists()

        # Initialize track list.
        if self.current_context is not None:
            self._set_context(self.current_context)
        else:
            if not self.restore_previous_tracks():
                logger.debug("Loading the Saved track list")
                self._set_playlist(self.user_list[0])

        # Initialize the help list
        help_list = []
        for config_key, description in self.config.key_help.items():
            key = chr(self.config.get_config_param(config_key))
            help_list.append(Option("{}:\t{}".format(key, description)))

        help_list.append(Option(""))
        help_list.append(Option("-----------------"))
        help_list.append(Option(""))

        for line in self.config.help().split('\n'):
            help_list.append(Option(line))

        self.help_list.update_list(help_list)

        # Initialize other program actions
        def queue_key(key):
            def func():
                self.key_queue.append(key)
            return func

        def run_command(command):
            def func():
                self.cmd.process_command(command)
            return func

        self.other_actions_list.update_list([
            PlayerAction(" [{}] Show Devices".format(chr(self.config.show_devices)), 
                         queue_key(self.config.show_devices)),
            PlayerAction(" [{}] Goto Artist".format(chr(self.config.current_artist)), 
                         queue_key(self.config.current_artist)),
            PlayerAction(" [{}] Goto Album".format(chr(self.config.current_album)), 
                         queue_key(self.config.current_album)),
            PlayerAction(" [{}] Create Playlist".format(chr(self.config.create_playlist)), 
                         queue_key(self.config.create_playlist)),
            PlayerAction(" [{}] Sync Player".format(chr(self.config.refresh)), 
                         run_command("refresh")),
            PlayerAction(" [{}] Seek".format(chr(self.config.seek)), 
                         queue_key(self.config.seek)),
            PlayerAction(" [{}] Help".format(chr(self.config.toggle_help)), 
                          queue_key(self.config.toggle_help)),
            PlayerAction(" Exit", run_command("exit"))
        ])

    def _load_playlists(self):
        # Get the users playlists.
        user = self.api.get_user()
        if user is None:
            raise RuntimeError("Trouble finding user. Try again later.")

        playlists = self.api.get_user_playlists(user)
        if playlists is None:
            print("Could not load playlists. Try again later.")
            exit(1)
        playlists = list(playlists)

        # Add the Saved tracks playlist.
        playlists.insert(0, self.api.user_saved_playlist())
        self.user_list.update_list(tuple(playlists))

    def sync_player_state(self):
        self.cmd.process_command("refresh")

    def periodic_sync_devices(self):
        self.available_devices = self.api.get_devices()
        if self.available_devices is None:
            self.alert.warn("Could not find any devices")
            return
        
        # Don't reset the index since this is called every 1s when the devices
        # menu is open.
        self.device_list.update_list(self.available_devices, reset_index=False)

    def process_key(self, key):
        """Process a key.

        Args:
            key (int): The key that was pressed. Can also be None.
        """
        if key is None and self.key_queue:
            key = self.key_queue.pop(0)

        action = self.current_state.process_key(key)
        if action:
            # Kinda gross, but easiest way to deal with passing in the key that was presed
            # and not forcing all functions to take in a positional argument.
            try:
                action()
            except TypeError:
                action(key)

        if key is not None and action is None:
            logger.info("Unrecognized key: %d", key)

        # Run all Periodics.
        self.dispatcher.dispatch()

        # Make sure sync_devices is only active when selecting a device.
        # TODO: Should be handled on state changes
        if not self.in_select_device_menu():
            if self.sync_devices.is_active():
                self.sync_devices.deactivate()

        self._set_player_icons()

    def calculate_track_progress(self):
        # Calculate track progress.
        time_delta = 1000*(time.time() - self.track_progress_last_update_time)
        if self.progress and self.playing:
            self.progress[0] = self.progress[0] + time_delta

            # If song is done. Let's plan to re-sync in 1 second.
            percent = float(self.progress[0])/self.progress[1]
            if percent > 1.0:
                logger.debug("Reached end of song. Re-syncing in 2s.")
                self.sync_player.call_in(2)
                self.progress = None

        # Save off this last time.
        self.track_progress_last_update_time = time.time()

    def calculate_alert_timeout(self):
        time_delta = time.time() - self.alert_last_update_time
        self.alert.dec_time(time_delta)
        self.alert_last_update_time = time.time()

    def switch_to_state(self, new_state):
        """Transition to a new State.

        Args:
            new_state (State): The new State to transition to.
        """
        if not isinstance(current_thread(), _MainThread):
            self.logger.info("Only the MainThread can switch states!")
            return

        logger.debug("State transition: %s -> %s", self.current_state, new_state)
        self.prev_state = self.current_state
        self.current_state = new_state

    def save_state(self):
        """Save the state to disk."""
        ps = {
            attr_name: getattr(self, attr_name)
            for attr_name in self.PICKLE_ATTRS
        }
        state_filename = common.get_file_from_cache(self.api.user_username(), "state")
        with open(state_filename, "wb") as file:
            logger.debug("Saving %s state", self.api.user_username())
            pickle.dump(ps, file)

    def load_state(self):
        """Load part of the state from disk."""
        state_filename = common.get_file_from_cache(self.api.user_username(), "state")
        if os.path.isfile(state_filename):
            with open(state_filename, "rb") as file:
                logger.debug("Loading %s state", self.api.user_username())
                ps = pickle.load(file)

            for attr in self.PICKLE_ATTRS:
                setattr(self, attr, ps[attr])

    def _execute_search(self, *query):
        query = " ".join(query)
        results = self.api.search(("artist", "album", "track", "playlist"), query)
        if results:
            self.search_list.update_list(results)
            self.search_list.header = "Search results for \"{}\"".format(query)
        else:
            self.search_list.update_list([])
            self.search_list.header = "No results found for \"{}\"".format(query)
        self.switch_to_state(self.search_state)

    def _execute_seek(self, time, device=None):
        if device is None:
            device = self.current_device

        if isinstance(time, str) and (':' in time):
            converter = {
                0: 1,    # 1 s in 1s
                1: 60,    # 60s in 1m
                2: 3600  # 3600s in 1hr
            }
            toks = time.split(':')
            assert len(toks) <= 3, "Invalid time format"
            seconds = 0
            for i, value in enumerate(toks[::-1]):
                seconds += converter[i] * int(value)
        else:
            seconds = int(time)

        self.api.seek(seconds * 1000, device)

        self.sync_player.call_in(1)

        self.switch_to_state(self.tracks_state)

    def _execute_find(self, i, *query):
        query = " ".join(query)
        # Find the right state to search in.
        state_to_search = self.current_state
        if self.current_state == self.creating_command_state:
            state_to_search = self.prev_state

        search_list = state_to_search.get_list()

        found = []
        for index, item in enumerate(search_list):
            if query.lower() in str(item).lower():
                found.append(index)

        if found:
           search_list.set_index(found[int(i) % len(found)])

        if self.current_state == self.creating_command_state:
            self.switch_to_state(state_to_search)

    def _execute_shuffle(self, state):
        state = state.lower().strip()
        state = True if state == "true" else False
        self._set_player_shuffle(state)
        self.api.shuffle(state)

    def _execute_repeat(self, repeat_option):
        repeat_option = repeat_option.lower().strip()
        if repeat_option in ["off", "context", "track"]:
            self._set_player_repeat(repeat_option)
            self.api.repeat(repeat_option)
    
    def _execute_refresh(self):
        # Note: DO NOT set the current_context
        # Otherwise, it will confuse the state of things. 
        player_state = self.api.get_player_state()
        if player_state:
            track = player_state['item']
            self.currently_playing_track = Track(track) if track else NoneTrack
            self.playing = player_state['is_playing']
            self.current_device = Device(player_state['device'])
            self.volume = self.current_device['volume_percent']
            self._set_player_repeat(player_state['repeat_state'])
            self._set_player_shuffle(player_state['shuffle_state'])

            duration = player_state['progress_ms']
            if self.currently_playing_track and duration:
                self.progress = [duration, self.currently_playing_track['duration_ms']]
        else:
            self.currently_playing_track = NoneTrack
            self.playing = False
            self.current_device = UnableToFindDevice
            self.volume = 0
            self.progress = None

    def _execute_volume(self, volume):
        volume = common.clamp(int(volume), 0, 100)
        self.volume = volume
        self.api.volume(self.volume)

    def _execute_play(self):
        self._play(None, None)

    def _execute_pause(self):
        self._pause()

    def _execute_next(self):
        self._play_next()

    def _execute_previous(self):
        self._play_previous()

    def _execute_create_playlist(self, *query):
        playlist_name = " ".join(query)
        playlist = self.api.create_playlist(playlist_name)
        if playlist is None:
            self.alert.warn("Unable to create new playlist")
        else:
            self._load_playlists()
            self.switch_to_state(self.tracks_state)

    def _execute_exit(self):
        self.current_state = self.exit_state

    def _pause(self):
        self.playing = False
        self.api.pause()

    def _play(self, track, context):
        # Make sure there is a device to play.
        if self.current_device is UnableToFindDevice:
            key_ord = self.config.show_devices
            key_chr = str(key_ord)
            try: 
                key_chr = chr(self.config.show_devices)
            except:
                pass
            message = "No device is selected! Press '{}' ({}) to open the Devices menu."
            self.alert.warn(message.format(key_chr, key_ord))
            return

        self.playing = True

        context_uri = None
        uris = None
        track_id = None

        if track:
            self.currently_playing_track = track
            self.progress = [0, track['duration_ms']]
            track_id = track['uri']

        if context:
            # The Saved Tracks playlist in Spotify doesn't have a Context.
            # So we have to give the API a list of Tracks to play
            # to mimic a context.
            if context['uri'] == common.SAVED_TRACKS_CONTEXT_URI:
                tracks = self.api.get_tracks_from_playlist(self.user_list[0])
                if tracks is not None:
                    uris = [t['uri'] for t in tracks]
                    track_id = self.tracks_list.i
            # Mimic a context for the Artist page (i.e, top tracks)
            elif context.get('type') == 'artist':
                selections = self.api.get_selections_from_artist(self.current_context)
                if selections is not None:
                    uris = [s['uri'] for s in selections if s['type'] == 'track']
                    track_id = self.tracks_list.i
            # Mimic the "all tracks" context
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
        self.sync_player.call_in(2)


    @common.asynchronously
    def _play_next(self):
        self.api.next()
        self.sync_player.call_in(2)

    @common.asynchronously
    def _play_previous(self):
        self.api.previous()
        self.sync_player.call_in(2)

    def _toggle_play(self):
        if self.playing:
            self.cmd.process_command("pause")
        else:
            self.cmd.process_command("play")

    def _toggle_shuffle(self):
        self.cmd.process_command("shuffle {}".format(not self.shuffle))

    def _toggle_repeat(self):
        self.cmd.process_command("repeat {}".format(
            ['off', 'context', 'track'][(self.repeat + 1) % 3]
        ))

    def _decrease_volume(self):
        self.cmd.process_command("volume {}".format(self.volume - 5))

    def _increase_volume(self):
        self.cmd.process_command("volume {}".format(self.volume + 5))

    def _get_repeat_enum(self, repeat):
        return {"off": self.REPEAT_OFF,
                "track": self.REPEAT_TRACK,
                "context": self.REPEAT_CONTEXT}[repeat]

    def _add_track_to_playlist(self, track, playlist):
        return self.api.add_track_to_playlist(track, playlist)

    def _remove_track_from_playlist(self, track, playlist):
        return self.api.remove_track_from_playlist(track, playlist)

    def _remove_playlist(self, playlist):
        return self.api.remove_playlist(playlist)

    def _set_playlist(self, playlist):
        future = Future(target=(self.api.get_tracks_from_playlist, playlist),
                        result=(self._update_track_list, (playlist, playlist['name'])),
                        use_return=True)
        self.execute_future(future, self.tracks_state)

    def _set_artist(self, artist):
        future = Future(target=(self.api.get_selections_from_artist, artist),
                        result=(self._update_track_list, (artist, artist['name'])),
                        use_return=True)
        self.execute_future(future, self.tracks_state)

    def _set_artist_all_tracks(self, artist):
        future = Future(target=(self.api.get_all_tracks_from_artist, artist),
                        result=(self._update_track_list, 
                                (common.get_all_tracks_context(artist),
                                 "All tracks from " + artist['name'])),
                        use_return=True)
        self.execute_future(future, self.tracks_state)

    def _set_album(self, album):
        future = Future(target=(self.api.get_tracks_from_album, album),
                        result=(self._update_track_list, (album, album['name'])),
                        use_return=True)
        self.execute_future(future, self.tracks_state)

    def _set_context(self, context):
        target_api_call = {
            "artist": self.api.get_selections_from_artist,
            "playlist": self.api.get_tracks_from_playlist,
            "album": self.api.get_tracks_from_album,
            common.ALL_ARTIST_TRACKS_CONTEXT_TYPE: self.api.get_all_tracks_from_artist,
        }[context["type"]]

        context = self.api.convert_context(context)
        if context is None:
            return

        future = Future(target=(target_api_call, context),
                        result=(self._update_track_list, (context, context['name'])),
                        use_return=True)
        self.execute_future(future, self.tracks_state)

    def _update_track_list(self, tracks, context, header):
        if tracks is None:
            msg = "Unable to get tracks from {}. Try again."
            self.alert.warn(msg.format(header))
            return
            
        # Save the track listing.
        self.previous_tracks.append((tracks, context, header))

        # Set the new track listing.
        self.current_context = context
        self.tracks_list.update_list(tracks)
        self.tracks_list.header = header

        # Go to the tracks pane.
        self.tracks_list.set_index(0)

    def _update_artist_list(self, artists):
        self.artist_list.update_list(artists)
        self.artist_list.set_index(0)
        self.switch_to_state(self.select_artist_state)

    def _set_player_device(self, new_device, play):
        self.current_device = new_device
        self.api.transfer_playback(new_device, play)

    def _set_command_query(self, text):
        self.text_query = TextQuery(text)

    def _set_player_repeat(self, state):
        self.repeat = self._get_repeat_enum(state)

    def _set_player_shuffle(self, state):
        self.shuffle = state

    def _set_player_icons(self):
        self.player_list[0].title = "({})".format('S' if self.shuffle else 's')
        self.player_list[2].title = "||" if self.playing else "|>"
        self.player_list[4].title = "({})".format(['x', 'o', '1'][self.repeat])

    def restore_previous_tracks(self):
        if len(self.previous_tracks) >= 2:
            self.previous_tracks.pop()
            self._update_track_list(*self.previous_tracks.pop())
            return True
        else:
            return False

    def is_creating_command(self):
        return self.is_in_state(self.creating_command_state)

    def in_search_menu(self):
        return self.is_in_state(self.search_state)

    def in_main_menu(self):
        return self.is_in_state([self.tracks_state, self.user_state, self.player_state])

    def in_select_device_menu(self):
        return self.is_in_state(self.device_state)

    def is_loading(self):
        return self.is_in_state(self.loading_state)

    def is_adding_track_to_playlist(self):
        return self.is_in_state([self.a2p_select_state, self.a2p_confirm_state])

    def is_selecting_artist(self):
        return self.is_in_state(self.select_artist_state)

    def is_running(self):
        return not self.is_in_state(self.exit_state)

    def is_in_state(self, states):
        if not isinstance(states, (list, tuple)):
            states = [states]
        return self.current_state in states

    def get_display_name(self):
        return self.api.user_display_name()

    def get_command_query(self):
        return self.text_query

    def get_currently_playing_track(self):
        return self.currently_playing_track

    @with_future_lock
    def execute_future(self, future, next_state):
        # If we're not already executing one, run it.
        # Otherwise, it will be added to the queue and executed later.
        logger.debug("Adding Future: %s", future)
        self.futures.append(future)
        if not self.is_loading():
            self.switch_to_state(self.loading_state)
            future.run()
        self.next_future_state = next_state

    def get_loading_progress(self):
        if self.futures:
            return self.futures[0].get_progress() or 0.0

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

        def switch_to_player_state():
            self.switch_to_state(self.player_state)

        def switch_to_other_actions_state():
            self.switch_to_state(self.other_actions_state)

        def switch_to_user_state():
            self.switch_to_state(self.user_state)

        def switch_to_help_state():
            self.switch_to_state(self.help_state)

        def switch_to_prev_state():
            self.switch_to_state(self.prev_state)

        #
        # User State - Handles commands while in the user pane
        #
        user_state = State("user", self.user_list)
        user_state.bind_key(uc.KEY_UP, move_up_current_list)
        user_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        user_state.bind_key(uc.KEY_RIGHT, switch_to_tracks_state)
        user_state.bind_key(uc.KEY_LEFT, switch_to_other_actions_state)

        def enter():
            playlist = self.user_list.get_current_entry()
            if playlist:
                self._set_playlist(playlist)
        user_state.bind_key(self.ENTER_KEYS, enter)

        def delete():
            entry = self.user_list.get_current_entry()
            if entry['uri'] == common.SAVED_TRACKS_CONTEXT_URI:
                self.alert.warn("You can't remove this playlist")
                return
            if entry["type"] == "playlist":
                self.playlist_to_remove = entry
                self.switch_to_state(self.remove_playlist_confirm_state)
        user_state.bind_key(self.config.delete, delete)

        self.user_state = user_state

        #
        # Track State - Handles commands while in the tracks listing pane
        #
        tracks_state = State("tracks", self.tracks_list)
        tracks_state.bind_key(uc.KEY_UP, move_up_current_list)
        tracks_state.bind_key(uc.KEY_LEFT, switch_to_user_state)
        tracks_state.bind_key(uc.KEY_RIGHT, switch_to_player_state)

        def down():
            cur_list = self.current_state.get_list()
            if cur_list.i == len(cur_list)-1:
                switch_to_player_state()
            else:
                move_down_current_list()
        tracks_state.bind_key(uc.KEY_DOWN, down)

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

        def remove_from_playlist():
            entry = self.tracks_list.get_current_entry()
            if entry['type'] == 'track':
                self.track_to_remove = entry
                self.switch_to_state(self.remove_track_confirm_state)
        tracks_state.bind_key(self.config.delete, remove_from_playlist)

        def goto_artist():
            entry = self.tracks_list.get_current_entry()
            if entry['type'] == 'track':
                artists = entry['artists']
                if len(artists) == 1:
                    self._set_artist(artists[0])
                else:
                    self._update_artist_list(artists)
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
        # Remove Track State - Handles removing a track from a playlist
        #
        remove_track_confirm_state = State("remove_track_confirm", self.confirm_list)
        remove_track_confirm_state.bind_key(uc.KEY_UP, move_up_current_list)
        remove_track_confirm_state.bind_key(uc.KEY_DOWN, move_down_current_list)

        def cancel():
            self.track_to_remove = None
            switch_to_tracks_state()
        remove_track_confirm_state.bind_key(self.CANCEL_KEYS, cancel)

        def enter():
            entry = self.confirm_list.get_current_entry()
            if entry.get().lower() == "yes":
                new_tracks = self._remove_track_from_playlist(self.track_to_remove, self.current_context)
                self.tracks_list.update_list(new_tracks)
            self.track_to_remove = None
            switch_to_tracks_state()
        remove_track_confirm_state.bind_key(self.ENTER_KEYS, enter)
        self.remove_track_confirm_state = remove_track_confirm_state

        #
        # Remove Playlist State - Handles removing a playlist
        #
        remove_playlist_confirm_state = State("remove_playlist_confirm", self.confirm_list)
        remove_playlist_confirm_state.bind_key(uc.KEY_UP, move_up_current_list)
        remove_playlist_confirm_state.bind_key(uc.KEY_DOWN, move_down_current_list)

        def cancel():
            self.playlist_to_remove = None
            switch_to_user_state()
        remove_playlist_confirm_state.bind_key(self.CANCEL_KEYS, cancel)

        def enter():
            entry = self.confirm_list.get_current_entry()
            if entry.get().lower() == "yes":
                self._remove_playlist(self.playlist_to_remove)
                self._load_playlists()
            self.playlist_to_remove = None
            switch_to_user_state()
        remove_playlist_confirm_state.bind_key(self.ENTER_KEYS, enter)
        self.remove_playlist_confirm_state = remove_playlist_confirm_state

        #
        # Player State - Handles commands while in the player pane
        #
        player_state = State("player", self.player_list)
        player_state.bind_key(uc.KEY_UP, switch_to_tracks_state)
        def left():
            if self.current_state.get_list().i == 0:
                switch_to_user_state()
            else:
                move_up_current_list()
        player_state.bind_key(uc.KEY_LEFT, left)

        def right():
            cur_list = self.current_state.get_list()
            if cur_list.i == (len(cur_list) - 1):
                switch_to_other_actions_state()
            else:
                move_down_current_list()
        player_state.bind_key(uc.KEY_RIGHT, right)

        def enter():
            self.player_list.get_current_entry().action()
        player_state.bind_key(self.ENTER_KEYS, enter)

        self.player_state = player_state

        #
        # Other Actions State - Handles commands for other actions in the player window
        #
        other_actions_state = State("other_actions", self.other_actions_list)
        other_actions_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        other_actions_state.bind_key(uc.KEY_LEFT, switch_to_player_state)
        other_actions_state.bind_key(uc.KEY_RIGHT, switch_to_user_state)

        def up():
            if self.current_state.get_list().i == 0:
                switch_to_tracks_state()
            else:
                move_up_current_list()
        other_actions_state.bind_key(uc.KEY_UP, up)
        
        def enter():
            self.other_actions_list.get_current_entry().action()
        other_actions_state.bind_key(self.ENTER_KEYS, enter)

        self.other_actions_state = other_actions_state

        #
        # Creaintg Command State - Handles commands while user is typing in a command
        #
        creating_command_state = State("creating_command")

        def left():
            self.text_query.cursor_left()
        creating_command_state.bind_key(uc.KEY_LEFT, left)

        def right():
            self.text_query.cursor_right()
        creating_command_state.bind_key(uc.KEY_RIGHT, right)

        def up():
            self.cmd.back()
            self.text_query = TextQuery(self.cmd.get_command())
        creating_command_state.bind_key(uc.KEY_UP, up)

        def down():
            self.cmd.forward()
            self.text_query = TextQuery(self.cmd.get_command())
        creating_command_state.bind_key(uc.KEY_DOWN, down)

        def backspace():
            if not self.text_query.empty():
                self.text_query.delete()
            else:
                self.switch_to_state(self.tracks_state)
        creating_command_state.bind_key(self.BACKSPACE_KEYS, backspace)

        def ascii_key(key):
            char = chr(key)
            self.text_query.insert(char)
        creating_command_state.bind_key(list(range(32, 128)), ascii_key)

        def enter():
            self.cmd.process_command(self.text_query, save=True)
            self.text_query.clear()
        creating_command_state.bind_key(self.ENTER_KEYS, enter)

        creating_command_state.bind_key([uc.KEY_EXIT, 27], switch_to_prev_state)

        self.creating_command_state = creating_command_state

        #
        # Search State - Handles commands while user is searching
        #
        search_state = State("search", self.search_list)
        search_state.bind_key(uc.KEY_UP, move_up_current_list)
        search_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        search_state.bind_key(self.BACKSPACE_KEYS + self.CANCEL_KEYS, switch_to_prev_state)

        def right():
            entry = self.search_list.get_current_entry()
            if entry['type'] == 'album':
                self.current_state = tracks_state
                self._set_album(entry)
            elif entry['type'] == 'artist':
                albums = self.api.get_albums_from_artist(entry)
                if albums is not None:
                    self.search_menu['results'].update_list(albums)
        search_state.bind_key(uc.KEY_RIGHT, right)

        def enter():
            entry = self.search_list.get_current_entry()
            if entry:
                if entry['type'] == 'artist':
                    self._set_artist(entry)
                elif entry['type'] == 'album':
                    self._set_album(entry)
                elif entry['type'] == 'playlist':
                    self._set_playlist(entry)
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
        device_state.bind_key(self.BACKSPACE_KEYS + self.CANCEL_KEYS, switch_to_prev_state)

        def enter():
            new_device = self.device_list.get_current_entry()
            if new_device:
                self._set_player_device(new_device, self.playing)
                switch_to_tracks_state()
        device_state.bind_key(self.ENTER_KEYS, enter)

        self.device_state = device_state

        #
        # Help State - Handles commands while user is in the help menu
        #
        help_state = State("help", self.help_list)
        help_state.bind_key(uc.KEY_UP, move_up_current_list)
        help_state.bind_key(uc.KEY_DOWN, move_down_current_list)
        help_state.bind_key(self.BACKSPACE_KEYS + self.CANCEL_KEYS + [self.config.toggle_help], 
                            switch_to_prev_state)

        self.help_state = help_state

        #
        # Command commands for all of the main states
        #
        main_states = [user_state, tracks_state, player_state, other_actions_state, search_state]

        bind_to_all(main_states, self.BACKSPACE_KEYS, self.restore_previous_tracks)
        bind_to_all(main_states, self.config.toggle_help, switch_to_help_state)

        def start_command(key):
            char = chr(key)
            self._set_command_query(char)
            self.switch_to_state(self.creating_command_state)

        bind_to_all(main_states, [ord(c) for c in self.cmd.get_triggers()], start_command)

        def find_next():
            toks = self.cmd.get_prev_cmd_toks()
            if toks[0] == "find":
                i = int(toks[1])
                command = toks
                command[1] = str(i + 1)
                self.cmd.process_command(" ".join(command))
        bind_to_all(main_states, self.config.find_next, find_next)

        def find_prev():
            toks = self.cmd.get_prev_cmd_toks()
            if toks[0] == "find":
                i = int(toks[1])
                command = toks
                command[1] = str(i - 1)
                self.cmd.process_command(" ".join(command))
        bind_to_all(main_states, self.config.find_previous, find_prev)

        def show_devices():
            self.switch_to_state(self.device_state)
            self.sync_devices.activate()
        bind_to_all(main_states, self.config.show_devices, show_devices)

        bind_to_all(main_states, self.config.refresh, self.sync_player_state)

        def current_artist():
            entry = self.currently_playing_track
            if entry is not NoneTrack:
                artists = entry['artists']
                if len(artists) == 1:
                    self._set_artist(artists[0])
                else:
                    self._update_artist_list(artists)
        bind_to_all(main_states, self.config.current_artist, current_artist)

        def current_album():
            entry = self.currently_playing_track
            if entry is not NoneTrack:
                album = entry['album']
                self._set_album(album)
        bind_to_all(main_states, self.config.current_album, current_album)

        def current_context():
            state = self.api.get_player_state()
            if state is not None:
                context = state.get("context")
                if context is None:
                    self.alert.warn("Unable to go to currently playing context!")
                else:
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

        def volume(key):
            config_param = self.config.get_config_param(key)
            volume = 10 * int(config_param.split("_")[1])
            self.cmd.process_command("volume {}".format(volume))
        bind_to_all(main_states, self.config.get_volume_keys(), volume)

        def volume_down():
            self.cmd.process_command("volume {}".format(self.volume - 5))
        def volume_up():
            self.cmd.process_command("volume {}".format(self.volume + 5))
        bind_to_all(main_states, self.config.volume_down, volume_down)
        bind_to_all(main_states, self.config.volume_up, volume_up)

        #
        # Loading State - The loading state when the program is making a long query
        #
        loading_state = State("loading")

        def loading():
            # Nothing to do here, go back.
            if not self.futures:
                if self.next_future_state is not None:
                    self.switch_to_state(self.next_future_state)
                    self.next_future_state = None
                else:
                    self.logger.info("Invalid next state, going to previous.")
                    switch_to_prev_state()
            else:
                # Get the current Future.
                future = self.futures[0]

                # If it's done, leave the loading_state.
                # If this Future doesn't have progress information, don't wait for it.
                # But if there are more Futures to execute, continue to run them.
                if future.is_done() or future.get_progress() is None:
                    with future_lock:
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
            self.switch_to_state(self.a2p_confirm_state)
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
                switch_to_tracks_state()
        select_artist_state.bind_key(self.ENTER_KEYS, enter)
        self.select_artist_state = select_artist_state

        #
        # Adding a playlist
        #
        def create_playlist():
            self._set_command_query(":create_playlist ")
            self.switch_to_state(self.creating_command_state)
        bind_to_all(main_states, self.config.create_playlist, create_playlist)

        #
        # Seek
        #
        def start_seek():
            self._set_command_query(":seek ")
            self.switch_to_state(self.creating_command_state)
        bind_to_all(main_states, self.config.seek, start_seek)

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

    def __init__(self, target, result=(), use_return=False, progress=True):
        """Constructor.

        Args:
            target (func, tuple): Contains the target function, args, and kwargs.
                The target function must accept a keyword argument 'progress'
                that is a Progress object.
            result (tuple): Contains the result function, args and kwargs.
            use_return (bool): If True, pass the return value in as the first argument
                of the result function.
            progress (bool): True if this Future operation has progress. If False,
                the program will not wait on it or show progress information.
        """
        def to_iter(obj):
            if isinstance(obj, (tuple, list)):
                return obj
            else:
                return (obj,)

        target = to_iter(target)

        result = to_iter(result)

        self.use_return = use_return
        """If True, pass the return value in as the first argument of the result function."""

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

        self.has_progress = progress
        """True if this Future operation has progress."""

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
            if self.use_return:
                self.result_func(result, *self.result_args, **self.result_kwargs)
            else:
                self.result_func(*self.result_args, **self.result_kwargs)

        # Notify that we're done.
        self.event.set()

    def wait(self):
        self.event.wait()

    def get_progress(self):
        return self.progress.get_percent() if self.has_progress else None

    def is_done(self):
        return self.event.is_set()

    def __str__(self):
        return str((self.target_func.__name__, self.target_args, self.target_kwargs)) + " -> " +\
            str((self.result_func.__name__, self.result_args, self.result_kwargs))


class Progress(object):
    """Represents the amount of work complete."""

    def __init__(self):
        """Constructor."""
        self.percent_done = 0.0
        """The amount done."""

        self.lock = RLock()
        """A lock for the object."""

    def set_percent(self, percent):
        with self.lock:
            self.percent_done = percent

    def get_percent(self):
        return self.percent_done


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

    def __str__(self):
        return self.desc


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

    def set_default_action(self, func, desc=""):
        """Sets the default action of this state.

        Args:
            action (Action): The default Action.
        """
        self._default_action = Action(func, desc)

    def bind_key(self, key, func, desc=""):
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

    def get_actions(self):
        return self._actions

    def __str__(self):
        return self._name


class Alert(object):
    """Represents a informational warning to the user."""

    def __init__(self):
        self.message = ""
        """The message to displaty."""

        self.time_left = 0
        """The amount of time left to display the message."""

    def warn(self, message, timeout=10):
        """Set an alert for the user.

        Args:
            message (str): The message to display.
            timeout (float): How long to display the message.
        """
        self.message = message
        self.time_left = timeout
        logger.warning("Alert: %s", message)

    def get_message(self):
        """Get the current message.

        Returns the current message if the Alert is active.

        Returns:
            str: The message. None if the Alert is not active.    
        """
        return self.message if self.is_active() else None

    def is_active(self):
        """If the Alert is active.

        An Alert is active if there is still time remaining.
        
        Returns:
            bool: True if there is time left in the Alert.
        """
        return self.time_left > 0

    def dec_time(self, amount):
        """Decrement the amount of time left in an Alert.

        Args:
            amount (float): How much time to decrement by.
        """
        self.time_left -= amount