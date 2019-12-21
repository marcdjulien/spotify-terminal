from . import unicurses as uc
from . import common


logger = common.logging.getLogger(__name__)


class Config(object):
    """Read and store config parameters."""
    key_help = {
        "find_next": "Find the next entry matching the previous expression.",
        "find_previous": "Find the previous entry matching the previous expression.",
        "add_track": "Add a track to a playlist.",
        "delete": "Remove playlist or a track from a playlist.",
        "create_playlist": "Create a new playlist.",
        "show_devices": "Show available devices",
        "refresh": "Refresh the player.",
        "goto_artist": "Go to the artist page of the highlighted track.",
        "goto_album": "Go to the album page of the highlighted track.",
        "current_artist": "Go to the artist page of the currently playing track.",
        "current_album": "Go to the album page of the currently playing track.",
        "current_context": "Go to the currently playing context.",
        "next_track": "Play the next track.",
        "previous_track": "Play the previous track.",
        "play": "Toggle play/pause.",
        "seek": "Seek to a position in the currently playing track.",
        "volume_0": "Mute volume.",
        "volume_1": "Set volume to 10%.",
        "volume_2": "Set volume to 20%.",
        "volume_3": "Set volume to 30%.",
        "volume_4": "Set volume to 40%.",
        "volume_5": "Set volume to 50%.",
        "volume_6": "Set volume to 60%.",
        "volume_7": "Set volume to 70%.",
        "volume_8": "Set volume to 80%.",
        "volume_9": "Set volume to 90%.",
        "volume_10": "Set volume to 100%.",
        "volume_up": "Increase volume by 5%.",
        "volume_down": "Decrease volume by 5%.",
        "toggle_help": "Toggle the help menu"
    }

    default = {
        "find_next": ord("n"),
        "find_previous": ord("p"),
        "add_track": ord("P"),
        "delete": uc.KEY_DC,
        "create_playlist": ord("O"),
        "show_devices": ord("W"),
        "refresh": ord("R"),
        "goto_artist": ord("D"),
        "goto_album": ord("S"),
        "current_artist": ord("C"),
        "current_album": ord("X"),
        "current_context": ord("|"),
        "next_track": ord(">"),
        "previous_track": ord("<"),
        "play": ord(" "),
        "seek": ord("G"),
        "volume_0": ord("~"),
        "volume_1": ord("!"),
        "volume_2": ord("@"),
        "volume_3": ord("#"),
        "volume_4": ord("$"),
        "volume_5": ord("%"),
        "volume_6": ord("^"),
        "volume_7": ord("&"),
        "volume_8": ord("*"),
        "volume_9": ord("("),
        "volume_10": ord(")"),
        "volume_up": ord("+"),
        "volume_down": ord("_"),
        "toggle_help": ord("H")
    }

    def __init__(self, config_filename=None):
        self.config_filename = config_filename
        """The full path to the config file."""

        self.keys = {}
        """Mapping of config keys to key codes and the reverse."""

        if self.config_filename:
            if not self._parse_and_validate_config_file():
                raise RuntimeError("Unable to parse config file. See above for details.")

            logger.debug("The following config parameters are being used:")
            for param, key in self.keys.items():
                if isinstance(param, str):
                    try:
                        logger.debug("\t%s: %s (%s)", param, chr(key), key)
                    except:
                        logger.debug("\t%s: %s", param, key)
        else:
            self.keys = self.default

        # Reverse map the params and keys.
        for key, value in list(self.keys.items()):
            self.keys[value] = key

    def get_config_param(self, key):
        return self.keys.get(key, "")

    def get_volume_keys(self):
        return [self.keys["volume_{}".format(i)] for i in range(11)]

    def __getattr__(self, attr):
        return self.keys[attr]

    def __contains__(self, key):
        return key in self.keys

    def _parse_and_validate_config_file(self):
        """Initializes the users settings based on the config file."""
        rc_file = open(self.config_filename, "r")

        new_keys = {}

        for line in rc_file:
            # Strip whitespace and comments.
            line = line.strip()
            line = line.split("#")[0]
            try:
                param, code = line.split(":")
                code = code.strip()
                if common.is_int(code):
                    code = int(code)
                else:
                    code = ord(eval(code))

                # Make sure this is a valid config param.
                if param not in self.default:
                    print("The following parameter is not recognized: {}".format(param))

                # Make sure this param wasn't defined twice.
                if param in new_keys:
                    print("The following line is redefining a param:")
                    print(line)
                    return False

                # Make sure this code wasn't defined twice.
                if code in new_keys.values():
                    print("The following line is redefining a key code:")
                    print(line)
                    return False

                new_keys[param] = code
            except:
                print("The following line is not formatted properly:")
                print(line)
                return False

        # Copy over the defaults.
        for param in set(self.default.keys()) - set(new_keys.keys()):
            new_keys[param] = self.default[param]

        # Make sure there's no collision.
        if len(set(new_keys.values())) != len(new_keys):
            print("A conflicting parameter was found with the default configuration!")
            print("Check the help message (-h) for the defaults and make sure")
            print("you aren't using the same keys.")
            return False

        # Success!
        self.keys = new_keys

        return True

    @staticmethod
    def help():
        msg = "The following keys can be specified in the config file:\n\n"
        for key, help_msg in sorted(Config.key_help.items()):
            msg = msg + "%20s - %s (Default=\"%s\")\n" % (key, help_msg, chr(Config.default[key]))

        msg = msg + "\nEach key should be defined by a single character in quotes.\n"
        msg = msg + "Example:\n next_track: \">\"\n\n"
        msg = msg + "Alternatively, you can define a special key code not in quotes.\n"
        msg = msg + "Example:\n next_track: 67\n\n"

        return msg