import time

from . import common
from . import unicurses as uc
from .periodic import PeriodicCallback, PeriodicDispatcher


logger = common.logging.getLogger(__name__)


class Window(object):
    """Wrapper around a curses window."""

    def __init__(self, name, window):
        self.name = name
        self.window = window


class CursesDisplay(object):
    # Max amount of time to dispatch each cycle when the program is active.
    ACTIVE_PROGRAM_DISPATCH_TIME = 0.02

    # Max amount of time to dispatch each cycle when the program is idle.
    IDLE_PROGRAM_DISPATCH_TIME = 0.1

    # Max amount of time to dispatch each cycle when the program is sleeping.
    SLEEP_PROGRAM_DISPATCH_TIME = 0.4

    # How long to wait before declaring the program is not active and is idle.
    IDLE_TIMEOUT = 0.5

    # How long to wait before declaring the program is not idle and is sleeping.
    SLEEP_TIMEOUT = 5 * 60

    # How often to run the program loop when the user is actively using it.
    PROGRAM_PERIOD = 0.01

    # How often to re-render.
    RENDER_PERIOD = 0.01

    # How often to clear the screen.
    CLEAR_PERIOD = 60 * 15

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
        self._register_window("help", self._window_sizes["help"])
        self._register_window("search_results", self._window_sizes["search"])
        self._register_window("select_device", self._window_sizes["select_device"])
        self._register_window("user", self._window_sizes["user"])
        self._register_window("tracks", self._window_sizes["tracks"])
        self._register_window("player", self._window_sizes["player"])

        self.periodic_dispatcher = PeriodicDispatcher([
            PeriodicCallback(self.PROGRAM_PERIOD, self.dispatch),
            PeriodicCallback(self.RENDER_PERIOD, self.render),
            PeriodicCallback(self.CLEAR_PERIOD, self.clear)
        ])

        self.dispatch_time = self.ACTIVE_PROGRAM_DISPATCH_TIME

        # This increments each control loop. A value of -50 means that we'll have
        # 2s (200 * PROGRAM_LOOP) until the footer begins to roll.
        self._footer_roll_index = -200

        self.last_pressed_time = time.time()

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
        logger.info("Starting main loop")

        # Initial render.
        self.render()

        while self._running:
            with common.ContextDuration() as t:
                self.periodic_dispatcher.dispatch()

            time.sleep(max(0, self.dispatch_time - t.duration))

        # Tear down the display.
        logger.debug("Tearing down curses display")
        uc.endwin()
        common.clear()

    def dispatch(self):
        """Dispatch main program logic."""
        # Handle user input.
        self.process_input()

        # Do any calculations related to rendering.
        self.render_calcs()

        # Are we still running?
        self._running = self.state.is_running()

    def process_input(self):
        """Process all keyboard input."""
        key_pressed = False
        for win in self.get_windows():
            # Gather all key inputs.
            keys = []
            while True:
                k = uc.wgetch(win)
                if k != -1:
                    keys.append(k)
                else:
                    break
            
            # For now, we only process individual key commands.
            # Soemthing like "Shift + Left Arrow" will result in multiple
            # keys and could trigger unintentional commands.
            # Disallow this until we support these kinds of key combinations.
            if len(keys) == 1:
                key_pressed = True
                key = keys[0]
                self.last_pressed_time = time.time()
                self.state.process_key(key)

        # If we didn't press a key, kick the state anyway.
        if not key_pressed:
            self.state.process_key(None)

    def render_calcs(self):
        """Perform any calculations related to rendering."""
        # TODO: Make this state based?
        key_timeout = time.time() - self.last_pressed_time

        if key_timeout <= self.IDLE_TIMEOUT:
            self.dispatch_time = self.ACTIVE_PROGRAM_DISPATCH_TIME
        elif self.IDLE_TIMEOUT < key_timeout and key_timeout <= self.SLEEP_TIMEOUT:
            self.dispatch_time = self.IDLE_PROGRAM_DISPATCH_TIME
        elif self.SLEEP_TIMEOUT < key_timeout:
            self.dispatch_time = self.SLEEP_PROGRAM_DISPATCH_TIME

    def render(self):
        # Set the panel order based on what action is going on.
        self.set_panel_order()

        # Update the panel size incase the terminal size changed.
        # TODO: Doesn't work.
        self.update_panel_size()

        # Clear the screen.
        uc.erase()

        # Draw all of the panels.
        self.render_user_panel()
        self.render_track_panel()
        self.render_player_panel()
        self.render_footer()
        self.render_search_panel()
        self.render_select_device_panel()
        self.render_popup_panel()
        self.render_help_panel()

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
        elif self.is_active_window("select_device"):
            uc.top_panel(self._panels["select_device"])
        elif self.is_active_window("help"):
            uc.top_panel(self._panels["help"])
        else:
            for panel_name, panel in self._panels.items():
                if panel_name not in ["search_results", "select_device", "popup", "help"]:
                    uc.top_panel(panel)

    def update_panel_size(self):
        self._resize_window("popup", self._window_sizes["popup"])
        self._resize_window("help", self._window_sizes["help"])
        self._resize_window("search_results", self._window_sizes["search"])
        self._resize_window("select_device", self._window_sizes["select_device"])
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
        title_start_line = 1
        self._render_text(win, title_start_line, 2,
                          "[Spotify Terminal]",
                          cols-3,
                          uc.A_BOLD,
                          centered=True)

        # Show the display_name.
        display_name_start_line = title_start_line + 1
        self._render_text(win, display_name_start_line, 2,
                          self.state.get_display_name(),
                          cols-3,
                          uc.A_BOLD,
                          centered=True)

        # Bar.
        self._render_text(win, display_name_start_line+1, 1,
                          "_"*cols,
                          cols-2,
                          uc.A_NORMAL)

        # Show the playlists.
        playlists = [str(playlist) for playlist in self.state.user_list]
        selected_i = self.state.user_list.i
        playlist_start_line = display_name_start_line + 2
        self._render_list(win,
                          playlists,
                          playlist_start_line, rows-(playlist_start_line+1),
                          2, cols-3,
                          selected_i,
                          self.is_active_window("user"))

    def render_track_panel(self):
        win, rows, cols = self._init_render_window("tracks")

        # Draw border.
        uc.box(win)

        # Show the title of the context.
        title_start_row = 1
        self._render_text(win, title_start_row, 2,
                      self.state.tracks_list.header, cols-3, uc.A_BOLD)

        # Show the tracks.
        selected_i = self.state.tracks_list.i
        track_start_line = title_start_row + 2
        tracks = [track.str(cols-3) for track in self.state.tracks_list]
        self._render_list(win, tracks, track_start_line, rows-4,
                          2, cols-3, selected_i, self.is_active_window("tracks"))

    def render_player_panel(self):
        win, rows, cols = self._init_render_window("player")

        # Draw border.
        uc.box(win)

        # Display currently playing track
        self._render_text(win, 1, 2, self.state.get_currently_playing_track().track, cols-3, uc.A_BOLD)
        self._render_text(win, 2, 2, self.state.get_currently_playing_track().album, cols-3, uc.A_BOLD)
        self._render_text(win, 3, 2, self.state.get_currently_playing_track().artist, cols-3, uc.A_BOLD)

        # Display the current device
        device_info = "{} ({}%)".format(self.state.current_device, self.state.volume)
        self._render_text(win, 7, 2, device_info, cols-3, uc.A_NORMAL)

        # Display the media icons
        col = 2
        for i, action in enumerate(self.state.player_list):
            if ((i == self.state.player_list.i)
                    and self.state.current_state.get_list().name == "player"):
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            icon = action.title
            uc.mvwaddstr(win, 5, col, icon, style)
            col += len(icon) + 2

        # Display other actions
        col = cols//2
        self._render_list(win, self.state.other_actions_list, 
                          1, rows-1,
                          cols//2, (cols//2) - 2,
                          self.state.other_actions_list.i,
                          self.state.current_state.get_list().name == "other_actions")

    def render_footer(self):
        if self.state.is_loading():
            percent = self.state.get_loading_progress()
            if percent is not None:
                text = " " * int(self._cols * percent)
                uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_STANDOUT)
        elif self.state.is_adding_track_to_playlist():
            text = "Select a playlist to add this track"
            uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_BOLD)
        elif self.state.is_creating_command():
            start_col = 1
            query = self.state.get_command_query()
            text = str(query) + " "
            uc.mvwaddstr(self.stdscr, self._rows-1, start_col, text)
            uc.mvwaddstr(self.stdscr,
                         self._rows-1, start_col+query.get_cursor_index(),
                         query.get_current_index() or " ",
                         uc.A_STANDOUT)
        else:
            entry = self.state.current_state.get_list().get_current_entry()
            if entry:
                ncols = self._cols-1
                long_str = common.ascii(str(entry))
                short_str = entry.str(ncols) if hasattr(entry, "str") else long_str

                # Check if we need to scroll or not.
                if "".join(short_str.split()) == "".join(long_str.split()):
                    uc.mvwaddstr(self.stdscr, self._rows-1, 0, short_str, uc.A_BOLD)
                    # This ensures that we always start form the same position
                    # when we go from a static footer to a long footer that needs rolling.
                    self._footer_roll_index = -200
                else:
                    self._footer_roll_index += 1
                    footer_roll_index = max(0, self._footer_roll_index)
                    footer_roll_index //= 10
                    # Double the string length so that we always uniformly roll
                    # even in the case the entire string length is less than the terminal width.
                    # Also, add a border to easily identify the end.
                    long_str = 2 * (long_str + " | ")
                    text = list(long_str)
                    for _ in range(footer_roll_index):
                        text.append(text.pop(0))
                    text = "".join(text)
                    text = text[0:ncols]
                    uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_BOLD)
        
        if self.state.alert.is_active():
            text = self.state.alert.get_message()
            text = "[{}]".format(text)
            uc.mvwaddstr(self.stdscr, self._rows-1, 0, text, uc.A_STANDOUT)
        
        # Track progress bar
        progress = self.state.get_track_progress()
        if progress:
            percent = float(progress[0])/progress[1]
            text = "-"*int(self._cols*percent)
            self._render_text(self.stdscr, self._rows-2, 0, text, self._cols, uc.A_BOLD)

    def render_search_panel(self):
        win, rows, cols = self._init_render_window("search_results")
        uc.box(win)
        n_display_cols = cols - 4

        # Show the title of the context.
        title_start_row = 1
        self._render_text(win,
                          title_start_row, 2,
                          self.state.search_list.header,
                          n_display_cols, uc.A_BOLD)

        # Show the results.
        results = [r.str(n_display_cols) for r in self.state.search_list]
        selected_i = self.state.search_list.i
        self._render_list(win,
                          results,
                          3, rows-4,
                          2, n_display_cols,
                          selected_i,
                          self.is_active_window("search_results"))

    def render_select_device_panel(self):
        win, rows, cols = self._init_render_window("select_device")
        uc.box(win)

        # Show the title of the context.
        title_start_row = 1
        self._render_text(win,
                          title_start_row,
                          2,
                          "Select a Player",
                          cols-3,
                          uc.A_BOLD)

        selected_i = self.state.device_list.i
        self._render_list(win, self.state.device_list, 3, rows-4, 2, cols-3, selected_i, self.is_active_window("select_device"))

    def render_popup_panel(self):
        win, rows, cols = self._init_render_window("popup")
        uc.box(win)

        current_popup_list = self.state.current_state.get_list()

        # Show the title of the context.
        prompt = current_popup_list.header
        title_start_row = 1
        self._render_text(win,
                          title_start_row,
                          (cols//2) - (len(prompt)//2) - 1,
                          prompt,
                          cols-3,
                          uc.A_BOLD)

        selected_i = current_popup_list.i
        list_start_row = title_start_row + 2
        self._render_list(win,
                          current_popup_list,
                          list_start_row, rows - list_start_row - 1,
                          2, cols-4,
                          selected_i,
                          self.is_active_window("popup"),
                          centered=True)

    def render_help_panel(self):
        win, rows, cols = self._init_render_window("help")
        uc.box(win)

        current_help_list = self.state.current_state.get_list()

        # Show the title of the context.
        prompt = "Shortcuts"
        title_start_row = 1
        self._render_text(win,
                          title_start_row,
                          (cols//2) - (len(prompt)//2) - 1,
                          prompt,
                          cols-3,
                          uc.A_BOLD)

        selected_i = current_help_list.i
        list_start_row = title_start_row + 2
        self._render_list(win,
                          current_help_list,
                          list_start_row, rows - list_start_row - 1,
                          2, cols-4,
                          selected_i,
                          self.is_active_window("help"))

    def _render_list(self, win, list,
                     row_start, n_rows,
                     col_start, n_cols,
                     selected_i,
                     is_active,
                     centered=False):
        n_elems = len(list)
        start_entry_i = common.clamp(selected_i - n_rows//2,
                                     0, max(n_elems-n_rows, 0))
        end_entry_i = start_entry_i + n_rows
        display_list = list[start_entry_i:end_entry_i]

        for i, entry in enumerate(display_list):
            text = str(entry)
            if i == (selected_i-start_entry_i) and is_active:
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            self._render_text(win, row_start+i, col_start, text, n_cols, style, centered=centered)

    def _render_text(self, win, row, col, text, n_cols, style, centered=False):
        text = common.ascii(text)
        if centered:
            w2 = (n_cols-col)//2
            n2 = len(text)//2
            uc.mvwaddnstr(win, row, col+w2-n2, text, n_cols, style)
        else:
            uc.mvwaddnstr(win, row, col, text, n_cols, style)

    def is_active_window(self, window_name):
        if self.state.in_search_menu():
            return window_name == "search_results"
        elif self.state.in_select_device_menu():
            return window_name == "select_device"
        # TODO: This sucks, make it better.
        elif (self.state.is_in_state(self.state.a2p_confirm_state) 
              or self.state.is_selecting_artist()
              or self.state.is_in_state(self.state.remove_track_confirm_state)
              or self.state.is_in_state(self.state.remove_playlist_confirm_state)):
            return window_name == "popup"
        elif self.state.is_in_state(self.state.help_state):
            return window_name == "help"
        else:
            return self.state.current_state.get_list().name == window_name

    def get_windows(self):
        return [w.window for w in self._windows.values()]

    def get_panels(self):
        return list(self._panels.values())

    @property
    def _rows(self):
        return uc.getmaxyx(self.stdscr)[0]

    @property
    def _cols(self):
        return uc.getmaxyx(self.stdscr)[1]

    @property
    def _window_sizes(self):
        user = (self._rows-2,
                self._cols//4,
                0,
                0)
        tracks = (self._rows*2//3,
                  self._cols-(user[1])-1,
                  0,
                  user[1]+user[3])
        player = (self._rows-tracks[0]-2,
                  tracks[1],
                  tracks[0],
                  tracks[3])
        search = (self._rows*8//10,
                  self._cols*8//10,
                  self._rows//10,
                  self._cols//10)
        select_device = (self._rows*6//10,
                         self._cols*6//10,
                         self._rows*2//10,
                         self._cols*2//10)

        help = (self._rows*8//10,
                  self._cols*8//10,
                  self._rows//10,
                  self._cols//10)

        popup = (self._rows//4,
                   self._cols//4,
                   self._rows*3//8,
                   self._cols*3//8)

        return {
            "user": user,
            "tracks": tracks,
            "player": player,
            "search": search,
            "select_device": select_device,
            "help": help,
            "popup": popup
        }
