import time
import datetime

from . import common
from . import unicurses as uc
from .gui import WindowManager
from .periodic import PeriodicCallback, PeriodicDispatcher


logger = common.logging.getLogger(__name__)


class CursesDisplay(object):
    # How often to clear the screen if it gets garbled.
    CLEAR_PERIOD = 60 * 15

    # Max amount of time to dispatch each cycle when the program is active.
    ACTIVE_PROGRAM_DISPATCH_TIME = 0.01

    # Max amount of time to dispatch each cycle when the program is idle.
    IDLE_PROGRAM_DISPATCH_TIME = 0.1

    # Max amount of time to dispatch each cycle when the program is sleeping.
    SLEEP_PROGRAM_DISPATCH_TIME = 0.4

    # How long to wait before declaring the program is not active and is idle.
    ACTIVE_TO_IDLE_TIMEOUT = 0.5

    # How long to wait before declaring the program is not idle and is sleeping.
    IDLE_TO_SLEEP_TIMEOUT = 5 * 60

    POP_UP_WINDOW_NAMES = ["search", "help", "popup", "select_device"]

    ACTIVE_STATE, IDLE_STATE, SLEEP_STATE = (1, 2, 3)

    def __init__(self, sp_state):
        self.state = sp_state
        """The SpotifyState object."""

        self.activity_state = self.ACTIVE_STATE
        self.dispatch_time = self.ACTIVE_PROGRAM_DISPATCH_TIME
        """Active, idle, or sleep."""

        self.wm = WindowManager()
        """The WindowManager."""

        self.create_all_windows()
        
        self._running = True
        """Whether to continue running."""

        self.other_tasks = PeriodicDispatcher([
            PeriodicCallback(self.CLEAR_PERIOD, self.wm.clear)
        ])
        """Other tasks to run periodically."""

        # This increments each control loop. A value of -50 means that we'll have
        # 2s (200 * PROGRAM_LOOP) until the footer begins to roll.
        # TODO: Not valid for all activity states 
        self._footer_roll_index = -200

        self.last_pressed_time = time.time()

        self.dispatch_times = {
            self.ACTIVE_STATE: self.ACTIVE_PROGRAM_DISPATCH_TIME,
            self.IDLE_STATE: self.IDLE_PROGRAM_DISPATCH_TIME,
            self.SLEEP_STATE: self.SLEEP_PROGRAM_DISPATCH_TIME
        }
    def start(self):
        # Initial render.
        self.wm.render()

        logger.info("="*50)
        logger.info("Starting main loop")
        logger.info("="*50)

        while self._running:
            with common.ContextDuration() as t:
                self.process()
                self.render()
                self.other_tasks.dispatch()

            time.sleep(max(0, self.dispatch_time - t.duration))

        # Tear down the display.
        self.wm.exit()
        common.clear()

    def process(self):
        """Dispatch main program logic."""
        # Handle user input.
        self.process_input()

        # Do any calculations related to rendering.
        self.render_calcs()

        # Are we still running?
        self._running = self.state.is_running()

    def process_input(self):
        """Process all keyboard input."""
        # Gather all key inputs.
        key_pressed = False
        keys = []
        while True:
            k = self.wm.get_input()
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

        if key_timeout <= self.ACTIVE_TO_IDLE_TIMEOUT:
            self.activity_state = self.ACTIVE_STATE
        elif self.ACTIVE_TO_IDLE_TIMEOUT < key_timeout and key_timeout <= self.IDLE_TO_SLEEP_TIMEOUT:
            self.activity_state = self.IDLE_STATE
        elif self.IDLE_TO_SLEEP_TIMEOUT < key_timeout:
            self.activity_state = self.SLEEP_STATE

        self.dispatch_time = self.dispatch_times[self.activity_state]

        self.set_active_window()
        self.set_popup_window()

    def render(self):
        # Check if we need to resize.
        if self.wm.resize_requested():
            self.resize()

        # Draw all of the panels.
        self.render_user_panel()
        self.render_tracks_panel()
        self.render_player_panel()
        self.render_other_panel()
        self.render_footer()
        self.render_search_panel()
        self.render_select_device_panel()
        self.render_popup_panel()
        self.render_help_panel()
        
        # Render!
        self.wm.render()

    def render_user_panel(self):
        win = self.wm.get_window("user")
        rows, cols = win.get_size()
        win.erase()

        # Draw border.
        win.draw_box()

        # Show the display_name.
        title_start_line = 1
        win.draw_text(
            "[Spotify Terminal]",
            title_start_line, 2,
            cols-3,
            style=uc.A_BOLD,
            centered=True
        )

        # Show the display_name.
        display_name_start_line = title_start_line + 1
        win.draw_text(
            self.state.get_display_name(),
            display_name_start_line, 2,
            cols-3,
            style=uc.A_BOLD,
            centered=True
        )

        # Bar.
        win.draw_text(
            "_"*cols,
            display_name_start_line+1, 1,
            cols-2,
            style=uc.A_NORMAL
        )

        # Show the playlists.
        playlists = [str(playlist) for playlist in self.state.user_list]
        selected_i = self.state.user_list.i
        playlist_start_line = display_name_start_line + 2
        nplaylist_rows = rows-(playlist_start_line+1)
        win.draw_list(
            playlists,
            playlist_start_line, nplaylist_rows,
            2, cols-4,
            selected_i,
            scroll_bar=(playlist_start_line+1, cols-2, nplaylist_rows-1)
        )

    def render_tracks_panel(self):
        win = self.wm.get_window("tracks")
        rows, cols = win.get_size()
        win.erase()
        
        # Draw border.
        win.draw_box()

        # Show the title of the context.
        title_start_row = 1
        win.draw_text(
            self.state.tracks_list.header,
            title_start_row, 2,
            cols-3, 
            style=uc.A_BOLD
        )

        # Show the tracks.
        selected_i = self.state.tracks_list.i
        track_start_line = title_start_row + 2

        text_disp_width = cols-3
        tracks = []
        for track in self.state.tracks_list:
            track_str = track.str(text_disp_width-1) # +1 to account for >
            if track == self.state.get_currently_playing_track():
                track_str = ">"+track_str
            else:
                track_str = " "+track_str
            tracks.append(track_str)
        
        win.draw_list(
            tracks, 
            track_start_line, rows - 4,
            1, text_disp_width, 
            selected_i,
            scroll_bar=(2, cols-2, rows-3) 
        )


    def render_player_panel(self):
        win = self.wm.get_window("player")
        rows, cols = win.get_size()
        win.erase()
        
        # Draw border.
        win.draw_box()

        # Display currently playing track
        current_track = self.state.get_currently_playing_track()
        win.draw_text(current_track.track, 1, 2, cols-3, style=uc.A_BOLD)
        win.draw_text(current_track.album, 2, 2, cols-3, style=uc.A_BOLD)
        win.draw_text(current_track.artist, 3, 2, cols-3, style=uc.A_BOLD)

        if self.state.progress is not None:
            dur, total_dur = self.state.progress
            fmt = "%H:%M:%S" if total_dur >= 60 * 60 * 1000 else "%M:%S"
            dur = time.strftime(fmt, time.gmtime(dur//1000))
            total_dur = time.strftime(fmt, time.gmtime(total_dur//1000))
            win.draw_text("{} // {}".format(dur, total_dur), 4, 2, cols-3, style=uc.A_BOLD)

        # Display the current device
        device_info = "{} ({}%)".format(self.state.current_device, self.state.volume)
        win.draw_text(device_info, 8, 2, cols-3, style=uc.A_NORMAL)

        # Display the media icons
        col = 2
        for i, action in enumerate(self.state.player_list):
            if ((i == self.state.player_list.i)
                    and self.state.current_state.get_list().name == "player"):
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            icon = action.title
            win.draw_text(icon, 6, col, style=style)
            col += len(icon) + 2

    def render_other_panel(self):
        win = self.wm.get_window("other")
        rows, cols = win.get_size()
        win.erase()
        
        # Draw border.
        win.draw_tab_box()
        # Display other actions
        win.draw_list(
            self.state.other_actions_list, 
            1, rows-2,
            1, cols-1,
            self.state.other_actions_list.i
        )

    def render_footer(self):
        win = self.wm.get_window("footer")
        rows, cols = win.get_size()
        win.erase()

        if self.state.is_loading():
            percent = self.state.get_loading_progress()
            if percent is not None:
                text = " " * int(cols * percent)
                win.draw_text(text, rows-1, 0, style=uc.A_STANDOUT)
        elif self.state.is_adding_track_to_playlist():
            text = "Select a playlist to add this track"
            win.draw_text(text,  rows-1, 0, style=uc.A_BOLD)
        elif self.state.is_creating_command():
            start_col = 1
            query = self.state.get_command_query()
            text = str(query) + " "
            win.draw_text(text, rows-1, start_col)
            win.draw_text(
                query.get_current_index() or " ",
                rows-1, start_col+query.get_cursor_index(),
                style=uc.A_STANDOUT
            )
        else:
            entry = self.state.current_state.get_list().get_current_entry()
            if entry:
                ncols = cols-1
                long_str = common.ascii(str(entry))
                short_str = entry.str(ncols) if hasattr(entry, "str") else long_str

                # Check if we need to scroll or not.
                if "".join(short_str.split()) == "".join(long_str.split()):
                    win.draw_text(short_str, rows-1, 0, style=uc.A_BOLD)
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
                    win.draw_text(text, rows-1, 0, style=uc.A_BOLD)
        
        if self.state.alert.is_active():
            text = self.state.alert.get_message()
            text = "[{}]".format(text)
            win.draw_text(text, rows-1, 0, style=uc.A_STANDOUT)
        
        # Track progress bar
        progress = self.state.get_track_progress()
        if progress:
            percent = float(progress[0])/progress[1]
            text = "-"*int(cols*percent)
            win.draw_text(text, rows-2, 0, cols, style=uc.A_BOLD)

    def render_search_panel(self):
        win = self.wm.get_window("search")
        rows, cols = win.get_size()
        win.erase()
        
        win.draw_box()
        n_display_cols = cols - 4

        # Show the title of the context.
        title_start_row = 1
        win.draw_text(
            self.state.search_list.header,
            title_start_row, 2,
            n_display_cols, 
            style=uc.A_BOLD
        )

        # Show the results.
        results = [r.str(n_display_cols) for r in self.state.search_list]
        selected_i = self.state.search_list.i
        win.draw_list(
            results,
            3, rows-4,
            2, n_display_cols,
            selected_i
        )

    def render_select_device_panel(self):
        win = self.wm.get_window("select_device")
        rows, cols = win.get_size()
        win.erase()
        
        win.draw_box()

        # Show the title of the context.
        title_start_row = 1
        win.draw_text(
            "Searching...",
            title_start_row,
            2, cols-3,
            style=uc.A_BOLD
        )

        selected_i = self.state.device_list.i
        win.draw_list(
            self.state.device_list, 
            3, rows-4, 2, 
            cols-3, 
            selected_i
        )

    def render_popup_panel(self):
        win = self.wm.get_window("popup")
        rows, cols = win.get_size()
        win.erase()
        
        win.draw_box()

        current_popup_list = self.state.current_state.get_list()

        # Show the title of the context.
        prompt = current_popup_list.header
        title_start_row = 1
        win.draw_text(
            prompt,
            title_start_row,
            (cols//2) - (len(prompt)//2) - 1,
            cols-3,
            style=uc.A_BOLD
        )

        selected_i = current_popup_list.i
        list_start_row = title_start_row + 2
        win.draw_list(
            current_popup_list,
            list_start_row, rows - list_start_row - 1,
            2, cols-4,
            selected_i,
            centered=True
        )

    def render_help_panel(self):
        win = self.wm.get_window("help")
        rows, cols = win.get_size()
        win.erase()
        
        win.draw_box()

        current_help_list = self.state.current_state.get_list()

        # Show the title of the context.
        prompt = "Shortcuts"
        title_start_row = 1
        win.draw_text(
            prompt,
            title_start_row,
            (cols//2) - (len(prompt)//2) - 1,
            cols-3,
            style=uc.A_BOLD
        )

        selected_i = current_help_list.i
        list_start_row = title_start_row + 2
        win.draw_list(
            current_help_list,
            list_start_row, rows - list_start_row - 1,
            2, cols-4,
            selected_i
        )

    def set_active_window(self):
        popup_states = [
            self.state.a2p_confirm_state,
            self.state.remove_track_confirm_state,
            self.state.remove_playlist_confirm_state,
            self.state.select_artist_state
        ]

        playlist_states =[
            self.state.user_state,
            self.state.a2p_select_state
        ]

        if self.state.in_search_menu():
            window_name = "search"
        elif self.state.in_select_device_menu():
            window_name = "select_device"
        elif self.state.is_in_state(popup_states):
            window_name = "popup"
        elif self.state.is_in_state(self.state.help_state):
            window_name = "help"
        elif self.state.is_in_state(self.state.player_state):
            window_name = "player"
        elif self.state.is_in_state(self.state.other_actions_state):
            window_name = "other"
        elif self.state.is_in_state(self.state.tracks_state):
            window_name = "tracks"
        elif self.state.is_in_state(playlist_states):
            window_name = "user"
        else:
            window_name = "footer"

        self.wm.set_focus(window_name)

    def set_popup_window(self):
        for window_name in self.POP_UP_WINDOW_NAMES:
            window = self.wm.get_window(window_name)
            if window.get_focus():
                window.show()
            else:
                window.hide()

    def resize(self):
        self.wm.resize(self.get_window_sizes())

    def create_all_windows(self):
        sizes = self.get_window_sizes()

        self.wm.create_window("user", *sizes["user"])
        self.wm.create_window("tracks", *sizes["tracks"])
        self.wm.create_window("player", *sizes["player"])
        self.wm.create_window("other", *sizes["other"])
        self.wm.create_window("search", *sizes["search"])
        self.wm.create_window("select_device", *sizes["select_device"])
        self.wm.create_window("help", *sizes["help"])
        self.wm.create_window("popup", *sizes["popup"])
        self.wm.create_window("footer", *sizes["footer"])

        for name in self.POP_UP_WINDOW_NAMES:
            self.wm.get_window(name).hide()

    def get_window_sizes(self):
        rows, cols = self.wm.get_size()

        user = (rows-2,
                cols//4,
                0,
                0)

        tracks = (rows*2//3,
                  cols-(user[1])-1,
                  0,
                  user[1]+user[3])

        player = (rows-tracks[0]-2,
                  tracks[1],
                  tracks[0],
                  tracks[3])

        start = user[1]+(player[1]*2//3)
        other = (rows - tracks[0] - 2 - 3,
                 cols - start - 3,
                 player[2],
                 start)
        
        search = (rows*8//10,
                  cols*8//10,
                  rows//10,
                  cols//10)

        select_device = (rows*6//10,
                         cols*6//10,
                         rows*2//10,
                         cols*2//10)

        help = (rows*8//10,
                  cols*8//10,
                  rows//10,
                  cols//10)

        popup = (rows//4,
                   cols//4,
                   rows*3//8,
                   cols*3//8)

        footer = (2, cols, rows-2, 0)

        return {
            "user": user,
            "tracks": tracks,
            "player": player,
            "other": other,
            "search": search,
            "select_device": select_device,
            "help": help,
            "popup": popup,
            "footer": footer
        }