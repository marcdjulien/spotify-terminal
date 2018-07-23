import logging
import os

import util


# Set TEMP_DIR
APP_DIR = util.get_app_dir()


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
