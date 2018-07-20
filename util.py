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
    """Returns True if 'n' is an integet.

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
        string (str): The String to encode.

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


def get_temp_dir():
    """Return the temporary directory.

    Returns:
        str: The full path to the directory.
    """
    if is_windows():
        dirname = os.path.join(os.getenv('APPDATA'), ".spotifyterminal")
    elif is_linux():
        dirname = os.path.join("~", ".spotifyterminal")

    if not os.path.isdir(dirname):
        os.mkdir(dirname)

    return dirname