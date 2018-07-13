from Globals import *
from Utilities import *
import os
import time
import json
import urllib2
import string
from SpotifyRemote import SpotifyRemote
from SpotifyAuthentication import authenticate
from Cache import Cache

ARTIST_STATE = 0
ALBUM_STATE = 1
TRACK_STATE = 2
ALBUM_QUERY_STATE = 3
TRACK_QUERY_STATE = 4
DONE_STATE = 5
COMBO_SEARCH_STATE = 6


class InvalidSelectionError(Exception):
    pass

class EmptyInputException(Exception):
    pass

class Console(object):

    def __init__(self):
        super(Console, self).__init__()
        self.spotify = SpotifyRemote()
        self.cache = Cache(self.spotify)
        self.env_info = {}
        self.shortcuts = {}
        self.last_selection = []
        self.last_album = {}
        self.last_artist = {}
        self.last_track = {}
        self.last_context = None

    def set_command(self, prop, value):
        if prop not in self.env_info.keys():
            print "This property does not exit"
        else:
            self.env_info[prop] = value

    def pause_command(self):
        self.spotify.pause()

    def play_command(self, n=None):
        """Plays seleciton n from the last seleciton print_list"""
        if is_int(n):
            n = int(n)
            if in_range(n, self.last_selection):
                track_uri = self.last_selection[n]['uri']
                if track_uri:
                    self.spotify.play(track_uri, context_uri=self.last_context)
                else:
                    logging.info("Error: Can't choose a song.")
            else:
                raise InvalidSelectionError("Selection not in range")
        else:
            self.spotify.play(None, None)

    def user_command(self, username):
        info = self.spotify.get_user_info(username)
        print "{0} [{1}]".format(info["display_name"], info['id'])
        print "Account Type: {0}".format(info['type'])

    def playlists_command(self, username):
        playlists = self.spotify.get_user_playlists(username)
        if playlists == []: return None
        self.print_list(playlists, "Playlists")
        playlist, play_now = self.select_from_list(playlists)
        if play_now:
            uri = playlist['uri'] if playlist != None else None
            self.last_context = uri
            self.spotify.play(None, uri)
        else:
            tracks = self.spotify.get_tracks_from_playlist(playlist['owner']['id'],
                                                           playlist['id'])
            self.print_list(tracks, "Tracks")
            track, play_now = self.select_from_list(tracks)
            self.last_context = playlist['uri']
            self.spotify.play(track['uri'], playlist['uri'])

    def search_command(self, query, type):
        try:
            results = self.search_for_uri(query, type)
            if results is None:
                raise InvalidSelectionError("No results selected")
            track_uri, context_uri = results[0], results[1]
            if track_uri == None and context_uri == None:
                return
            else:
                self.last_context = context_uri
                self.spotify.play(track_uri, context_uri)
        except (EmptyInputException, InvalidSelectionError):
            return

    def current_command(self):
        track = self.spotify.get_currently_playing()
        print "Artist(s): {}".format(", ".join(
            [artist['name'] for artist in track['artists']]
        ))
        print "Album:     {}".format(track['album']['name'])
        print "Title:     {}".format(track['name'])

    def saved_command(self, limit=10, offset=0):
        songs = self.spotify.get_saved_tracks(limit, offset)
        self.print_list(songs)
        track, play_now = self.select_from_list(songs)
        if track:
            self.spotify.play(track['uri'], None)

    def print_list(self, selections, title="", offset=0, clear_console=True):
        if clear_console:
           clear()

        if selections == []:
            return

        print FMT%("---%s---"%(title))
        for i in xrange(len(selections)):
            if "Artist" in title or "Playlist" in title:
                print FMT%("%s [%d]"%(selections[i]['name'].encode('ascii', 'ignore'),
                                      i+offset))
            else:
                names = self.cache.get_artists_from_uri(selections[i]['uri'])
                print FMT%("%50s  [%d]  %s"%(selections[i]['name'].encode('ascii', 'ignore'),
                                             i+offset,
                                             names))

    def print_2d_list(self, selections, title=""):
        clear()
        offset = 0
        for i in xrange(len(selections)):
            self.print_list(selections[i], title[i], offset, clear_console=(i==0))
            offset += len(selections[i])

    def select_from_list(self, selections):
        if selections == []:
            raise EmptyInputException

        input_str = self.get_input("Enter a number: ")
        if input_str == "":
            logging.info("Nothing entered.")
            return {}, None

        self.last_selection = selections
        play_now = False
        if is_int(input_str):
            n = int(input_str)
            if in_range(n, selections):
                play_now = False
                return selections[n], play_now
            else:
                logging.info("Invalid selection")
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
                raise InvalidSelectionError

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
                if artists == []:
                    return
                self.print_list(artists, "Artists")
                artist, play_now = self.select_from_list(artists)
                self.last_artist = artist
                if play_now:
                    uri = artist['uri'] if artist != None else None
                    track_uri, context_uri = 0, uri
                    cur_state = DONE_STATE
                    continue
                else:
                    artist_id = artist.get('id')
                    self.last_artist = artist['name']
                    cur_state = ALBUM_STATE
            elif cur_state == ALBUM_STATE:
                if artist_id == None:
                    print "Error: Invalid Artist Selection"
                    return
                albums = self.spotify.get_albums_from_artist(artist_id)
                self.print_list(albums, "Albums")
                album, play_now = self.select_from_list(albums)
                self.last_album = album
                if play_now:
                    uri = album.get('uri')
                    track_uri, context_uri = 0, uri
                    cur_state = DONE_STATE
                    continue
                else:
                    album_id = album.get('id')
                    cur_state = TRACK_STATE
            elif cur_state  == TRACK_STATE:
                if album_id == None:
                    print "Error: Invalid Album Selection"
                    return
                tracks = self.spotify.get_tracks_from_album(album_id)
                self.print_list(tracks, "Tracks")
                track, play_now = self.select_from_list(tracks)
                uri = track.get('uri')
                track_uri, context_uri = uri, self.last_album['uri']
                cur_state = DONE_STATE
            elif cur_state == ALBUM_QUERY_STATE:
                albums = self.spotify.search(type, query)['albums']
                if albums == []: return
                self.print_list(albums, "Albums")
                album, play_now = self.select_from_list(albums)
                self.last_album = album
                if play_now:
                    uri = album.get('uri')
                    track_uri, context_uri = 0, uri
                    cur_state = DONE_STATE
                    continue
                else:
                    album_id = album.get('id')
                    cur_state = TRACK_STATE
            elif cur_state  == TRACK_QUERY_STATE:
                tracks = self.spotify.search(type, query)['tracks']
                if tracks == []: return
                self.print_list(tracks, "Tracks")
                track,play_now = self.select_from_list(tracks)
                uri = track.get('uri')
                track_uri, context_uri = uri, None
                cur_state = DONE_STATE
            elif cur_state == COMBO_SEARCH_STATE:
                results = self.spotify.search(type, query)
                combined = []
                combined.append(results["artists"])
                combined.append(results["albums"])
                combined.append(results["tracks"])
                self.print_2d_list(combined, ["Artists", "Albums", "Tracks"])
                selection = []
                selection.extend(results["artists"])
                selection.extend(results["albums"])
                selection.extend(results["tracks"])
                something, play_now = self.select_from_list(selection)

                if something is None:
                    return

                if play_now:
                    if something.get('type') == 'artist':
                        self.last_artist = something
                        track_uri = None
                        context_uri = something['uri']
                    elif something.get('type') == 'album':
                        self.last_album = something
                        track_uri = None
                        context_uri = something['uri']
                    elif something.get('type') == 'track':
                        track_uri = something
                        context_uri = None
                    else:
                        return None
                    cur_state = DONE_STATE
                    continue

                if something.get('type') == 'artist':
                    self.last_artist = something
                    artist_id = something['id']
                    cur_state = ALBUM_STATE
                elif something.get('type') == 'album':
                    self.last_album = something
                    album_id = something['id']
                    cur_state = TRACK_STATE
                elif something.get('type') == 'track':
                    uri = something['uri']
                    track_uri, context_uri = uri, None
                    cur_state = DONE_STATE
                else:
                    return None
            else:
                print "Error: Invalid State"
                return

        return track_uri, context_uri

    def evaluate_input(self, input_str):
        input_str = input_str.strip()
        if input_str == "":
            return

        toks = input_str.split(" ")
        n_toks = len(toks)
        n_args = n_toks-1
        command = toks[0]

        if command == "set":
            if n_args == 2:
                self.set_command(toks[1], toks[2])
            else:
                logging.warning("Not enough arguments")
        elif command == '.':
            self.current_command()
        elif command == "exit":
            exit()
        elif command == "play":
            self.play_command(*toks[1::])
        elif command == "pause":
            self.pause_command()
        elif command in ["next", 'n']:
            self.spotify.next()
        elif command in ["prev", "previous", 'p']:
            self.spotify.previous()
        elif command in ['saved', 's']:
            self.saved_command(*toks[1::])
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
                self.search_command(" ".join(toks[1::]), ["artists"])
        elif command in ["search-album", "sal"]:
            if n_args >= 1:
                self.search_command(" ".join(toks[1::]), ["albums"])
        elif command in ["search-track", "str"]:
            if n_args >= 1:
                self.search_command(" ".join(toks[1::]), ["tracks"])
        elif command in ["last_album", "lal", "ls"]:
            self.last_selection = self.spotify.get_tracks_from_album(self.last_album['id'])
            self.print_list(self.last_selection, "Tracks")
        elif command in ["last_artist", "lar"]:
            self.last_selection = self.spotify.get_albums_from_artist(self.last_artist['id'])
            self.print_list(self.last_selection, "Albums")
        elif command in ['sleep']:
            if n_args != 1:
                print("Enter an amount of time to sleep")
            else:
                time.sleep(int(toks[1]))
        elif command in ["help", "h"]:
            display_help_message()
        else:
            # If a number try to play form last selection
            if is_int(input_str):
                self.evaluate_input("play {}".format(input_str))
            # Do a search for it
            else:
                self.search_command(input_str, ["artists","tracks","albums"])

    def configure(self):
        """Initializes the users settings based on the stermrc file"""
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
                    exit()
                self.env_info[toks[0]] = toks[1]
                continue
            elif "=" in line:
                toks = line.split("=")
                if len(toks) != 2:
                    logging.error("Error in line: %s"%(line))
                    exit()
                self.shortcuts[toks[0]] = toks[1]

    def auth_from_file(self):
        if os.path.isfile(AUTH_FILENAME):
            auth_file = open(AUTH_FILENAME)
            for line in auth_file:
                line = line.strip()
                toks = line.split("=")
                setattr(self.spotify, "api_{}".format(toks[0]), toks[1])
            logging.info("Authentication file found")
            return True
        else:
            logging.info("No authentication file found")
            return False

    def auth_from_web(self):
        auth_data = authenticate()
        for k,v in auth_data.items():
            setattr(self.spotify, "api_{}".format(k), v)
        logging.info("Authentication from web complete")
        # Assuming this will work everytime for now
        return True

    def init(self):
        # Configure from stermrc file
        self.configure()

        # Authenticate form file if available or web
        if not self.auth_from_file():
            self.auth_from_web()
        logging.info("Initialization complete")

    def get_input(self, prompt):
        input_str = raw_input(prompt)
        input_str = input_str.strip()
        logging.info("Input: %s"%(input_str))
        return input_str

    def run(self):
        clear()
        print TITLE
        print "Welcome %s."%(self.env_info['user'])
        print "Remember: When making a selection, putting 'p' before will start playing"
        print "          For example, 'p3' or 'p 3', will start playing selection 3"

        while True:
            user_input = self.get_input("spotify>")
            commands = user_input.split(";")
            for command in commands:
                try:
                    self.evaluate_input(command)
                except urllib2.HTTPError as e:
                    if "Unauthorized" in e.msg:
                        self.auth_from_web()
                        self.evaluate_input(command)
                    else:
                        print e.msg


