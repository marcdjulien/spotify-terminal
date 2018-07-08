import os

def clear():
    os.system('cls')

def display_help_message():
    info = {}
    info['exit'] = ["exit", "Exit the program"]
    info['play [s]'] = ["play/p", "Play music. Selection s from last set of options if optional param is used"]
    info['pause'] = ["pause ", "Pause music"]
    info['next'] = ["next/n", "Next track"]
    info['prev'] = ["previous/prev/p", "Previous track"]
    info['user'] = ["user", "Display user info"]
    info['playlists'] = ["playlists", "List the current users playlists for selection"]
    info['search-artists'] = ["search-artist/sar", "Search for an artist to play"]
    info['search-albums'] = ["search-album/sal", "Search for an album to play"]
    info['search-tracks'] = ["search-track/str", "Search for a track to play"]
    info['help'] = ["help", "Display this help message"]
    print
    for line in info:
        print "%20s %s"%(info[line][0], info[line][1])

def is_int(n):
    try:
        n = int(n)
        return True
    except:
        return False

def in_range(n, list):
	return (0 <= n) and (n < len(list))

