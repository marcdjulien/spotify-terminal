"""
Spotify Terminal authenticates with Spotify by directing
your browser to the locally hosted authentication link.
"""
import json
import os
import requests
import struct
import urllib.request, urllib.parse, urllib.error
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from . import common


logger = common.logging.getLogger(__name__)


class Authenticator(object):
    """Authenticate."""

    port = 12345

    scope = " ".join([
        "playlist-modify-private",
        "playlist-modify-public",
        "playlist-read-collaborative",
        "playlist-read-private",
        "user-read-email",
        "user-read-currently-playing",
        "user-read-playback-state",
        "user-read-private",
        "user-modify-playback-state",
        "user-library-modify",
        "user-library-read"
    ])

    def __init__(self, username):
        self.username = username
        self.token_type = None
        self.access_token = None
        self.refresh_token = None
        self.app_data = []
        self._data = {}
        self._init()

    def authenticate(self):
        # Try to use local auth file.
        success = False
        if self.username is not None:
            success = self._auth_from_file()
        
        # Re-authenticate
        if not success:
            def start_server():
                http_server = HTTPServer(('localhost', self.port), AuthenticationHandler)
                http_server.handle_request()
                self.data = http_server.data

            logger.debug("Starting auth server")
            web_thread = Thread(target=start_server)
            web_thread.start()

            logger.debug("Opening %s in browser", self._authorize_url())
            webbrowser.open_new_tab(self._authorize_url())

            logger.debug("Waiting for user to complete authentication process")
            web_thread.join()

            self._get_tokens()

    def refresh(self):
        logger.debug("Refreshing token")
        post_body = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.app_data[0],
            "client_secret": self.app_data[1]
        }

        resp = requests.post(self._token_url(), data=post_body)
        resp.raise_for_status()

        data = json.loads(resp.text)
        data["refresh_token"] = self.refresh_token
        self._data = data
        for key, value in self._data.items():
            setattr(self, key, value)

        if self.username is not None:
            self.save(self.username)

    def _init(self):
        # Full disclosure -- This is easy to decode.
        # However, this program does not save any of your
        # personal information, so none of your data is compromised.
        filename = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".st"
        )
        with open(filename, "rb") as f:
            line = "".join([
                chr(i-1993) for i in struct.unpack("64I", f.readline())
            ])
            self.app_data.append(line[0:32])
            self.app_data.append(line[32::])

    def _auth_from_file(self):
        required_keys = {"access_token",
                         "token_type",
                         "refresh_token"}
        found_keys = set()
        if os.path.isfile(common.get_auth_filename(self.username)):
            with open(common.get_auth_filename(self.username)) as auth_file:
                for line in auth_file:
                    line = line.strip()
                    toks = line.split("=")
                    if toks[0] in required_keys:
                        logger.info("Found %s in auth file", toks[0])
                        setattr(self, toks[0], toks[1])
                        self._data[toks[0]] = toks[1]
                        found_keys.add(toks[0])
            return len(required_keys.symmetric_difference(found_keys)) == 0
        else:
            return False

    def _get_tokens(self):
        # First request to get tokens.
        post_body = {
            "grant_type": "authorization_code",
            "code": self.data["code"],
            "redirect_uri": "http://localhost:{}/".format(self.port),
            "client_id": self.app_data[0],
            "client_secret": self.app_data[1]
        }
        resp = requests.post(self._token_url(), data=post_body)
        resp.raise_for_status()
        self._data = json.loads(resp.text)

        for key, value in self._data.items():
            setattr(self, key, value)

    def _authorize_url(self):
        params = {
            "client_id": self.app_data[0],
            "redirect_uri": "http://localhost:{}/".format(self.port),
            "scope": self.scope,
            "response_type": "code",
            "show_dialog": False
        }
        return "https://accounts.spotify.com/authorize" + "?" + urllib.parse.urlencode(params)

    def _token_url(self):
        return "https://accounts.spotify.com/api/token"

    def save(self, username):
        if self._data:
            if not os.path.isdir(common.get_app_dir()):
                os.mkdir(common.get_app_dir())

            with open(common.get_auth_filename(username), "w") as auth_file:
                for k, v in self._data.items():
                    auth_file.write("%s=%s\n" % (k, v))
                logger.debug("%s created", common.get_auth_filename(username))
        else:
            try:
                os.remove(common.get_auth_filename(username))
                logger.debug("%s deleted", common.get_auth_filename(username))
            except OSError as e:
                logger.warning(e)


class AuthenticationHandler(BaseHTTPRequestHandler):
    HTML = """
        <p><span style="color: rgb(71, 85, 119); font-family: Tahoma, Geneva, sans-serif; font-size: 48px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial; float: none; display: inline !important;">You may close this tab, and continue jamming in your terminal!</span><span style="color: rgb(40, 50, 78); font-family: Tahoma, Geneva, sans-serif; font-size: 48px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial; float: none; display: inline !important;">&nbsp;</span></p>    
    <script type="text/javascript">
        window.close();
    </script>
    """

    def do_GET(self):
        if "code=" in self.path:
            self.server.data = self.parse_path(self.path[2::])
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes(self.HTML, "utf-8"))

        if "favicon" in self.path:
            with open("favicon.ico", "rb") as icon_file:
                self.wfile.write(icon_file.read()) 

    def parse_path(self, path):
        data = {}
        items = path.split("&")
        for thing in items:
            toks = thing.split("=")
            data[toks[0]] = toks[1]
        return data

    def log_message(self, format, *args):
        logger.debug(format, *args)
