# Spotify Terminal
Terminal program to play/control music via Spotify. Some features require a Spotify Premium account.

```
┌──────────────────────────────┐┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│     [Spotify Terminal]       ││ Saved                                                                                         │
│        Display Name          ││                                                                                               │
│______________________________││                Can You Feel It                 Can You Feel It                  T-Mass, Enthic│
│                              ││                    Convolution                  Tear The Roots                         Kaleida│
│ Saved                        ││    Tactical Precision Disarray     Tactical Precision Disarray                     Perturbator│
│ NIN Trilogy                  ││          Heptan - Enjoii Remix           Heptan (Enjoii Remix)        MYSTXRIVL, Sokos, Enjoii│
│ Techno Bunker                ││ Watch You Sleeping - Instrumen              Watch You Sleeping   Blue Foundation, Mark Kozelek│
│ Guitar                       ││            XXVI Crimes of Love             XXVI Crimes of Love                       Huoratron│
│ Boxplot                      ││ Something About Smooth Seas an  Something About Smooth Seas an                      Half Empty│
│ Instrumental Madness         ││ Bringing Me Down (feat. Ruelle                         Silence               Ki:Theory, Ruelle│
│ Bad Religion                 ││                 Sell Your Soul             Time Is A Landscape      We Plants Are Happy Plants│
│ Wonderland Complete          ││                      Humanizer                       Humanizer                       Powercyan│
│ Better Alone                 ││                     STILLBIRTH                      STILLBIRTH                     Alice Glass│
│ WAF                          ││                   Still Wasted                    Still Wasted                 Enjoii, Skeler.│
│ The Ones That Got Away       ││                                                                                        Ic3peak│
│ Your Top Songs 2017          ││    High Speed Weekend Survivor        Feed Me's Family Reunion                         Feed Me│
│ Vince Staples  Big Fish Theor││                      It's Only                      Deflection                         Arkasia│
│ Discover Weekly              ││         We Stayed Up All Night          We Stayed Up All Night                  Tourist, Ardyn│
│ Stranger Things              ││     Serpent's Missing Messages            Assorted Repetitions                         No Mana│
│ Best Trap and Electronic     ││                 E Is More Than            Assorted Repetitions                         No Mana│
│ A Perfect Circle             ││                      Gray Pill                  Piety of Ashes                   The Flashbulb│
│ No Mana                      ││ Turn off the Lights (feat. Ale  Turn off the Lights (feat. Ale      Chris Lake, Alexis Roberts│
│ ATTLAS                       ││                    SV_Cheats 0             The Maze To Nowhere                            Lorn│
│ ATTLAS Storyline Vol. 1      ││                     Tramontane                   Tramontane EP                         Boxplot│
│ ATTLAS After Hours Mix       ││           Runnin' - Radio Edit                         Runnin'           Cutline, Belle Humble│
│ Jack U NYE Playlist          ││                    Star Trails                     Star Trails          Fraunhofer Diffraction│
│ Ki:Theory  KITTY HAWK        ││          The Bleeding of Mercy            The Course of Empire           Telepathic Teddy Bear│
│ Mobile Download              │└───────────────────────────────────────────────────────────────────────────────────────────────┘
│ Space                        │┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ DragonBall Z  Bruce Faulconer││ Can You Feel It                                                                               │
│ Wolfgang                     ││ Can You Feel It                                                                               │
│ HEALTH + DF                  ││ T-Mass, Enthic                                                                                │
│ The Bloody Beetroots  HIDE   ││                                                                                               │
│ Download                     ││ (s) <<  (P)  >> (x)  --  ++                                                                   │
│ PnR                          ││                                                                                               │
│ Starred                      ││ Computer: YEARZERO                                                                            │
│ Seven Lions                  ││                                                                                               │
│ COHSOTV                      ││                                                                                               │
│ Buckethead                   ││                                                                                               │
└──────────────────────────────┘└───────────────────────────────────────────────────────────────────────────────────────────────┘
---------------------------------------------------------------------------------------------------------------
                            Can You Feel It                            Can You Feel It                             T-Mass, Enthic
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

Use --help or -h to see more options.
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

```Shift + ?``` to immediately go to the context of the currently playing song.

```Shift + X``` to immediately go to the album page of the currently playing song.

```Shift + C``` to immediately go to the artist page of the currently playing song.

```Shift + R``` to re-sync the player.

```Shift + >``` to play the next song.

```Shift + <``` to play the previous song.

```Shift + W``` to see list of your devices.

```Shift + 0-9``` to set to set the volume. 1...0 for volume 10...100.

```Shift + ` ``` to mute.

```Shift + P ``` to add a song to a playlist.

# Notes
This has only been tested on Linux and Windows with a Spotify Premium account.
