# spotifyterminal
Terminal program to play/control music via Spotify.

# Install
Unicurses and Requests for Python are required to run this program.

https://pypi.org/project/UniCurses


http://docs.python-requests.org/en/v2.9.1/user/install/


# Usage
Execute the following command to run the program:
```
./spotify.py [username]
```
Where ```username``` is your Spotify username.

# \# Search
By typing ```#``` you can begin a search.

# : Commands
By typing ```:``` you can enter commands. The following is a list of all commands:

```search [query]``` | Search for an Artist, Album or Song.

```find [index] [query]``` | Find an entry in the currently list that contains *query*. The UI will automatically go to the *index* found entry.

```volume [0-100]``` | Set the volume.

```play``` | Start playing.

```pause``` | Pause the player.

```repeat [off|context|track]``` | Set the repeat mode.

```shuffle [True|False]``` | Set the shuffle mode.

```exit``` | Exit the application.

# Other Tips
Type ```/``` is a shortcut to the find command. You can also type ```n``` or ```p``` to find a next or previous entry.

Use ```:q``` to exit.

Use ```Backspace``` to cycle through previous Track listings.

# Notes
This has only been tested on Linux and Windows.