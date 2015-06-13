
def display_help_message(self):
    info = {}
    info['exit'] = ["exit", "Exit the program"]
    info['play'] = ["play", "Play music"]
    info['pause'] = ["pause [d]", "Pause music, if the optional argument is used it will pause for d seconds"]
    info['user'] = ["user", "Display user info"]
    info['playlists'] = ["playlists", "List the current users playlists for selection"]
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

def in_range(n, list):
	return (0 <= n) and (n < len(list))