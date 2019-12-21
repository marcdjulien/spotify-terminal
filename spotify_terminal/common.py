import logging
import os
import platform
import requests
import shutil
import time
import tempfile
import traceback
import unicodedata

from threading import Thread


logger = None

DEBUG = False


def catch_exceptions(func):
    """Decorator to catch exceptions and print it in DEBUG mode.

    All threaded functions should be decorated with this,
    otherwise exceptions will go uncaught.
    """
    def wrapper(*args, **kwargs):
        """Wrapper to catch and print exceptions."""
        try:
            return func(*args, **kwargs)
        except BaseException:
            clear()
            traceback.print_exc()
            os._exit(1)

    return wrapper if DEBUG else func


def asynchronously(func):
    """Decorator to execute a function asynchronously."""
    @catch_exceptions
    def wrapper(*args, **kwargs):
        Thread(target=func, args=args, kwargs=kwargs).start()

    return wrapper


def is_windows():
    return platform.system() == "Windows"


def is_linux():
    return platform.system() == "Linux"


def is_mac(): 
    return platform.system() == 'Darwin'


def clear():
    """Clear the terminal."""
    if is_windows():
        os.system('cls')
    elif is_linux():
        os.system("reset")
    elif is_mac():
        os.system('reset')
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
        string (str, bytes): The string to encode.

    Returns:
        str: The ascii encoded string.
    """
    return unicodedata.normalize("NFKD", string).encode("ascii", "ignore").decode("ascii")


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


def ensure_dir(func):
    """Decorator to ensure a path exists before returning it."""

    @catch_exceptions
    def wrapper(*args, **kwargs):
        """A wrapper that ensures the dir exists before returning it."""
        path = func(*args, **kwargs)
        if not os.path.exists(path):
            os.makedirs(path)
            if logger:
                logger.debug("Created %s", path)
        return path

    return wrapper


@ensure_dir
def get_app_dir():
    """Return the application's directory.

    Returns:
        str: The full path to the directory.
    """
    return os.path.join(tempfile.gettempdir(), "spotifyterminal")


def get_app_file_path(*args):
    """Return the path of a file in the application's directory.

    Args:
        args (tuple): The file paths.

    Returns:
        str: The full path to the file.
    """
    return os.path.join(get_app_dir(), *args)


@ensure_dir
def get_user_dir(username):
    """Return dir for the user.

    Args:
        username (str): The user name.

    Returns:
        str: The path to the user's cache.
    """
    return get_app_file_path(username)


def get_user_file_path(username, *args):
    """Return the path from the user's directory.

    Args:
        args (tuple): The file paths.

    Returns:
        str: The full path to the file.
    """
    return os.path.join(get_user_dir(username), *args)


@ensure_dir
def get_cache(username):
    """Return the directory of the user's cache.

    Args:
        username (str): The user name.

    Returns:
        str: The path to the user's cache.
    """
    return get_user_file_path(username, ".cache")


def get_file_from_cache(username, file):
    """Return a file from a user's cache.

    Args:
        username (str): The user.
        file (str): The file.

    Returns:
        str: The fill path to the file.
    """
    return os.path.join(get_cache(username), file)


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


def get_auth_filename(username):
    """Return the path to the auth filename.

    Returns:
        str: The full path to the auth filename
    """
    return get_user_file_path(username, "auth")


def clear_auth(username):
    """Clear the user's authorization tokens.

    Args:
        username (str): The user name.
    """
    auth_filename = get_auth_filename(username)
    try:
        os.remove(auth_filename)
    except Exception as e:
        logger.debug("Could not clear %s", auth_filename)
        logger.debug("%s", e)


def extract_version(stream):
    version = None
    for line in stream:
        line = line.decode()
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
        # Read in as bytes. extract_version will decode it.
        # This maintains compatibility with get_master_version
        # which relies on bytes from the Request response.
        with open(version_file, "rb") as f:
            return extract_version(f)
    except BaseException as e:
        logger.info("Could not get current version %s", e)


def get_master_version():
    try:
        resp = requests.get(
            "https://raw.githubusercontent.com/marcdjulien/spotify-terminal/master/spotify_terminal/.version",
            timeout=1
        )
        return extract_version(resp)
    except BaseException as e:
        logger.info("Could not get latest version %s", e)


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


SPOTIFY_BANNER = """
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

  [marcdjulien]
"""


TITLE = """

{}
   Loading...

   v{}.{}.{}
""".format(SPOTIFY_BANNER, *get_version())


PEACE = """

{}

   Saving...

""".format(SPOTIFY_BANNER)

SAVED_TRACKS_CONTEXT_URI = "spotify_terminal:saved_tracks:context"

ARTIST_ALL_TRACKS_CONTEXT_URI = "spotify_terminal:artist:all_tracks_context"

ARTIST_ALL_TRACKS_CONTEXT = {'uri': ARTIST_ALL_TRACKS_CONTEXT_URI}

ALL_ARTIST_TRACKS_CONTEXT_TYPE = "all_artist_tracks"

def get_all_tracks_context(artist):
    return {'uri': ARTIST_ALL_TRACKS_CONTEXT_URI,
            'artist': artist,
            'type': ALL_ARTIST_TRACKS_CONTEXT_TYPE}


def is_all_tracks_context(context):
    return context['uri'] == ARTIST_ALL_TRACKS_CONTEXT_URI


logging.basicConfig(filename=get_app_file_path("log"),
                    filemode='w',
                    format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s',
                    level=logging.DEBUG)


logger = logging.getLogger(__name__)