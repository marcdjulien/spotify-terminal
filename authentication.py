"""
Spotify Terminal authenticates with Spotify by directing
your browser to the locally hosted authentication link.

After you log in and authenticate the redirect url will bring you to a localhost
page. At this point Spotify Terminal will be running a web server
to obtain the authentication information.
"""
import os
import urllib
import webbrowser
from BaseHTTPServer import *
from threading import Thread

import common


logger = common.logging.getLogger(__name__)


CLIENT_ID = "bd392941710943429ba45210c9b2c640"

PORT = 12345

REDIRECT_URI = "http://localhost:{}/".format(PORT)

SCOPE = " ".join([
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-read-currently-playing",
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-library-read"
])

RESPONSE_TYPE = "token"

PARAMS = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    "response_type": RESPONSE_TYPE
}

URL = "https://accounts.spotify.com/authorize" + "?" + urllib.urlencode(PARAMS)

# After you authenticate this page will grab the web hash
# that contains your auth token and redirect us to a url
# that we can use to exract it.
HTML = """
<html>
    <div id="hash"></div>

    <script type="text/javascript">
        window.location = window.location.hash.substring(1);
    </script>
</html>
"""

# When you are authenticated this page will be returned
# which closes the tab.
HTML2 = """
<html>
    <script type="text/javascript">
            window.close();
    </script>
</html>
"""

data = None


class AuthenticationHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        global data
        logger.info(self.path)
        if "access_token" in self.path:
            data = self.parse_path(self.path[1::])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(HTML2)
            return
        else:
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

    def log_message(self, format, *args):
        logger.debug(format, *args)


def start_server():
    server = HTTPServer(('localhost', PORT), AuthenticationHandler)
    server.handle_request()  # Get token
    server.handle_request()  # Return Token in URL


def write_auth_file(data):
    if not os.path.isdir(common.APP_DIR):
        os.mkdir(common.APP_DIR)
    auth_file = open(common.AUTH_FILENAME, "w")
    for k, v in data.items():
        auth_file.write("%s=%s\n" % (k, v))
    auth_file.close()
    logger.debug("%s created", common.AUTH_FILENAME)


def authenticate():
    """Execute the authentication process."""
    global data
    # Start running the server
    web_thread = Thread(target=start_server)
    web_thread.start()

    # Open the authentication link.
    # A web browser is required because token information is returned
    # as a hash fragment.
    webbrowser.open_new_tab(URL)

    # Wait for the server to make the 2 expected http request
    web_thread.join()

    # Save the new authentication information to disk
    write_auth_file(data)

    return data
