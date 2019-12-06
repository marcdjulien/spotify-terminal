from . import unicurses as uc

class Window(object):
    """A Window in the display."""

    def __init__(self, name, rows, cols, start_row, start_col):
        self.name = name
        """The name of the window."""

        self.row = start_row
        """The row to start drawing the box."""

        self.col = start_col
        """The col to start drawing the box."""

        self.rows = rows
        """The number of rows (or height) or the box."""

        self.cols = cols
        """The number of columns (or width) of the box."""

        self._uc_window = uc.newwin(rows, cols, start_row, start_col)
        """Unicurses Window object."""

        self._uc_panel = uc.new_panel(self._uc_window)
        """Unicurses Panel object."""

        self._focus = False
        """Whether this window is in focus."""

        self._init()

    def _init(self):
        """Initialize the Window."""    
        # Make getch and getstr non-blocking.
        uc.nodelay(self._uc_window, True)

        # Allow non-ascii keys.
        uc.keypad(self._uc_window, True)

    def set_focus(self, focus):
        """Set whether this Window is in focus.

        Args:
            focus (bool): Whether this Window is in Focus.
        """
        self._focus = focus

    def set_location(self, row, col):
        """The location of the Window.

        Args:
            row (int): The new row.
            col (int): The new column.
        """
        self.row = row
        self.col = col
        uc.move_panel(self._uc_panel, row, col)

    def resize(self, rows, cols):
        """Resize the Window.

        Args:
            rows (int): The new number of rows (or height).
            cols (int): The new number of columnss (or width).
        """
        self.rows = rows
        self.cols = cols
        self._uc_window = uc.newwin(rows, cols, self.row, self.col)
        uc.replace_panel(self._uc_panel, self._uc_window)

    def show(self):
        """Show the panel."""
        uc.show_panel(self._uc_panel)

    def hide(self):
        """Hide the panel."""
        uc.hide_panel(self._uc_panel)

    def draw_text(self, text, row=0, col=0, ncols=None, style=uc.A_NORMAL, centered=False):
        """Draw text on the window.

        Args:
            text (str): The text.
            row (int): The row to draw.
            col (int): The column to start drawing.
            ncols (int): Max columns to use.
            style (int): Unicurses style.
            centered (bool): Whether to center the text or not.
        """
        # TODO: put this back in
        #text = common.ascii(text)
        if ncols is None:
            ncols = len(text)

        if centered:
            w2 = (ncols - col) // 2
            n2 = len(text) // 2
            uc.mvwaddnstr(self._uc_window, row, col + w2 - n2, text, ncols, style)
        else:
            uc.mvwaddnstr(self._uc_window, row, col, text, ncols, style)

    def draw_list(self, texts, row, nrows, col, ncols, index, centered=False):
        """Draw text on the window.

        Args:
            text (iter): The collections of texts to display.
            row (int): The row to draw.
            nrows (int): Max rows to use.
            col (int): The column to start drawing.
            ncols (int): Max columns to use.
            i (int): An index to optionally highlight.
            centered (bool): Whether to center the text or not.
        """
        def clamp(value, low, high):
            return max(low, min(value, high))

        nelems = len(texts)
        start_entry_i = clamp(index - nrows//2, 0, max(nelems-nrows, 0))
        end_entry_i = start_entry_i + nrows
        display_list = texts[start_entry_i:end_entry_i]

        for i, entry in enumerate(display_list):
            # TODO: Santizie list before passing to this functions
            text = str(entry)
            if ((start_entry_i + i) == index) and self._focus:
                style = uc.A_BOLD | uc.A_STANDOUT
            else:
                style = uc.A_NORMAL
            self.draw_text(text,
                           row + i, 
                           col, 
                           ncols, 
                           style, 
                           centered=centered)

    def draw_box(self):
        """Draw a border around the Window."""
        uc.box(self._uc_window)

    def get_size(self):
        """Return the size of the window.

        Returns:
            tuple: The row and column size.
        """
        return self.rows, self.cols

    def erase(self):
        """Erase the Window."""
        uc.werase(self._uc_window)



class WindowManager(object):
    """Manages a set of Windows."""

    def __init__(self):
        self._stdscr = uc.initscr()
        """Standard window."""

        self._windows = {}
        """The Windows to manage."""

        # Don't echo text.
        uc.noecho()

        # Don't show the cursor.
        uc.curs_set(False)

        # Make getch and getstr non-blocking.
        uc.nodelay(self._stdscr, True)

        # Allow non-ascii keys.
        uc.keypad(self._stdscr, True)

    def create_window(self, name, start_row, start_col, rows, cols):
        """Create a new window."""
        err_msg = "A Window with this name already exists: {}".format(name)
        assert name not in self._windows, err_msg
        self._windows[name] = Window(
            name, 
            start_row, 
            start_col, 
            rows, 
            cols
        )

    def set_focus(self, name):
        """Set a Window to be the focus.

        Args
            name (str): The name of the Window.
        """
        for win in self._windows.values():
            win.set_focus(False)
        self.get_window(name).set_focus(True)


    def render(self):
        """Render everything."""
        uc.erase()

        #for window in self._windows.values():
            # TODO: Do we still need werase?
            #window.render()
        
        uc.update_panels()
        uc.doupdate()

    def clear(self):
        """Clear the entire screen."""
        uc.erase()
        uc.move(0, 0)
        uc.clrtobot()
        uc.refresh()

    def get_size(self):
        """Return the size of the main screen.

        Returns:
            tuple: (rows, cols)
        """
        return uc.getmaxyx(self._stdscr)

    def get_window(self, name):
        """Get a Window by name.

        Args
            name (str): The name of the Window.

        Returns:
            Window: The Window.
        """
        assert name in self._windows, "{} is not a valid window!".format(name)
        return self._windows[name]

    def get_input(self):
        """Get input from the screen.

        Returns:
            int: The key code. None if no input.
        """
        return uc.getch()

    def exit(self):
        """Clean up."""
        uc.endwin()

