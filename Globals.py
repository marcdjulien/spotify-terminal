import logging

# Temporary directory path
TEMP_DIR = "tmp"

# Authentication filename
CACHE_FILENAME = "%s/cache"%(TEMP_DIR)

# Authentication filename
AUTH_FILENAME = "%s/auth"%(TEMP_DIR)

# Configuration filename
CONFIG_FILENAME = "stermrc"

# Log filename
LOGGER_FILENAME = "%s/log"%(TEMP_DIR)

# List of all commands
COMMANDS = ["set", "exit", "pause", "play", "user", "playlists", "search-artist", "sar",
            "search-album", "sal", "search-track", "str", "last-album", "lal", "last-artist",
            "lar", "help", "h", '.']
FMT = "%60s"