import logging
import os
import platform
import requests
import shutil
import time
import traceback
import unicodedata


def catch_exceptions(func):
    """Catch an exception and print it."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException:
            clear()
            traceback.print_exc()
            os._exit(1)

    return wrapper


def get_default_market():
    """Return the default market.

    Currently only supports US.

    Returns:
        str: The default market.
    """
    return "US"


def is_windows():
    return platform.system() == "Windows"


def is_linux():
    return platform.system() == "Linux"


def clear():
    """Clear the terminal."""
    if is_windows():
        os.system('cls')
    elif is_linux():
        os.system("reset")


def is_int(n):
    """Returns True if 'n' is an integer.

    Args:
        n (anything): The variable to check.

    Returns:
        bool: True if it is an integet.
    """
    try:
        int(n)
        return True
    except (ValueError, TypeError):
        return False


def in_range(n, list):
    """Returns True if n is in range of the list.

    Args:
        n (int): The selection.
        list (list): The list.

    Returns:
        bool: True if n is in range.
    """
    return (0 <= n) and (n < len(list))


def ascii(string):
    """Return an ascii encoded version of the string.

    Args:
        string (str): The string to encode.

    Returns:
        str: The ascii encoded string.
    """
    return unicodedata.normalize("NFKD", string).encode('ascii', 'ignore')


def clamp(value, low, high):
    """Clamp value between low and high (inclusive).

    Args:
        value (int, float): The value.
        low (int, float): Lower bound.
        high (int, float): Upper bound.

    Returns
        int, float: Value such that low <= value <= high.
    """
    return max(low, min(value, high))


def get_app_dir():
    """Return the application's directory.

    Returns:
        str: The full path to the directory.
    """
    if is_windows():
        dirname = os.path.join(os.getenv('APPDATA'), ".spotifyterminal")
    elif is_linux():
        dirname = os.path.join(os.path.expanduser("~"), ".spotifyterminal")

    if not os.path.isdir(dirname):
        os.mkdir(dirname)

    return dirname


def get_app_file_path(*args):
    """Return the path from the applications directory.

    Args:
        args (tuple): The file paths.

    Returns:
        str: The full path to the file.
    """
    return os.path.join(get_app_dir(), *args)


def get_cache(username):
    """Return the directory of the user's cache.

    Args:
        username (str): The user name.

    Returns:
        str: The path to the user's cache.
    """
    return get_app_file_path(".cache", username)


def clear_cache(username):
    """Clear the user's cache.

    Args:
        username (str): The user name.
    """
    user_cache = get_cache(username)
    try:
        shutil.rmtree(user_cache)
    except Exception as e:
        logger.debug("Could not clear %s", user_cache)
        logger.debug("%s", e)


def create_cache(username):
    """Create the user's cache.

    If the cache already exists, this has no effect.

    Args:
        username (str): The user name.
    """
    if not get_app_file_path(".cache"):
        os.mkdir(get_app_file_path(".cache"))

    user_cache = get_cache(username)
    if not os.path.isdir(user_cache):
        os.mkdir(user_cache)


def extract_version(stream):
    version = None
    for line in stream:
        if "." in line:
            version = line.strip()
            break
    version = tuple(int(n.strip()) for n in version.split("."))
    return version


def get_version():
    try:
        version_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".version"
        )
        with open(version_file, "r") as f:
            return extract_version(f)
    except BaseException as e:
        logger.info("Could not get current version %s", e)


def get_master_version():
    try:
        resp = requests.get("https://raw.githubusercontent.com/marcdjulien/spotifyterminal/master/.version")
        return extract_version(resp)
    except BaseException as e:
        logger.info("Could not get latest version %s", e)


# Authentication filename
AUTH_FILENAME = get_app_file_path("auth")


# Configuration filename
CONFIG_FILENAME = get_app_file_path("spotifyrc")


TITLE = """

   _____             __  _ ____
  / ___/____  ____  / /_(_/ ____  __
  \__ \/ __ \/ __ \/ __/ / /_/ / / /
 ___/ / /_/ / /_/ / /_/ / __/ /_/ /
/____/ .___/\____/\__/_/_/  \__, /
    /_/                    /____/
       ______                    _             __
      /_  _____  _________ ___  (_)___  ____ _/ /
       / / / _ \/ ___/ __ `__ \/ / __ \/ __ `/ /
      / / /  __/ /  / / / / / / / / / / /_/ / /
     /_/  \___/_/  /_/ /_/ /_/_/_/ /_/\__,_/_/


   [marcdjulien] v{}.{}.{}
""".format(*get_version())


SAVED_TRACKS_CONTEXT_URI = "spotify_terminal:saved_tracks:context"

ARTIST_PAGE_CONTEXT_URI = "spotify_terminal:artist:context"

ARTIST_PAGE_CONTEXT = {'uri': ARTIST_PAGE_CONTEXT_URI}

logging.basicConfig(filename=get_app_file_path("log"),
                    filemode='w',
                    format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s',
                    level=logging.DEBUG)


logger = logging.getLogger(__name__)
logger.info("\n\n\n")


class ContextDuration(object):
    """Measured the duration of the context."""

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exception, value, traceback):
        self.end = time.time()
        self.duration = self.end - self.start
        if not exception:
            return self
