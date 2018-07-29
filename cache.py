import os
import common
import pickle


logger = common.logging.getLogger(__name__)


class UriCache(object):
    """Cache for app URIs."""

    def __init__(self, username):
        self.username = username
        """The username of the cache."""

        self._cache = {}
        """Storage for the memory cache."""

        common.create_cache(username)

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

    def __setitem__(self, key, item):
        # Save to disk.
        cache_filename = self.get_filename(key)
        with open(cache_filename, "wb") as file:
            logger.debug("Saving %s to disk", key)
            pickle.dump(item, file)

        # Save to memory.
        self._cache[key] = item

    def get_filename(self, key):
        """Return the filename of the key.

        Args:
            key (str): The key.

        Returns:
            str: The path of the cached file.
        """
        return os.path.join(common.get_cache(self.username),
                            key.replace(":", "_"))
