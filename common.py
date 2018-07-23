import logging
import os
import platform


def is_windows():
    return platform.system() == "Windows"


def is_linux():
    return platform.system() == "Linux"


def clear():
    """Clear the terminal."""
    if is_windows():
        os.system('cls')
    elif is_linux():
        os.system("clear")


def is_int(n):
    """Returns True if 'n' is an integer.

    Args:
        n (anything): The variable to check.

    Returns:
        bool: True if it is an integet.
    """
    try:
        n = int(n)
        return True
    except ValueError:
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
    return string.encode('ascii', 'replace')


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


# Set TEMP_DIR
APP_DIR = get_app_dir()


# Authentication filename
AUTH_FILENAME = os.path.join(APP_DIR, "auth")


# Configuration filename
CONFIG_FILENAME = os.path.join(APP_DIR, "spotifyrc")


# Log filename
LOGGER_FILENAME = os.path.join(APP_DIR, "log")


TITLE = """

   _____             __  _ ____
  / ___/____  ____  / /_(_/ ____  __
  \__ \/ __ \/ __ \/ __/ / /_/ / / /
 ___/ / /_/ / /_/ / /_/ / __/ /_/ /
/____/ .___/\____/\__/_/_/  \__, /
    /_/                    /____/
       ______                    _             __
      /_  _____  _________ ___  (_____  ____ _/ /
       / / / _ \/ ___/ __ `__ \/ / __ \/ __ `/ /
      / / /  __/ /  / / / / / / / / / / /_/ / /
     /_/  \___/_/  /_/ /_/ /_/_/_/ /_/\__,_/_/

 by marcdjulien
"""

HTML_TITLE = """
<br>
<br>   _____             __  _ ____
<br>  / ___/____  ____  / /_(_/ ____  __
<br>  \__ \/ __ \/ __ \/ __/ / /_/ / / /
<br> ___/ / /_/ / /_/ / /_/ / __/ /_/ /
<br>/____/ .___/\____/\__/_/_/  \__, /
<br>    /_/                    /____/
<br>       ______                    _             __
<br>      /_  _____  _________ ___  (_____  ____ _/ /
<br>       / / / _ \/ ___/ __ `__ \/ / __ \/ __ `/ /
<br>      / / /  __/ /  / / / / / / / / / / /_/ / /
<br>     /_/  \___/_/  /_/ /_/ /_/_/_/ /_/\__,_/_/
<br>
"""

logging.basicConfig(filename=LOGGER_FILENAME,
                    filemode='w',
                    format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s',
                    level=logging.DEBUG)

