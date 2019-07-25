#!/usr/bin/env python

import argparse
import time
import unicurses as uc

import common
from display import CursesDisplay
from api import SpotifyApi
from state import SpotifyState, Config


logger = common.logging.getLogger(__name__)


def get_args():
    """Parse and return the command line arguments."""
    parser = argparse.ArgumentParser(description="Terminal remote Spotify player.",
                                     epilog=Config.help(),
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("username", help="username associated with your spotify account (email or user id)")
    parser.add_argument("-c --clear_cache",
                        action="store_true",
                        default=False,
                        dest="clear_cache",
                        help="clear the cache")
    parser.add_argument("-a --clear_auth",
                        action="store_true",
                        default=False,
                        dest="clear_auth",
                        help="clear your authorization tokens")
    parser.add_argument("-p --config_path",
                        default=None,
                        dest="config_path",
                        help="pass a configuration file")
    return parser.parse_args()


def check_version():
    """Check the version we're running."""
    my_version = common.get_version()
    latest_version = common.get_master_version()
    if my_version and latest_version and (my_version < latest_version):
        print("Version {}.{}.{} is now available".format(*latest_version))
        print("Run with -c after upgrading to clear your cache!".format(*latest_version))
        time.sleep(3)
    else:
        logger.info("Current version: %s", my_version)
        logger.info("Latest version:  %s", latest_version)


if __name__ == '__main__':
    # Get command line arguments.
    args = get_args()

    # Clear the console then print the title screen.
    common.clear()
    print(common.TITLE)

    # Check the version we're running.
    check_version()

    # Clear your auth keys.
    if args.clear_auth:
        logger.debug("Clearing authorization tokens")
        common.clear_auth(args.username)

    # Reset the cache.
    if args.clear_cache:
        logger.debug("Clearing the cache")
        common.clear_cache(args.username)

    # Parse config file.
    logger.debug("Parsing config file %s", args.config_path)
    config = Config(args.config_path)

    # Spotify API interface.
    api = SpotifyApi(args.username)

    # Display premium warning.
    if not api.is_premium():
        print("This is not a Premium account. Some features may not work.")
        time.sleep(3)

    # Create Spotify state.
    sp_state = SpotifyState(api, config)
    sp_state.load_state()
    sp_state.init()

    # Initialize the curses screen.
    stdscr = uc.initscr()

    # Create the display.
    display = CursesDisplay(stdscr, sp_state)

    # Start the display.
    # Clear the screen before raising any Exceptions.
    try:
        display.start()
    except KeyboardInterrupt:
        common.clear()
    except BaseException:
        common.clear()
        raise

    print(common.PEACE)

    # Save the state.
    sp_state.save_state()

    # Clear the screen to leave a clean terminal.
    common.clear()
