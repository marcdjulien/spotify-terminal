from Globals import *
import os
import urllib
from threading import Thread
import webbrowser
from BaseHTTPServer import *

PORT = 80
HOST = "https://accounts.spotify.com/authorize"
CLIENT_ID = "bd392941710943429ba45210c9b2c640"
REDIRECT_URI = "http://localhost/"
SCOPE = "playlist-read-private playlist-read-collaborative"
RESPONSE_TYPE = "token"
PARAMS = { "client_id":CLIENT_ID,
           "redirect_uri":REDIRECT_URI,
           "scope":SCOPE,
           "response_type":RESPONSE_TYPE 
         }
URL = HOST+"?"+urllib.urlencode(PARAMS)
HTML = """
<html>
<div id="hash"></div>
<script type="text/javascript">
window.location = window.location.hash.substring(1);
</script>
</html>
"""
HTML2 = """
<html>
You have been authenticated! Continue jamming!
</html>
"""
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



def authenticate():
    global data
    web_thread = Thread(target=start_server)
    web_thread.start()
    webbrowser.open_new_tab(URL)
    web_thread.join()
    write_auth_file()
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
    print "Auth file created"
