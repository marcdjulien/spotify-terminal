from Globals import *
from Console import Console

# Initialize the console and go!
if __name__ == '__main__':
    logging.basicConfig(filename=LOGGER_FILENAME, 
                        format='[%(asctime)s][%(levelname)s]-%(message)s',
                        level=logging.DEBUG)
    logging.info("Logger started.")
    console = Console()
    console.init()
    console.run()
