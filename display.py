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
    # How often to sync up the player state.
    SYNC_PERIOD = 60 * 5

    # How often to run the program loop.
    PROGRAM_PERIOD = 0.01

    # How often to re-render.
    # For now, this is the same as the program loop.
    # Will need to investigate the performance impact of this.
    RENDER_PERIOD = PROGRAM_PERIOD

    # How often to clear the screen.
    CLEAR_PERIOD = 60 * 10

    def __init__(self, stdscr, sp_state):
        self.state = sp_state
        """The SpotifyState object."""

        self.stdscr = stdscr
        """The unicurses standard window."""

        self._panels = {}
        """Panels."""

        self._windows = {}
        """Windows."""

        self._running = True
        """Whether to continue running."""

        self._ordered_windows = []
        """Windows in an odered list."""

        self._register_window("popup", self._window_sizes["popup"])
        self._register_window("search_results", self._window_sizes["search"])
        self._register_window("select_player", self._window_sizes["select_player"])
        self._register_window("user", self._window_sizes["user"])
        self._register_window("tracks", self._window_sizes["tracks"])
        self._register_window("player", self._window_sizes["player"])

        self.sync_period = common.PeriodicCallback(self.SYNC_PERIOD, self.sync_player)

        self.periodic_callbacks = [
            self.sync_period,
            common.PeriodicCallback(self.RENDER_PERIOD, self.render),
            common.PeriodicCallback(self.CLEAR_PERIOD, self.clear),
        ]

        # This increments each control loop. A value of -50 means that we'll have
        # 2.5s (50 * PROGRAM_LOOP) until the footer begins to roll.
        self._footer_roll_index = -50

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
            # Time how long it takes to process input
            # and render the screen.
            with common.ContextDuration() as t:
                # Handle user input.
                pressed = self.process_input()

                # Do any calculations related to rendering.
                self.render_calcs()

                # Execute the periodic call backs.
                for pc in self.periodic_callbacks:
                    pc.update(time.time())

            # Are we still running?
            self._running = self.state.is_running()

            # Sleep for an amount of time.
            sleep_time = self.PROGRAM_PERIOD - t.duration
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
        key_buf = []
        for win in self.get_windows():
            key = uc.wgetch(win)
            if key != -1:
                key_buf.append(key)

        key_pressed = False
        while key_buf:
            call_time = time.time()
            key_pressed = True
            key = key_buf.pop()

            # Enter key
            if key in [13, 10]:
                # We probably just selected a Track, let's plan
                # to re-sync in 5s.
                self.sync_period.call_in(5)

            self.state.process_key(key, call_time)

        # If we didn't press a key, kick the state anyway.
        if not key_pressed:
            self.state.process_key(None, time.time())

        return key_pressed

    def render_calcs(self):
        """Perform any calculations related to rendering."""

    def render(self):
        # Set the panel order based on what action is going on.
        self.set_panel_order()

        # Update the panel size incase the terminal size changed.
        self.update_panel_size()

        # Clear the screen.
        uc.erase()

        # Draw all of the panels.
        self.render_user_panel()
        self.render_track_panel()
        self.render_player_panel()
        self.render_footer()
        self.render_search_panel()
        self.render_select_player_panel()
        self.render_popup_panel()

        # Required.
        uc.update_panels()
        uc.doupdate()

    def clear(self):
        uc.erase()
        uc.move(0, 0)
        uc.clrtobot()
        uc.refresh()

    def set_panel_order(self):
        if self.is_active_window("popup"):
            uc.top_panel(self._panels["popup"])
        elif self.is_active_window("search_results"):
            uc.top_panel(self._panels["search_results"])
        elif self.is_active_window("select_player"):
            uc.top_panel(self._panels["select_player"])
        else:
            for panel_name, panel in self._panels.items():
                if panel_name not in ["search_results", "select_player", "popup"]:
                    uc.top_panel(panel)

    def update_panel_size(self):
        self._resize_window("popup", self._window_sizes["popup"])
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

        # Show the display_name.
        display_name_start_line = 1
        uc.mvwaddnstr(win, display_name_start_line, 2,
                      self.state.get_display_name(),
                      cols-3,
                      uc.A_BOLD)

        # Show the playlists.
        playlists = [str(playlist) for playlist in self.state.main_menu['user']]
        selected_i = self.state.main_menu["user"].i
        playlist_start_line = display_name_start_line + 2
        self._render_list(win, playlists, playlist_start_line, rows-4,
                          2, cols-3, selected_i, self.is_active_window("user"))

    def render_track_panel(self):
        win, rows, cols = self._init_render_window("tracks")

        # Draw border.
        uc.box(win)

        # Show the title of the context.
        title_start_row = 1
        uc.mvwaddnstr(win, title_start_row, 2,
                      self.state.main_menu['tracks'].header, cols-3, uc.A_BOLD)

        # Show the tracks.
        selected_i = self.state.main_menu['tracks'].i
        track_start_line = title_start_row + 2
        tracks = [track.str(cols-3) for track in self.state.main_menu['tracks']]
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

        for i, action in enumerate(self.state.main_menu["player"]):
            if (i == self.state.main_menu['player'].i) and self.is_active_window("player"):
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            uc.mvwaddstr(win, 5, 2 + i*4, action.title, style)

    def render_footer(self):
        if self.state.is_loading():
            percent = self.state.get_loading_progress()
            text = " " * int(self._cols * percent)
            uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_STANDOUT)

        elif self.state.is_adding_track_to_playlist():
            text = "Select a playlist to add this track"
            uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_BOLD)

        elif self.state.is_creating_command():
            start_col = 1
            text = "".join(self.state.get_command_query()) + " "
            uc.mvwaddstr(self.stdscr, self._rows-1, start_col, text)
            uc.mvwaddstr(self.stdscr,
                         self._rows-1, start_col+self.state.get_cursor_i(),
                         text[self.state.get_cursor_i()],
                         uc.A_STANDOUT)
        else:
            entry = self.state.current_menu.get_current_list_entry()
            if entry:
                ncols = self._cols-1
                short_str = entry.str(ncols)
                long_str = str(entry)

                # Check if we need to scroll or not.
                if "".join(short_str.split()) == "".join(long_str.split()):
                    uc.mvwaddstr(self.stdscr, self._rows-1, 0, short_str, uc.A_BOLD)
                    # This ensures that we always start form the same position
                    # when we go from a static footer to a long footer that needs rolling.
                    self._footer_roll_index = -50
                else:
                    self._footer_roll_index += 1
                    footer_roll_index = 0 if self._footer_roll_index < 0 else self._footer_roll_index
                    footer_roll_index /= 10
                    # Double the string length so that we always uniformly roll
                    # even in the case the entire string length is less than the terminal width.
                    # Also, add a border to easily identify the end.
                    long_str = 2 * (long_str + " | ")
                    text = list(long_str)
                    for _ in xrange(footer_roll_index):
                        text.append(text.pop(0))
                    text = "".join(text)
                    text = text[0:ncols]
                    uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_BOLD)

        # Track progress bar
        progress = self.state.get_track_progress()
        if progress:
            percent = float(progress[0])/progress[1]
            text = "-"*int(self._cols*percent)
            uc.mvwaddnstr(self.stdscr, self._rows-2, 0, text, self._cols, uc.A_BOLD)

            # Song is done. Let's plan to re-sync in 1 second.
            if percent > 1.0:
                logger.debug("Reached end of song. Re-syncing in 1s.")
                self.sync_period.call_in(1)
                self.state.progress = None

    def render_search_panel(self):
        win, rows, cols = self._init_render_window("search_results")
        uc.box(win)
        n_display_cols = cols - 4

        # Show the title of the context.
        title_start_row = 1
        uc.mvwaddnstr(win,
                      title_start_row, 2,
                      self.state.search_menu["search_results"].header,
                      n_display_cols, uc.A_BOLD)

        # Show the results.
        results = [r.str(n_display_cols) for r in self.state.search_menu["search_results"]]
        selected_i = self.state.search_menu.get_current_list().i
        self._render_list(win,
                          results,
                          3, rows-4,
                          2, n_display_cols,
                          selected_i,
                          self.is_active_window("search_results"))

    def render_select_player_panel(self):
        win, rows, cols = self._init_render_window("select_player")
        uc.box(win)

        # Show the title of the context.
        title_start_row = 1
        uc.mvwaddnstr(win, title_start_row, 2,
                      "Select a Player", cols-3, uc.A_BOLD)

        selected_i = self.state.select_player_menu.get_current_list().i
        self._render_list(win, self.state.select_player_menu["players"], 3, rows-4, 2, cols-3, selected_i, self.is_active_window("select_player"))

    def render_popup_panel(self):
        win, rows, cols = self._init_render_window("popup")
        uc.box(win)\

        current_popup_list = self.state.current_popup_menu.get_current_list()

        # Show the title of the context.
        prompt = current_popup_list.header
        title_start_row = 1
        uc.mvwaddnstr(win,
                      title_start_row,
                      (cols/2) - (len(prompt)/2) - 1,
                      prompt,
                      cols-3,
                      uc.A_BOLD)

        selected_i = current_popup_list.i
        list_start_row = title_start_row + 2
        self._render_list(win,
                          current_popup_list,
                          list_start_row, rows-list_start_row,
                          2, cols-4,
                          selected_i,
                          self.is_active_window("popup"),
                          centered=True)

    def _render_list(self, win, list, row_start, n_rows,
                     col_start, n_cols, selected_i, is_active,
                     centered=False):
        n_elems = len(list)
        start_entry_i = common.clamp(selected_i - n_rows/2,
                                     0, max(n_elems-n_rows, 0))
        end_entry_i = start_entry_i + n_rows
        display_list = list[start_entry_i:end_entry_i]

        for i, entry in enumerate(display_list):
            text = str(entry)
            if i == (selected_i-start_entry_i) and is_active:
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            if centered:
                w2 = (n_cols-col_start)/2
                n2 = len(text)/2
                uc.mvwaddnstr(win, row_start+i, col_start+w2-n2, text, n_cols, style)
            else:
                uc.mvwaddnstr(win, row_start+i, col_start, text, n_cols, style)

    def sync_player(self):
        self.state.sync_player_state()

    def is_active_window(self, window_name):
        if self.state.in_search_menu():
            return window_name == "search_results"
        elif self.state.in_select_player_menu():
            return window_name == "select_player"
        elif self.state.is_in_state(self.state.ADD_TO_PLAYLIST_CONFIRM_PLAYLIST) or \
                self.state.is_selecting_artist():
            return window_name == "popup"
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

        popup = (self._rows/4,
                   self._cols/4,
                   self._rows*3/8,
                   self._cols*3/8)

        return {
            "user": user,
            "tracks": tracks,
            "player": player,
            "search": search,
            "select_player": select_player,
            "popup": popup
        }
