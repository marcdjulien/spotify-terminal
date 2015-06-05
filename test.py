from SpotifyRemote import Sp
import time

sp = SpotifyRemote()
print "Playing album.."
sp.play('spotify:album:6eWtdQm0hSlTgpkbw4LaBG')
time.sleep(5)
print "Pausing song.."
sp.pause()
time.sleep(2)
print "Unpausing song.."
sp.unpause()