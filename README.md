# spotifyterminal
Terminal program to play/control music via Spotify.

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
│ Discover Weekly      ││                                                                        │
│ MJK et al            ││                                                                        │
│ Download 2           ││                                                                        │
│ Your Time Capsule    ││                                                                        │
│ Feed Me              ││                                                                        │
│ How To Destroy Angels││                                                                        │
│ Your Summer Rewind   ││                                                                        │
│ Party Playlist       ││                                                                        │
│ SoundHound           ││                                                                        │
│ Your Top Songs 2016  ││                                                                        │
│ Blanck Mass          ││                                                                        │
│ THIS IS: HEALTH      ││                                                                        │
│ Mr. Robot - music fro││                                                                        │
│ Seven Lions Discograp││                                                                        │
│ MMBP                 ││                                                                        │
│ Discover Weekly Archi││                                                                        │
│ Stranger Things      ││                                                                        │
│ Best Trap and Electro││                                                                        │
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
│ DragonBall Z  Bruce F││                                                                        │
│ Wolfgang             ││                                                                        │
│ HEALTH + DF          ││                                                                        │
│ The Bloody Beetroots ││                                                                        │
│ Download             ││                                                                        │
└──────────────────────┘└────────────────────────────────────────────────────────────────────────┘

                              Left                           Fine                         SONOIO
```
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

# Other Tips and Tricks
Type ```/``` is a shortcut to the find command. You can also type ```n``` or ```p``` to find a next or previous entry (similar to vim).

```:q``` to exit.

```Backspace``` to cycle through previous Track listings.

```Shift + S``` on any entry to immediately go to the Album track list.

```Shift + D``` on any entry to immediately go to the Artist page.

```Shift + R``` to re-sync the player.


# Notes
This has only been tested on Linux and Windows.
