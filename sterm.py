from Globals import *
from Console import Console
import os

# Initialize the console and go!
if __name__ == '__main__':
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    logging.basicConfig(filename=LOGGER_FILENAME, 
                        format='[%(asctime)s][%(levelname)s]   %(message)s',
                        level=logging.DEBUG)
    logging.info("Logger started.")
    console = Console()
    console.init()
    console.run()
