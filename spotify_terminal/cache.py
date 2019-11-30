import os
import pickle
from threading import Thread

from . import common

logger = common.logging.getLogger(__name__)


class UriCache(object):
    """Cache for app URIs."""

    def __init__(self, username, new=False):
        self.username = username
        """The username of the cache."""

        self._cache = {}
        """Storage for the memory cache."""

        if new:
            common.clear_cache(self.username)
            
    def get(self, key):
        """Return the cached object

        Args:
            key (str): The key.

        Returns:
            object: The object if available, otherwise None.
        """
        # First check memory.
        if key in self._cache:
            logger.debug("Memory cache hit: %s", key)
            return self._cache[key]

        # Check disk.
        cache_filename = self.get_filename(key)
        if os.path.isfile(cache_filename):
            with open(cache_filename, "rb") as file:
                logger.debug("Disk cache hit: %s", key)
                self._cache[key] = pickle.load(file)
                return self._cache[key]

        logger.debug("Cache miss: %s", key)

    def clear(self, key):
        """Clear an entry from the cache."""
        try:
            logger.debug("Removing %s from memory cache", key)
            del self._cache[key]
        except:
            pass

        try:
            logger.debug("Removing %s from disk cache", key)
            os.remove(self.get_filename(key))
        except:
            pass

    def __setitem__(self, key, item):
        # This may have been an error, don't save it.
        if item is None:
            return

        # Save to disk.
        cache_filename = self.get_filename(key)
        Thread(target=self.save, args=(cache_filename, item)).start()

        # Save to memory.
        self._cache[key] = item

    def save(self, filename, item):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as file:
            logger.debug("Saving %s to disk", filename)
            pickle.dump(item, file)

    def get_filename(self, key):
        """Return the filename of the key.

        Args:
            key (str): The key.

        Returns:
            str: The path of the cached file.
        """
        filename = key.replace("#", os.path.sep).replace(":", "_")
        return common.get_file_from_cache(self.username, filename)
