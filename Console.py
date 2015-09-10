from Globals import *
from Utilities import *
import os
import time
import json
import string
from threading import Timer
from SpotifyRemote import SpotifyRemote
from SpotifyAuthentication import authenticate

    
ARTIST_STATE = 0
ALBUM_STATE = 1
TRACK_STATE = 2
ALBUM_QUERY_STATE = 3
TRACK_QUERY_STATE = 4
DONE_STATE = 5
COMBO_SEARCH_STATE = 6

INF = -1

class InvalidSelectionError(Exception):
    pass

class EmptyInputException(Exception):
    pass

class Console(object):
    """docstring for Console"""
    def __init__(self):
        super(Console, self).__init__()
        self.env_info = { "user": "" }
        self.shortcuts = {}
        self.spotify = SpotifyRemote()
        self.last_selection = []
        self.last_album = []
        self.last_artist = []
        self.last_track = []

    def set_command(self, prop, value):
        if prop not in self.env_info.keys():
            print "This property does not exit"
        else:
            self.env_info[prop] = value

    def pause_command(self, time):
        self.spotify.pause(pause=True)
        Timer(time, self.spotify.pause, [False]).start()

    """
    Plays seleciton n from the last seleciton print_list
    """
    def play_command(self, n):
        if is_int(n):
            n = int(n)
            if in_range(n, self.last_selection):
                track_uri = self.last_selection[n]['uri']
                self.spotify.play(track_uri)
            else:
                print "Error: Invalid Track Selection"
                raise InvalidSelectionError
                

    def user_command(self, username):
        info = self.spotify.get_user_info(username)
        print "{0} [{1}]".format(info["display_name"], info['id'])
        print "Account Type: {0}".format(info['type'])

    def playlists_command(self, username):
        playlists = self.spotify.get_user_playlists(self)
        if playlists == []: return None
        self.print_list(playlists, "Playlists")
        playlist,play_now = self.select_from_list(playlists)
        if play_now:
            uri = playlist['uri'] if playlist != None else None
            self.spotify.play(uri)
        else:
            tracks = self.spotify.get_playlist_tracks(playlist['owner']['id'], 
                playlist['id'], self.env_info['token_type'], self.env_info['access_token'])
            self.print_list(tracks, "Tracks")
            track, play_now = self.select_from_list(tracks)
            self.spotify.play(track['uri'])
    def search_command(self, query, type):
        try:
            uri = self.search_for_uri(query, type)
            if uri == None:
                return
            else:
                self.spotify.play(uri)
        except EmptyInputException:
            return

    def print_list(self, selections, title="", offset=0):
        if selections == []: return
        print "---%s---"%(title)
        for i in xrange(len(selections)-1,-1,-1):
            print "[%d] %s"%(i+offset, selections[i]['name'].encode('ascii', 'ignore'))

    def print_2d_list(self, selections, title=""):
        offset = 0
        for i in xrange(len(selections)):
            self.print_list(selections[i], title[i], offset)
            offset += len(selections[i])

    def select_from_list(self, selections):
        if selections == []:
            print "Found nothing."
            logging.info("Empty selection.")
            raise EmptyInputException
        input_str = self.get_input("Enter a number: ")
        if input_str == "":
            raise EmptyInputException

        self.last_selection = selections
        play_now = False
        if is_int(input_str):
            n = int(input_str)
            if in_range(n, selections):
                play_now = False
                return selections[n], play_now
            else:
                raise InvalidSelectionError
        # Input was something like: p 9
        else:
            play_now = True
            ltr = input_str[0]
            try:
                n = int(input_str[1::].strip())
                if not in_range(n, selections):
                    raise InvalidSelectionError
                return selections[n], play_now
            except:
                return None

    def search_for_uri(self, query, type):
        if query in self.shortcuts.keys():
            query = self.shortcuts[query]

        uri = None
        tracks = None
        if type == ["artists"]:
            cur_state = ARTIST_STATE
        elif type == ["albums"]:
            cur_state = ALBUM_QUERY_STATE
        elif type == ["tracks"]:
            cur_state = TRACK_QUERY_STATE
        else:
            cur_state = COMBO_SEARCH_STATE

        while cur_state != DONE_STATE:
            if cur_state == ARTIST_STATE:
                artists = self.spotify.search(type, query)['artists']
                if artists == []: return None
                self.print_list(artists, "Artists")
                artist,play_now = self.select_from_list(artists)
                if play_now:
                    uri = artist['uri'] if artist != None else None
                    cur_state = DONE_STATE
                    continue
                artist_id = artist['id'] if artist != None else None
                self.last_artist = artist['name'] is artist != None
                cur_state = ALBUM_STATE
            elif cur_state == ALBUM_STATE:
                if artist_id == None:
                    print "Error: Invalid Artist Selection"
                    return
                albums = self.spotify.get_artist_albums(artist_id)
                self.print_list(albums, "Albums")
                album,play_now = self.select_from_list(albums)
                self.last_album = album
                if play_now:
                    uri = album['uri'] if album != None else None
                    cur_state = DONE_STATE
                    continue
                album_id = album['id'] if album != None else None
                cur_state = TRACK_STATE
            elif cur_state  == TRACK_STATE:
                if album_id == None:
                    print "Error: Invalid Album Selection"
                    return
                tracks = self.spotify.get_album_tracks(album_id)
                self.print_list(tracks, "Tracks")
                track,play_now = self.select_from_list(tracks)
                uri = track['uri'] if track != None else None
                cur_state = DONE_STATE
            elif cur_state == ALBUM_QUERY_STATE:
                albums = self.spotify.search(type, query)['albums']
                if albums == []: return None
                self.print_list(albums, "Albums")
                album,play_now = self.select_from_list(albums)
                self.last_album = album
                if play_now:
                    uri = album['uri'] if album != None else None
                    cur_state = DONE_STATE
                    continue
                album_id = album['id'] if album != None else None
                cur_state = TRACK_STATE
            elif cur_state  == TRACK_QUERY_STATE:
                tracks = self.spotify.search(type, query)['tracks']
                if tracks == []: return None
                self.print_list(tracks, "Tracks")
                track,play_now = self.select_from_list(tracks)
                uri = track['uri']  if track != None else None
                cur_state = DONE_STATE
            elif cur_state == COMBO_SEARCH_STATE:
                results = self.spotify.search(type, query)
                combined = []
                combined.append(results["artists"])
                combined.append(results["albums"])
                combined.append(results["tracks"])
                self.print_2d_list(combined, ["Artists", "Albums", "Tracks"])
                combined = []
                combined.extend(results["artists"])
                combined.extend(results["albums"])
                combined.extend(results["tracks"])
                something,play_now = self.select_from_list(combined)
                if something == None:
                    cur_state = DONE_STATE
                    continue
                if play_now:
                    uri = something['uri']
                    cur_state = DONE_STATE
                    continue
                if something['type'] == 'artist':
                    artist_id = something['id']
                    cur_state = ALBUM_STATE
                else:
                    uri = something['uri']
                    cur_state = DONE_STATE
            else:
                print "Error: Invalid State"
                return

        return uri

    def evaluate_input(self, input_str):
        input_str = input_str.strip()
        toks = input_str.split(" ")
        n_toks = len(toks)
        n_args = n_toks-1
        if input_str == "":
            return
        command = toks[0]
        cl = len(command)

        if command not in COMMANDS:
            logging.warning("This command does not exist. Searching for %s instead."%(input_str))

        if command == "set":
            if n_args == 2:
                self.set_command(toks[1], toks[2])
            else:
                logging.warning("Not enough arguments")
        elif command == "exit" or command == "q" or command == "quit":
            exit()
        elif command == "play":
            if n_args == 0:
                self.spotify.pause(pause=False)
            elif n_args == 1:
                self.play_command(toks[1])
        elif command == "pause":
            if n_args == 0:
                self.spotify.pause(pause=True)
            elif n_args > 1:
                logging.warning("The 'pause' command only uses 0 or 1 argument")
                return
            else:
                self.pause_command(int(toks[1]))
        elif command == "user":
            username = ""
            if n_args == 1:
                username = toks[1]
            else:
                username = self.env_info["user"]
            self.user_command(username)
        elif command == "playlists":
            if n_args == 1:
                self.playlists_command(toks[1])
            else:
                self.playlists_command(self.env_info["user"])
        elif command in ["search-artist", "sar"]:
            if n_args >= 1:
                self.search_command(input_str[cl+1::], ["artists"])
        elif command in ["search-album", "sal"]:
            if n_args >= 1:
                self.search_command(input_str[cl+1::], ["albums"])
        elif command in ["search-track", "str"]:
            if n_args >= 1:
                self.search_command(input_str[cl+1::], ["tracks"])
        elif command in ["last_album", "lal"]:
            last_selection = self.last_album
            self.print_list(self.last_album, "Tracks")
        elif command in ["last_artist", "lar"]:
            last_selection = self.last_artist
            self.print_list(self.last_artist, "Albums")
        elif command in ["help", "h"]:
            display_help_message()
        else:
            self.search_command(input_str, ["artists","tracks","albums"])

    """
    Initializes the users settings based on the stermrc file
    """
    def configure(self):
        try:
            rc_file = open(CONFIG_FILENAME,"r")
        except:
            print "No configuration file '%s'"%(CONFIG_FILENAME)
            return

        for line in rc_file:
            line = line.strip()
            line = line.split("#")[0] # Ignore comments
            if "<-" in line:
                toks = line.split("<-")
                if len(toks) != 2:
                    logging.error("Error in line: %s"%(line))
                    continue
                self.env_info[toks[0]] = toks[1]
                continue
            elif "=" in line:
                toks = line.split("=")
                if len(toks) != 2:
                    logging.error("Error in line: %s"%(line))
                    continue
                self.shortcuts[toks[0]] = toks[1]

    def auth_from_file(self):
        if os.path.isfile(AUTH_FILENAME):
            auth_file = open(AUTH_FILENAME)
            for line in auth_file:
                line = line.strip()
                toks = line.split("=")
                self.env_info[toks[0]] = toks[1]
            logging.info("Authentication file found")
            return True
        else:
            logging.info("No authentication file found")
            return False

    """
    Assuming this will work everytime for now
    """
    def auth_from_web(self):
        auth_data = authenticate()
        for k,v in auth_data.items():
            self.env_info[k] = v
        logging.info("Authentication from web complete")
        return True

    def init(self):
        # Configure form stermrc file
        self.configure()
        # Authenticate form file if available or web
        success = self.auth_from_file()
        if success:
            return
        else:
            self.auth_from_web()
        logging.info("Initialization complete")

    def get_input(self, prompt):
        input_str = raw_input(prompt)
        input_str = input_str.strip()
        logging.info("Input: %s"%(input_str))
        return input_str
        
    def run(self):
        if self.env_info['user'] == "":
            print "Welcome to spotify Terminal!"
        else:
            print "Welcome %s."%(self.env_info['user'])
        print "Remember: When making a selection, putting 'p' before will start playing"
        print "          For example, 'p3' or 'p 3', will start playing selection 3"
        while True:
            user_input = self.get_input("spotify>")
            self.evaluate_input(user_input)


