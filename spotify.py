import string
import sys
import time
import unicurses as uc

from spotify_api import SpotifyApi
from model import SpotifyState
from globals import *
from util import *


logger = logging.getLogger(__name__)


class Window(object):
    """Wrapper around a curses window."""

    def __init__(self, name, window):
        self.name = name
        self.window = window


class CursesDisplay(object):

    RENDER_PERIOD = 1

    def __init__(self, stdscr, sp_state):
        self.state = sp_state
        """The SpotifyState object."""

        self.stdscr = stdscr
        """The unicurses standard window."""

        self._panels = {}
        """Panels."""

        self._windows = {}
        """Windows."""

        self._key_buf = []
        """Buffer of keys that were pressed."""

        self._running = True
        """Whether to continue running."""

        self._ordered_windows = []
        """Windows in an odered list."""

        # Add the windows.
        user = (self._rows-2, self._cols/4, 0, 0)
        self._windows['user'] = Window('user', uc.newwin(*user))
        self._panels['user'] = uc.new_panel(self._windows['user'].window)
        self._ordered_windows.append(self._windows['user'])

        tracks = (self._rows*2/3, (self._cols - 1 - (user[1])), 0, user[1]+user[3])
        self._windows['tracks'] = Window('tracks', uc.newwin(*tracks))
        self._panels['tracks'] = uc.new_panel(self._windows['tracks'].window)
        self._ordered_windows.append(self._windows['tracks'])

        player = (self._rows*1/3-2, tracks[1], tracks[0], tracks[3])
        self._windows['player'] = Window('player', uc.newwin(*player))
        self._panels['player'] = uc.new_panel(self._windows['player'].window)
        self._ordered_windows.append(self._windows['player'])

        search = (self._rows*8/10, self._cols*8/10, self._rows/10, self._cols/10)
        self._windows['search'] = Window('search', uc.newwin(*search))
        self._panels['search'] = uc.new_panel(self._windows['search'].window)
        self._ordered_windows.append(self._windows['search'])

        self._update_time = time.time()
        self._last_update_time = time.time()

        self._last_render_time = time.time()

        # Initialize the display.
        self._init_curses()

    def _init_curses(self):
        """Initialize the curses environment and windows."""
        for win in self.get_windows():
            # Make getch and getstr non-blocking.
            uc.nodelay(win, True)

            # Allow non-ascii keys.
            uc.keypad(win, True)

        # Don't echo text.
        uc.noecho()

        # Don't show the cursor.
        uc.curs_set(False)
        logger.debug("Curses display initialized")

    def start(self):
        logger.info("Starting curses display loop")
        # Initial render.
        self.render()

        while self._running:
            # Handle user input.
            pressed = self.process_input()

            # Are we still running?
            self._running = self.state.is_running()

            # Do any calculations related to rendering.
            self.render_calcs()

            # Render the display if needed.
            # TODO: Also render periodically.
            rerender = time.time()-self._last_render_time > self.RENDER_PERIOD
            if pressed or rerender:
                self.render()
                self._last_render_time = time.time()

            # Sleep for an amount of time.
            time.sleep(0.05)

        # Tear down the display.
        logger.debug("Tearing down curses display")
        uc.endwin()
        clear()

    def process_input(self):
        """Process all keyboard input.

        Returns:
            bool: True if a key was pressed.
        """
        for win in self.get_windows():
            key = uc.wgetch(win)
            if key != -1:
                self._key_buf.append(key)

        key_pressed = False
        while self._key_buf:
            key_pressed = True

            key = self._key_buf.pop()

            # Enter key
            if key in [13, 10]:
                self._update_time = time.time() + 1

            self.state.process_key(key)

        return key_pressed

    def render_calcs(self):
        if time.time() > self._update_time:
            self.update_currently_playing_track()

    def render(self):
        uc.erase()

        self.render_user_panel()
        self.render_track_panel()
        self.render_player_panel()
        self.render_footer()
        self.render_search_panel()

        # Required.
        uc.update_panels()
        uc.doupdate()

    def _init_render_window(self, window_name):
        win = self._windows[window_name].window
        uc.werase(win)
        rows, cols = uc.getmaxyx(win)
        return win, rows, cols

    def render_user_panel(self):
        win, rows, cols = self._init_render_window("user")

        # Draw border.
        uc.box(win)

        # Show the username.
        username_start_line = 1
        uc.mvwaddnstr(win, username_start_line, 2,
                      self.state.get_username(),
                      cols-3,
                      uc.A_BOLD)

        # Show the playlists.
        playlists = [str(playlist) for playlist in self.state.main_model.get_list('playlists')]
        selected_i = self.state.main_model.get_list_current_entry_i("playlists")
        playlist_start_line = username_start_line + 2
        self._render_list(win, playlists, playlist_start_line, rows-4,
                          2, cols-3, selected_i, self.is_active_window("user"))

    def render_track_panel(self):
        win, rows, cols = self._init_render_window("tracks")

        # Draw border.
        uc.box(win)

        # Show the title of the context.
        title_start_line = 1
        uc.mvwaddnstr(win, title_start_line, 2,
                      ascii(self.state.main_model['tracks'].header), cols-3, uc.A_BOLD)

        # Show the tracks.
        selected_i = self.state.main_model.get_list_current_entry_i('tracks')
        track_start_line = title_start_line + 2
        tracks = [track.str(cols-3) for track in self.state.main_model.get_list('tracks')]
        self._render_list(win, tracks, track_start_line, rows-4,
                          2, cols-3, selected_i, self.is_active_window("tracks"))

    def render_player_panel(self):
        win, rows, cols = self._init_render_window("player")

        # Draw border.
        uc.box(win)

        style = uc.A_BOLD
        uc.mvwaddnstr(win, 1, 1, self.state.get_currently_playing_track().track, cols-3, style)
        uc.mvwaddnstr(win, 2, 1, self.state.get_currently_playing_track().album, cols-3, style)
        uc.mvwaddnstr(win, 3, 1, self.state.get_currently_playing_track().artist, cols-3, style)

        for i, action in enumerate(self.state.main_model.get_list("player")):
            if (i == self.state.main_model.get_list_current_entry_i('player')) and self.is_active_window("player"):
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            uc.mvwaddstr(win, 5, cols/2 + i*4, action.title, style)

    def render_footer(self):
        if self.state.is_creating_command():
            start_col = 2
            text = "".join(self.state.get_command_query()) + " "
            uc.mvwaddstr(self.stdscr, self._rows-1, start_col, text)
            uc.mvwaddstr(self.stdscr,
                         self._rows-1, start_col+self.state.get_cursor_i(),
                         text[self.state.get_cursor_i()],
                         uc.A_STANDOUT)
        else:
            text = self.state.main_model.get_current_list_entry().str(self._cols-1)
            uc.mvwaddstr(self.stdscr, self._rows-1, 3, text, uc.A_BOLD)

    def render_search_panel(self):
        # Determine the correct panel order.
        # TODO: Move this out to a more generic function?
        if self.is_active_window("search"):
            uc.top_panel(self._panels["search"])
        else:
            for panel_name, panel in self._panels.items():
                if panel_name != "search":
                    uc.top_panel(panel)

        win, rows, cols = self._init_render_window("search")
        uc.box(win)

        # Show the title of the context.
        title_start_line = 1
        uc.mvwaddnstr(win, title_start_line, 2,
                      "Search Results", cols-3, uc.A_BOLD)

        selected_i = self.state.search_model.get_current_list().i
        self._render_list(win, self.state.search_model["results"], 3, rows-4, 2, cols-3, selected_i, self.is_active_window("search"))

    def _render_list(self, win, list, row_start, n_rows,
                     col_start, n_cols, selected_i, is_active):
        n_elems = len(list)
        start_entry_i = clamp(selected_i - n_rows/2,
                              0, max(n_elems-n_rows, 0))
        end_entry_i = start_entry_i + n_rows
        display_list = list[start_entry_i:end_entry_i]

        for i, text in enumerate(display_list):
            if i == (selected_i-start_entry_i) and is_active:
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            uc.mvwaddnstr(win, row_start+i, col_start, text, n_cols, style)

    def update_currently_playing_track(self):
        self.state.poll_currently_playing_track()
        self._last_update_time = self._update_time
        self._update_time = time.time()+30

    def is_active_window(self, window_name):
        if self.state.is_searching():
            return window_name == "search"
        else:
            return self.state.main_model.list_i == self.get_window_position(window_name)

    def get_window_position(self, window_name):
        for i, window in enumerate(self._ordered_windows):
            if window.name == window_name:
                return i

    def get_cur_window(self):
        return self._ordered_windows[self.state.main_model.list_i]

    def get_windows(self):
        return [w.window for w in self._windows.values()]

    def get_panels(self):
        return self._panels.values()

    @property
    def _rows(self):
        return uc.getmaxyx(self.stdscr)[0]

    @property
    def _cols(self):
        return uc.getmaxyx(self.stdscr)[1]


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: spotify.py [username]")
        exit(1)

    clear()
    print(TITLE)

    # Initialize the curses screen.
    stdscr = uc.initscr()

    # Create Spotify state.
    sp_state = SpotifyState(SpotifyApi(sys.argv[1]))

    # Create the display and start!
    display = CursesDisplay(stdscr, sp_state)
    display.start()
