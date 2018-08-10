import time
import unicurses as uc

import common

logger = common.logging.getLogger(__name__)


class Window(object):
    """Wrapper around a curses window."""

    def __init__(self, name, window):
        self.name = name
        self.window = window


class CursesDisplay(object):

    RENDER_PERIOD = 1

    UPDATE_PERIOD = 30

    def __init__(self, stdscr, sp_state):
        self.period = 0.05
        """The period to run the loop."""

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

        self._register_window("search_results", self._window_sizes["search"])
        self._register_window("select_player", self._window_sizes["select_player"])
        self._register_window("user", self._window_sizes["user"])
        self._register_window("tracks", self._window_sizes["tracks"])
        self._register_window("player", self._window_sizes["player"])

        self._next_update_time = time.time()
        self._last_render_time = time.time()
        self._last_key_pressed_time = time.time()

        # Initialize the display.
        self._init_curses()

    def _register_window(self, name, size):
        """Register a window

        Args:
            size (tuple): The size of the window.
            name (str): The name of the window.
        """
        self._windows[name] = Window(name, uc.newwin(*size))
        self._panels[name] = uc.new_panel(self._windows[name].window)
        self._ordered_windows.append(self._windows[name])

    def _resize_window(self, name, size):
        """Register a window

        Args:
            size (tuple): The size of the window.
            name (str): The name of the window.
        """
        uc.wresize(self._windows[name].window, size[0], size[1])
        uc.wmove(self._windows[name].window, size[2], size[3])

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
            with common.ContextDuration() as t:
                # Handle user input.
                pressed = self.process_input()

                # Are we still running?
                self._running = self.state.is_running()

                # Do any calculations related to rendering.
                self.render_calcs()

                # Render the display if needed.
                rerender = (time.time() - self._last_render_time) > self.RENDER_PERIOD
                if pressed or rerender:
                    self.render()
                    self._last_render_time = time.time()

            # Sleep for an amount of time.
            sleep_time = self.period - t.duration
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                logger.debug("Cycle took %fs", t.duration)

        # Tear down the display.
        logger.debug("Tearing down curses display")
        uc.endwin()
        common.clear()

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
            self._last_key_pressed_time = time.time()
            key_pressed = True
            key = self._key_buf.pop()

            # Enter key
            if key in [13, 10]:
                # We probably just selected a Track, let's plan to update the
                # currently playing track in 1 second.
                self._next_update_time = time.time() + 1

            self.state.process_key(key)

        return key_pressed

    def render_calcs(self):
        """Perform any calculations related to rendering."""
        if time.time() > self._next_update_time and \
           (time.time() - self._last_key_pressed_time) < 10:
            self.sync_player()

    def render(self):
        # Clear the screem before rendering anything.
        uc.erase()

        # Set the panel order based on what action is going on.
        self.set_panel_order()

        # Update the panel size incase the terminal size changed.
        self.update_panel_size()

        # Draw all of the panels.
        self.render_user_panel()
        self.render_track_panel()
        self.render_player_panel()
        self.render_footer()
        self.render_search_panel()
        self.render_select_player_panel()

        # Required.
        uc.update_panels()
        uc.doupdate()

    def set_panel_order(self):
        if self.is_active_window("search_results"):
            uc.top_panel(self._panels["search_results"])
        elif self.is_active_window("select_player"):
            uc.top_panel(self._panels["select_player"])
        else:
            for panel_name, panel in self._panels.items():
                if panel_name not in ["search_results", "select_player"]:
                    uc.top_panel(panel)

    def update_panel_size(self):
        self._resize_window("search_results", self._window_sizes["search"])
        self._resize_window("select_player", self._window_sizes["select_player"])
        self._resize_window("user", self._window_sizes["user"])
        self._resize_window("tracks", self._window_sizes["tracks"])
        self._resize_window("player", self._window_sizes["player"])

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
        playlists = [str(playlist) for playlist in self.state.main_menu.get_list('user')]
        selected_i = self.state.main_menu["user"].i
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
                      self.state.main_menu['tracks'].header, cols-3, uc.A_BOLD)

        # Show the tracks.
        selected_i = self.state.main_menu['tracks'].i
        track_start_line = title_start_line + 2
        tracks = [track.str(cols-3) for track in self.state.main_menu.get_list('tracks')]
        self._render_list(win, tracks, track_start_line, rows-4,
                          2, cols-3, selected_i, self.is_active_window("tracks"))

    def render_player_panel(self):
        win, rows, cols = self._init_render_window("player")

        # Draw border.
        uc.box(win)

        uc.mvwaddnstr(win, 1, 2, self.state.get_currently_playing_track().track, cols-3, uc.A_BOLD)
        uc.mvwaddnstr(win, 2, 2, self.state.get_currently_playing_track().album, cols-3, uc.A_BOLD)
        uc.mvwaddnstr(win, 3, 2, self.state.get_currently_playing_track().artist, cols-3, uc.A_BOLD)
        uc.mvwaddnstr(win, 7, 2, self.state.current_device, cols-3, uc.A_NORMAL)

        for i, action in enumerate(self.state.main_menu.get_list("player")):
            if (i == self.state.main_menu['player'].i) and self.is_active_window("player"):
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            uc.mvwaddstr(win, 5, 2 + i*4, action.title, style)

    def render_footer(self):
        if self.state.is_creating_command():
            start_col = 1
            text = "".join(self.state.get_command_query()) + " "
            uc.mvwaddstr(self.stdscr, self._rows-1, start_col, text)
            uc.mvwaddstr(self.stdscr,
                         self._rows-1, start_col+self.state.get_cursor_i(),
                         text[self.state.get_cursor_i()],
                         uc.A_STANDOUT)
        else:
            text = self.state.main_menu.get_current_list_entry().str(self._cols)
            uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_BOLD)

    def render_search_panel(self):
        win, rows, cols = self._init_render_window("search_results")
        uc.box(win)

        # Show the title of the context.
        title_start_line = 1
        uc.mvwaddnstr(win, title_start_line, 2,
                      "Search Results", cols-3, uc.A_BOLD)

        selected_i = self.state.search_menu.get_current_list().i
        self._render_list(win, self.state.search_menu["search_results"], 3, rows-4, 2, cols-3, selected_i, self.is_active_window("search_results"))

    def render_select_player_panel(self):
        win, rows, cols = self._init_render_window("select_player")
        uc.box(win)

        # Show the title of the context.
        title_start_line = 1
        uc.mvwaddnstr(win, title_start_line, 2,
                      "Select a Player", cols-3, uc.A_BOLD)

        selected_i = self.state.select_player_menu.get_current_list().i
        self._render_list(win, self.state.select_player_menu["players"], 3, rows-4, 2, cols-3, selected_i, self.is_active_window("select_player"))


    def _render_list(self, win, list, row_start, n_rows,
                     col_start, n_cols, selected_i, is_active):
        n_elems = len(list)
        start_entry_i = common.clamp(selected_i - n_rows/2,
                                     0, max(n_elems-n_rows, 0))
        end_entry_i = start_entry_i + n_rows
        display_list = list[start_entry_i:end_entry_i]

        for i, text in enumerate(display_list):
            if i == (selected_i-start_entry_i) and is_active:
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            uc.mvwaddnstr(win, row_start+i, col_start, text, n_cols, style)

    def sync_player(self):
        self.state.sync_player_state()
        self._next_update_time = time.time() + self.UPDATE_PERIOD

    def is_active_window(self, window_name):
        if self.state.in_search_menu():
            return window_name == "search_results"
        elif self.state.in_select_player_menu():
            return window_name == "select_player"
        else:
            return self.state.main_menu.get_current_list().name == window_name

    def get_cur_window(self):
        return self._ordered_windows[self.state.main_menu.list_i]

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

    @property
    def _window_sizes(self):
        user = (self._rows-2,
                self._cols/4,
                0,
                0)
        tracks = (self._rows*2/3,
                  self._cols-(user[1])-1,
                  0,
                  user[1]+user[3])
        player = (self._rows-tracks[0]-2,
                  tracks[1],
                  tracks[0],
                  tracks[3])
        search = (self._rows*8/10,
                  self._cols*8/10,
                  self._rows/10,
                  self._cols/10)
        select_player = (self._rows*6/10,
                         self._cols*6/10,
                         self._rows*2/10,
                         self._cols*2/10)

        return {
            "user": user,
            "tracks": tracks,
            "player": player,
            "search": search,
            "select_player": select_player
        }
