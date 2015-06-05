import time
import sys
import json
import string
from threading import Timer
from SpotifyRemote import SpotifyRemote

sp = SpotifyRemote()
commands = ["set", "exit", "pause", "play", "user", "playlists", "search-artist", "sar",
            "search-album", "sal", "search-track", "str", "last-album", "lal", "last-artist",
            "lar", "help"]
env_info = {"user":""}
    
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

shortcuts = {}

class InvalidSelectionError(Exception):
    pass
class EmptySelectionError(Exception):
    pass

def display_help_message():
    help_msg = """
search-album
search-album
search-artist
last_album
last_artist
last_track
set
exit
"""
    print help_msg 
def is_int(n):
    try:
        n = int(n)
        return True
    except:
        return False
    return False

def set_command(prop, value):
    if prop not in env_info.keys():
        print "This property does not exit"
    else:
        env_info[prop] = value
    return

def pause_command(time):
    sp.pause(pause=True)
    Timer(time, sp.pause, [False]).start()

def play_command(n):
    if is_int(n):
        n = int(n)
        if (0 <= n) and (n < len(last_selection)):
            track_uri = last_selection[n]['uri']
            sp.play(track_uri)
        else:
            print "Error: Invalid Track Selection"
            return
    else:
        return

def user_command(username):
    info = sp.get_user_info(username)
    print "{0} [{1}]".format(info["display_name"], info['id'])
    print "Account Type: {0}".format(info['type'])

def playlists_command(username):
    playlists = sp.get_user_playlists(username)

def search_command(query, type):
    try:
        uri = search_for_uri(query, type)
        if uri == None:
            return
        else:
            sp.play(uri)
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
    input_str = raw_input("")
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
                n = int(input_str[1::])
                return selections[n],True
            except:
                return None,None

def is_uri(string):
    return "spotify:" in string

def search_for_uri(query, type):
    global last_selection
    global last_artist
    global last_album
    global last_track
    global shortcuts
    if query in shortcuts.keys():
        query = shortcuts[query]

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
            artists = sp.search(type, query)['artists']
            if artists == []: return None
            print_list(artists, "Artists")
            artist,er = select_from_list(artists)
            artist_id = artist['id'] if not er else None
            last_artist = artist['name'] is artist != None
            cur_state = ALBUM_STATE
        elif cur_state == ALBUM_STATE:
            if artist_id == None:
                print "Error: Invalid Artist Selection"
                return
            albums = sp.get_artist_albums(artist_id)
            print_list(albums, "Albums")
            album,er = select_from_list(albums)
            last_album = album
            if er:
                uri = album['uri']
                cur_state = DONE_STATE
                continue
            album_id = album['id']
            cur_state = TRACK_STATE
        elif cur_state  == TRACK_STATE:
            if album_id == None:
                print "Error: Invalid Album Selection"
                return
            tracks = sp.get_album_tracks(album_id)
            print_list(tracks, "Tracks")
            track,er = select_from_list(tracks)
            if track != None: uri = track['uri']
            cur_state = DONE_STATE
        elif cur_state == ALBUM_QUERY_STATE:
            albums = sp.search(type, query)['albums']
            if albums == []: return None
            print_list(albums, "Albums")
            album,er = select_from_list(albums)
            last_album = album
            if er:
                uri = album['uri']
                cur_state = DONE_STATE
                continue
            album_id = album['id']
            cur_state = TRACK_STATE
        elif cur_state  == TRACK_QUERY_STATE:
            tracks = sp.search(type, query)['tracks']
            if tracks == []: return None
            print_list(tracks, "Tracks")
            track,er = select_from_list(tracks)
            if track != None: uri = track['uri']
            cur_state = DONE_STATE
        elif cur_state == COMBO_SEARCH_STATE:
            results = sp.search(type, query)
            combined = []
            combined.append(results["artists"])
            combined.append(results["albums"])
            combined.append(results["tracks"])
            print_2d_list(combined, ["Artists", "Albums", "Tracks"])
            combined = []
            combined.extend(results["artists"])
            combined.extend(results["albums"])
            combined.extend(results["tracks"])
            something,er = select_from_list(combined)
            if something == None:
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

def in_range(n, lower, upper):
    if n >= lower:
        if upper == INF:
            return True
        else:
            return n <= upper
    else:
        return False

def evaluate_input(input_str):
    toks = input_str.split(" ")
    n_toks = len(toks)
    n_args = n_toks-1
    if input_str == "":
        return
    command = toks[0]
    cl = len(command)

    if command not in commands:
        print "This command does not exist. Searching."

    if command == "set":
        if n_args == 2:
            set_command(toks[1], toks[2])
        else:
            print "Not enough arguments"
    elif command == "exit":
        exit()
    elif command == "play":
        if n_args == 0:
            sp.pause(pause=False)
        elif n_args == 1:
            play_command(toks[1])
    elif command == "pause":
        if n_args == 0:
            sp.pause(pause=True)
        elif n_args > 1:
            print "The 'pause' command only uses 1 argument"
            return
        else:
            pause_command(int(toks[1]))
    elif command == "user":
        username = ""
        if n_args == 1:
            username = toks[1]
        else:
            username = env_info["user"]
        user_command(username)
    elif command == "playlists":
        if n_args == 1:
            playlists_command(toks[1])
        else:
            playlists_command(env_info["user"])
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


def init():
    global shortcuts
    global env_info
    rc_file = open("stermrc","r")
    for line in rc_file:
        line = line.strip()
        if "<-" in line:
            toks = line.split("<-")
            env_info[toks[0]] = toks[1]
            continue
        toks = line.split("=")
        if len(toks) != 2:
            print "Error parsing rc file"
            return
        shortcuts[toks[0]] = toks[1]

def main():
    init()
    done = False
    if env_info['user'] == "":
        print "Welcome to Spotify Terminal!"
    else:
        print "Welcome %s."%(env_info['user'])
    while not done:
        user_input = raw_input("spotify>")
        evaluate_input(user_input)

if __name__ == '__main__':
    main()
