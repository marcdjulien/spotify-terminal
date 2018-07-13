"""
Spotify Terminal authenticates with Spotify by directing
your browser to the authentication link.

After you log in and authenticate the redirect url will bring you to a localhost
page. At this point Spotify Terminal will be running a "web server"
to obtain the authentication information.
"""
from globals import *
import os
import urllib
from threading import Thread
import webbrowser
from BaseHTTPServer import *


logger = logging.getLogger(__name__)


PORT = 80
HOST = "https://accounts.spotify.com/authorize"
CLIENT_ID = "bd392941710943429ba45210c9b2c640"
REDIRECT_URI = "http://localhost/"
SCOPE = " ".join([
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-read-currently-playing",
    "user-modify-playback-state",
    "user-library-read"
])
RESPONSE_TYPE = "token"
PARAMS = { "client_id":CLIENT_ID,
           "redirect_uri":REDIRECT_URI,
           "scope":SCOPE,
           "response_type":RESPONSE_TYPE
         }
URL = HOST+"?"+urllib.urlencode(PARAMS)
# After you authenticate this page will grab the web hash
# that contains your auth token
HTML = """
<html>
<div id="hash"></div>
<script type="text/javascript">
window.location = window.location.hash.substring(1);
</script>
</html>
"""
# When you are authenticated this page will display
HTML2 = """
<html>
{}
\n
You may close this tab and continue to jam!
</html>
""".format(HTML_TITLE)
data = "Empty"
class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        global data
        if "access_token" in self.path:
            data = self.parse_path(self.path[1::])
            self.send_response(200)
            self.wfile.write(HTML2)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(HTML)
        return

    def parse_path(self, path):
        data = {}
        items = path.split("&")
        for thing in items:
            toks = thing.split("=")
            data[toks[0]] = toks[1]
        return data



def start_server():
    server = HTTPServer(('localhost', PORT), Handler)
    server.handle_request() # Get token
    server.handle_request() # Return Token wis URL

def write_auth_file():
    global data
    if not os.path.isdir(TEMP_DIR):
        os.mkdir(TEMP_DIR)
    auth_file = open(AUTH_FILENAME, "w")
    for k,v in data.items():
        auth_file.write("%s=%s\n"%(k,v))
    auth_file.close()
    logger.debug("Auth file created")

# This begin the authentication process
def authenticate():
    global data
    # Start running the server
    web_thread = Thread(target=start_server)
    web_thread.start()

    # Open the authentication link
    webbrowser.open_new_tab(URL)

    # Wait for the server to make the 2 expected http request
    web_thread.join()

    # Save the new authentication information to disk
    write_auth_file()

    return data
