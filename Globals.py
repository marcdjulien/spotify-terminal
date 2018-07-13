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

"""

HTML_TITLE = """
\n
\n   _____             __  _ ____
\n  / ___/____  ____  / /_(_/ ____  __
\n  \__ \/ __ \/ __ \/ __/ / /_/ / / /
\n ___/ / /_/ / /_/ / /_/ / __/ /_/ /
\n/____/ .___/\____/\__/_/_/  \__, /
\n    /_/                    /____/
\n       ______                    _             __
\n      /_  _____  _________ ___  (_____  ____ _/ /
\n       / / / _ \/ ___/ __ `__ \/ / __ \/ __ `/ /
\n      / / /  __/ /  / / / / / / / / / / /_/ / /
\n     /_/  \___/_/  /_/ /_/ /_/_/_/ /_/\__,_/_/
\n
"""

logging.basicConfig(filename=LOGGER_FILENAME,
                    format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s',
                    level=logging.DEBUG)
logging.info("="*25)