import argparse
import time

from . import unicurses as uc
from . import common
from .display import CursesDisplay
from .api import SpotifyApi, TestSpotifyApi
from .state import SpotifyState, Config


logger = common.logging.getLogger(__name__)

def get_args():
    """Parse and return the command line arguments."""
    parser = argparse.ArgumentParser(description="Terminal remote Spotify player.",
                                     epilog=Config.help(),
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-u --username",
                        default=None,
                        dest="username", 
                        help="username associated with your spotify account (email or user id)")
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
    parser.add_argument("--debug",
                        action="store_true",
                        default=False,
                        dest="debug",
                        help="debug mode")
    parser.add_argument("--test",
                        action="store_true",
                        default=False,
                        dest="test",
                        help="test mode")
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


def main():
    # Get command line arguments.
    args = get_args()

    # Clear the console then print the title screen.
    common.clear()
    print(common.TITLE)

    if args.debug:
        common.DEBUG = True

    if common.DEBUG:
        print("[!] Debug mode is on [!]\n")

    # Check the version we're running.
    check_version()

    # Clear your auth keys.
    if args.clear_auth:
        if args.username is None:
            print("Must specify username")
            exit(1)
        logger.debug("Clearing authorization tokens")
        common.clear_auth(args.username)

    # Reset the cache.
    if args.clear_cache:
        if args.username is None:
            print("Must specify username")
            exit(1)
        logger.debug("Clearing the cache")
        common.clear_cache(args.username)

    # Parse config file.
    logger.debug("Parsing config file %s", args.config_path)
    config = Config(args.config_path)

    try:
        # Spotify API interface.
        ApiClass = TestSpotifyApi if args.test else SpotifyApi
        api = ApiClass(args.username)

        # Display premium warning.
        if not api.user_is_premium():
            print("This is not a Premium account. Most features will not work!")
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
        display.start()
    except KeyboardInterrupt:
        common.clear()
    except BaseException as e:
        common.clear()
        if common.DEBUG:
            raise
        else:
            print(e)
            exit(1)

    print(common.PEACE)
    time.sleep(1)

    # Save the state.
    sp_state.save_state()

    # Clear the screen to leave a clean terminal.
    common.clear()
