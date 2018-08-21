#!/usr/bin/env python

import argparse
import time
import unicurses as uc

import common
from display import CursesDisplay
from spotify_api import SpotifyApi
from state import SpotifyState


logger = common.logging.getLogger(__name__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Terminal remote Spotify player.")
    parser.add_argument("username", help="spotify username")
    parser.add_argument("-c --clear_cache",
                        action="store_true",
                        default=False,
                        dest="clear_cache",
                        help="clear the cache")
    parser.add_argument("-l --load_state",
                        action="store_true",
                        default=False,
                        dest="load_state",
                        help="start the program from the last state it was in")
    args = parser.parse_args()

    # Clear the console then print the title screen.
    common.clear()
    print(common.TITLE)

    my_version = common.get_version()
    latest_version = common.get_master_version()
    if my_version and latest_version and (my_version < latest_version):
        print("Version {}.{}.{} is now available".format(*latest_version))
        print("Run with -c after upgrading to clear your cache!".format(*latest_version))
        time.sleep(3)
    else:
        logger.info("Current version: %s", my_version)
        logger.info("Latest version: %s", latest_version)

    # Reset the cache.
    if args.clear_cache:
        logger.debug("Clearing the cache")
        common.clear_cache(args.username)

    # API interface.
    api = SpotifyApi(args.username)

    # Create Spotify state.
    sp_state = SpotifyState(api)
    if args.load_state:
        state = common.load_state(args.username, sp_state)
    sp_state.init()

    # Initialize the curses screen.
    stdscr = uc.initscr()

    # Create the display
    display = CursesDisplay(stdscr, sp_state)

    # Start the display and clear the screen before
    # raising any Exceptions.
    try:
        display.start()
    except KeyboardInterrupt:
        common.clear()
    except BaseException:
        common.clear()
        raise

    print(common.PEACE)

    # Save the state.
    common.save_state(args.username, sp_state)

    # Clear the screen to leave a clean terminal.
    common.clear()
