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
                    format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s',
                    level=logging.DEBUG)
logging.info("="*25)