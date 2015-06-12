from Globals import *
import os
import time
import json
import string
from threading import Timer
from SpotifyRemote import SpotifyRemote
from SpotifyAuthentication import authenticate

SPOTIFY = SpotifyRemote()
COMMANDS = ["set", "exit", "pause", "play", "user", "playlists", "search-artist", "sar",
            "search-album", "sal", "search-track", "str", "last-album", "lal", "last-artist",
            "lar", "help"]
ENV_INFO = {"user":""}
    
ARTIST_STATE = 0
ALBUM_STATE = 1
TRACK_STATE = 2
ALBUM_QUERY_STATE = 3
TRACK_QUERY_STATE = 4
DONE_STATE = 5
COMBO_SEARCH_STATE = 6

INF = -1
last_selection = []
last_album = []
last_artist = []
last_track = []

SHORTCUTS = {}

class InvalidSelectionError(Exception):
    pass

class EmptySelectionError(Exception):
    pass

def display_help_message():
    info = {}
    info['exit'] = ["exit", "Exit the program"]
    info['play'] = ["play", "Play music"]
    info['pause'] = ["pause [d]", "Pause music, if the optional argument is used it will pause for d seconds"]
    info['user'] = ["user", "Display user info"]
    #info['playlists'] = ["playlists", "List the current users playlists for selection"]
    info['search-artists'] = ["search-artist/sar", "Search for an artist to play"]
    info['search-albums'] = ["search-album/sal", "Search for an album to play"]
    info['search-tracks'] = ["search-track/str", "Search for a track to play"]
    info['help'] = ["help", "Display this help message"]

    print ""
    for line in info:
        print "%20s %s"%(info[line][0], info[line][1])

def is_int(n):
    try:
        n = int(n)
        return True
    except:
        return False
    return False

def set_command(prop, value):
    if prop not in ENV_INFO.keys():
        print "This property does not exit"
    else:
        ENV_INFO[prop] = value
    return

def pause_command(time):
    SPOTIFY.pause(pause=True)
    Timer(time, SPOTIFY.pause, [False]).start()

def play_command(n):
    if is_int(n):
        n = int(n)
        if (0 <= n) and (n < len(last_selection)):
            track_uri = last_selection[n]['uri']
            SPOTIFY.play(track_uri)
        else:
            print "Error: Invalid Track Selection"
            return
    else:
        return

def user_command(username):
    info = SPOTIFY.get_user_info(username)
    print "{0} [{1}]".format(info["display_name"], info['id'])
    print "Account Type: {0}".format(info['type'])

def playlists_command(username):
    playlists = SPOTIFY.get_user_playlists(username,ENV_INFO['token_type'], 
                                ENV_INFO['access_token'])
    if playlists == []: return None
    print_list(playlists, "Playlists")
    playlist,play_now = select_from_list(playlists)
    if play_now:
        uri = playlist['uri'] if playlist != None else None
        SPOTIFY.play(uri)
        #else:
        #    tracks = 
def search_command(query, type):
    try:
        uri = search_for_uri(query, type)
        if uri == None:
            return
        else:
            SPOTIFY.play(uri)
    except EmptySelectionError:
        return

def print_list(selections, title="", offset=0):
    if selections == []: return
    print "---%s---"%(title)
    for i in xrange(len(selections)-1,-1,-1):
        print "[%d] %s"%(i+offset, selections[i]['name'].encode('ascii', 'ignore'))

def print_2d_list(selections, title=""):
    offset = 0
    for i in xrange(len(selections)):
        print_list(selections[i], title[i], offset)
        offset += len(selections[i])

def select_from_list(selections):
    global last_selection
    if selections == []:
        print "Found nothing."
        raise EmptySelectionError
    input_str = raw_input("Enter a number: ")
    if input_str == "":
        raise EmptySelectionError

    last_selection = selections
    try:
        n = int(input_str)
        if n < 0 or n >= len(selections):
            return None
        return selections[n],False
    except:
        if len(selections) > 2:
            ltr = input_str[0]
            try:
                n = int(input_str[1::].strip())
                return selections[n],True
            except Exception,e:
                print e
                return None,None

def search_for_uri(query, type):
    global last_selection
    global last_artist
    global last_album
    global last_track
    global SHORTCUTS
    if query in SHORTCUTS.keys():
        query = SHORTCUTS[query]

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
            artists = SPOTIFY.search(type, query)['artists']
            if artists == []: return None
            print_list(artists, "Artists")
            artist,play_now = select_from_list(artists)
            if play_now:
                uri = artist['uri'] if artist != None else None
                cur_state = DONE_STATE
                continue
            artist_id = artist['id'] if artist != None else None
            last_artist = artist['name'] is artist != None
            cur_state = ALBUM_STATE
        elif cur_state == ALBUM_STATE:
            if artist_id == None:
                print "Error: Invalid Artist Selection"
                return
            albums = SPOTIFY.get_artist_albums(artist_id)
            print_list(albums, "Albums")
            album,play_now = select_from_list(albums)
            last_album = album
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
            tracks = SPOTIFY.get_album_tracks(album_id)
            print_list(tracks, "Tracks")
            track,play_now = select_from_list(tracks)
            uri = track['uri'] if track != None else None
            cur_state = DONE_STATE
        elif cur_state == ALBUM_QUERY_STATE:
            albums = SPOTIFY.search(type, query)['albums']
            if albums == []: return None
            print_list(albums, "Albums")
            album,play_now = select_from_list(albums)
            last_album = album
            if play_now:
                uri = album['uri'] if album != None else None
                cur_state = DONE_STATE
                continue
            album_id = album['id'] if album != None else None
            cur_state = TRACK_STATE
        elif cur_state  == TRACK_QUERY_STATE:
            tracks = SPOTIFY.search(type, query)['tracks']
            if tracks == []: return None
            print_list(tracks, "Tracks")
            track,play_now = select_from_list(tracks)
            uri = track['uri']  if track != None else None
            cur_state = DONE_STATE
        elif cur_state == COMBO_SEARCH_STATE:
            results = SPOTIFY.search(type, query)
            combined = []
            combined.append(results["artists"])
            combined.append(results["albums"])
            combined.append(results["tracks"])
            print_2d_list(combined, ["Artists", "Albums", "Tracks"])
            combined = []
            combined.extend(results["artists"])
            combined.extend(results["albums"])
            combined.extend(results["tracks"])
            something,play_now = select_from_list(combined)
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

def evaluate_input(input_str):
    toks = input_str.split(" ")
    n_toks = len(toks)
    n_args = n_toks-1
    if input_str == "":
        return
    command = toks[0]
    cl = len(command)

    if command not in COMMANDS:
        print "This command does not exist. Searching for %s instead."%(input_str)

    if command == "set":
        if n_args == 2:
            set_command(toks[1], toks[2])
        else:
            print "Not enough arguments"
    elif command == "exit":
        exit()
    elif command == "play":
        if n_args == 0:
            SPOTIFY.pause(pause=False)
        elif n_args == 1:
            play_command(toks[1])
    elif command == "pause":
        if n_args == 0:
            SPOTIFY.pause(pause=True)
        elif n_args > 1:
            print "The 'pause' command only uses 0 or 1 argument"
            return
        else:
            pause_command(int(toks[1]))
    elif command == "user":
        username = ""
        if n_args == 1:
            username = toks[1]
        else:
            username = ENV_INFO["user"]
        user_command(username)
    elif command == "playlists":
        if n_args == 1:
            playlists_command(toks[1])
        else:
            playlists_command(ENV_INFO["user"])
    elif command in ["search-artist", "sar"]:
        if n_args >= 1:
            search_command(input_str[cl+1::], ["artists"])
    elif command in ["search-album", "sal"]:
        if n_args >= 1:
            search_command(input_str[cl+1::], ["albums"])
    elif command in ["search-track", "str"]:
        if n_args >= 1:
            search_command(input_str[cl+1::], ["tracks"])
    elif command in ["last_album", "lal"]:
        print last_album
    elif command in ["last_artist", "lar"]:
        print last_artist
    elif command == "help":
        display_help_message()
    else:
        search_command(input_str, ["artists","tracks","albums"])

"""
Initializes the users settings based on the stermrc file
"""
def configure():
    global SHORTCUTS
    global ENV_INFO
    try:
        rc_file = open(CONFIG_FILENAME,"r")
    except:
        print "No configuration file 'stermrc'"
        return

    for line in rc_file:
        line = line.strip()
        line = line.split("#")[0] # Ignore comments
        if "<-" in line:
            toks = line.split("<-")
            if len(toks) != 2:
                print "Error parsing rc file"
                return
            ENV_INFO[toks[0]] = toks[1]
            continue
        elif "=" in line:
            toks = line.split("=")
            if len(toks) != 2:
                print "Error parsing rc file"
                return
            SHORTCUTS[toks[0]] = toks[1]

def establish_authentication():
    if os.path.isfile(AUTH_FILENAME):
        auth_file = open(AUTH_FILENAME)
        for line in auth_file:
            line = line.strip()
            toks = line.split("=")
            ENV_INFO[toks[0]] = toks[1]
        print "Authentication file found"
    else:
        auth_data = authenticate()

def main():
    configure()
    establish_authentication()
    done = False
    if ENV_INFO['user'] == "":
        print "Welcome to Spotify Terminal!"
    else:
        print "Welcome %s."%(ENV_INFO['user'])
    print "Remember: When making a selection, putting 'p' before will start playing"
    print "          For example, 'p3' or 'p 3', will start playing selection 3"
    while not done:
        user_input = raw_input("spotify>")
        evaluate_input(user_input)

if __name__ == '__main__':
    main()
