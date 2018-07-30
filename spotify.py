#!/usr/bin/env python

import argparse
import sys
import unicurses as uc

import common
from display import CursesDisplay
from spotify_api import SpotifyApi
from model import SpotifyState


logger = common.logging.getLogger(__name__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Terminal remote Spotify player.")
    parser.add_argument("username", help="spotify username")
    parser.add_argument("-c",
                      action="store_true",
                      default=False,
                      dest="clear_cache",
                      help="clear the cache")
    args = parser.parse_args()

    common.clear()
    print(common.TITLE)

    # Reset the cache.
    if args.clear_cache:
        logger.debug("Clearing the cache")
        common.clear_cache(args.username)

    # Initialize the curses screen.
    stdscr = uc.initscr()

    # Create Spotify state.
    api = SpotifyApi(args.username)
    sp_state = SpotifyState(api)

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
