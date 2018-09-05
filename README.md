# Spotify Terminal
Terminal program to play/control music via Spotify. Some features require a Spotify Premium account.

```
┌──────────────────────┐┌────────────────────────────────────────────────────────────────────────┐
│ marcjulien           ││ Fine                                                                   │
│                      ││                                                                        │
│ Techno Bunker        ││           I Don't Know                  Fine                SONOIO     │
│ Guitar               ││                   Left                  Fine                SONOIO     │
│ Boxplot              ││     Thanks for Calling                  Fine                SONOIO     │
│ Instrumental Madness ││                 Pieces                  Fine                SONOIO     │
│ Bad Religion         ││              Vitamin D                  Fine                SONOIO     │
│ Wonderland Complete  ││              Bad Habit                  Fine                SONOIO     │
│ Better Alone         ││          Under the Sea                  Fine                SONOIO     │
│ WAF                  ││          What's Before                  Fine                SONOIO     │
│ The Ones That Got Awa││    I Don't Know (Coda)                  Fine                SONOIO     │
│ Your Top Songs 2017  ││                                                                        │
│ Vince Staples  Big Fi││                                                                        │
│ A Perfect Circle     │└────────────────────────────────────────────────────────────────────────┘
│ No Mana              │┌────────────────────────────────────────────────────────────────────────┐
│ ATTLAS               ││ Thanks for Calling                                                     │
│ ATTLAS Storyline Vol.││ Fine                                                                   │
│ ATTLAS After Hours Mi││ SONOIO                                                                 │
│ Old Collection       ││                                                                        │
│ Jack U NYE Playlist  ││ (S) <<  (P)  >> (o)  --  ++                                            │
│ Ki:Theory  KITTY HAWK││                                                                        │
│ Mobile Download      ││ Computer: YEARZERO                                                     │
│ Space                ││                                                                        │
└──────────────────────┘└────────────────────────────────────────────────────────────────────────┘
------------------------
                              Left                           Fine                         SONOIO
```
# Install
Unicurses and Requests for Python are required to run this program.

https://pypi.org/project/UniCurses
(A version of this already comes with the checkout)

http://docs.python-requests.org/en/v2.9.1/user/install/
```
pip install requests
```

Then clone or download this repository to use the application.

# Usage
Execute the following command to run the program:
```
Linux: ./spotify.py [username]
Windows: spotify.py [username]
```
Where ```username``` is either the email associated with your Spotify account or the user id.

# " Search
By typing ```"``` you can begin a search. You may optionally the search with an end ".

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

# Other Tips and Tricks
```TAB``` while on an artist's page to toggle between their main page and a list of all of their tracks. This is useful if you want to listen to all tracks by an artist within the same context.

```/``` is a shortcut to the ```find``` command. You can also type ```n``` or ```p``` to find a next or previous entry (similar to vim).

```:q``` to exit.

```Backspace``` to cycle through previous track listings.

```Shift + S``` on any track to immediately go to the album page.

```Shift + D``` on any track to immediately go to the artist page.

```Shift + R``` to re-sync the player.

```Shift + >``` to play the next song.

```Shift + <``` to play the previous song.

```Shift + W``` to see list of your devices.

```Shift + 0-9``` to set to set the volume. 1...0 for volume 10...100.

```Shift + ` ``` to mute.

```Shift + P ``` to add a song to a playlist.

# Notes
This has only been tested on Linux and Windows with a Spotify Premium account.
