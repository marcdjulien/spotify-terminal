#!/usr/bin/env python

import sys
import unicurses as uc

import common
from display import CursesDisplay
from spotify_api import SpotifyApi
from model import SpotifyState


logger = common.logging.getLogger(__name__)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: spotify.py [username]")
        exit(1)

    common.clear()
    print(common.TITLE)

    # Initialize the curses screen.
    stdscr = uc.initscr()

    # Create Spotify state.
    sp_state = SpotifyState(SpotifyApi(sys.argv[1]))

    # Create the display!
    display = CursesDisplay(stdscr, sp_state)

    # Start the display and clear the screen before
    # raising any Exceptions.
    try:
        display.start()
    except BaseException:
        common.clear()
        raise

    # Clear the screen to leave a clean terminal.
    common.clear()
