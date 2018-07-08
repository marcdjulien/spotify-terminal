from Globals import *
import os
import string
SAVE_COUNT = 20

class Cache(object):

    def __init__(self, spotify):
        self.spotify = spotify
        self.uri_to_name = {}
        self.count = 0
        self.read_cache(CACHE_FILENAME)

    def get_name_uri(self, uri):
        if uri in self.uri_to_name.keys():
            return self.uri_to_name[uri]
        else:
            id = uri.split(":")[2]
            if "track" in uri:
                artists = self.spotify.get_artists_from_track(id)
            else:
                artists = self.spotify.get_artists_from_album(id)
            names = []
            for a in artists:
                names.append(a['name'])
            self.uri_to_name[uri] = string.join(names, ", ")
            self.count += 1
            self.check_if_save()
            return self.uri_to_name[uri]

    def check_if_save(self):
        if self.count > SAVE_COUNT:
            self.save_cache()
            self.count = 0

    def save_cache(self):
        if not os.path.isdir(TEMP_DIR):
            os.mkdir(TEMP_DIR)
        cache_file = open(CACHE_FILENAME, "w")
        for k,v in self.uri_to_name.items():  
            cache_file.write("%s=%s\n"%(k,v.encode('ascii', 'ignore')))
        cache_file.close()
        logging.info("Cache file saved")

    def read_cache(self, filename):
        if os.path.isfile(CACHE_FILENAME):
            cache_file = open(CACHE_FILENAME)
            for line in cache_file:
                line = line.strip()
                toks = line.split("=")
                self.uri_to_name[toks[0]] = toks[1]
            logging.info("Cache file found")
        
        