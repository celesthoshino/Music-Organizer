# Music Organizer

Sorts a messy music collection into tidy Artist and Album folders, and renames each song from the info stored inside it
(its "tags"). Put your songs in the `input` folder, run the script, and get them organized in the `output` folder:

```
output/
├── Daft Punk/
│   └── Discovery/
│       ├── 01 - One More Time.mp3
│       └── 02 - Aerodynamic.mp3
└── Unknown Artist/
    └── Unknown Album/
        └── track07.mp3
```

## Folder layout

```
music_organizer/
├── organize_music.py   the script
├── requirements.txt    Python packages to install
├── README.md           this file
├── input/              put your songs here (subfolders are fine)
└── output/             organized songs appear here, in Artist/Album folders
```

## Setup (one time)

1. Install **Python 3.9 or newer** from https://www.python.org/downloads/
   (on Windows, tick "Add Python to PATH" during install).
2. Open a terminal in the `music_organizer` folder and run:

   ```
   pip install -r requirements.txt
   ```

## How to use

1. Copy your songs into the `input` folder. Subfolders are fine; they're all searched.
2. Open a terminal in the `music_organizer` folder.
3. **Optional, recommended the first time:** see what would happen without changing anything:

   ```
   python organize_music.py --dry-run
   ```

4. Organize them for real:

   ```
   python organize_music.py
   ```

5. The organized songs are in the `output` folder. Your originals in `input` are left alone (they're copied, not moved),
   unless you use `--move`.

| Command | What it does |
|---|---|
| `python organize_music.py` | Copies songs into `Artist/Album/01 - Title.mp3` |
| `python organize_music.py --dry-run` | Shows what would happen without copying anything |
| `python organize_music.py --move` | Moves songs instead of copying (saves space, empties `input`) |
| `python organize_music.py --flat` | No folders, just renames to `Artist - Title.mp3` |
| `python organize_music.py --help` | Shows all options |

## Options

| Option | Default | Meaning |
|---|---|---|
| `--flat` | off | Put every song directly in `output`, named `Artist - Title.mp3` |
| `--move` | off | Move files instead of copying them |
| `--dry-run` | off | Only show what would happen. Nothing is copied, moved or renamed |
| `-i`, `--input` | `input` folder | Folder to read songs from (subfolders included) |
| `-o`, `--output` | `output` folder | Folder to organize songs into |

## How songs are named

The script reads these tags from each song:

| Tag | Used for |
|---|---|
| Album artist | The artist folder. Keeps albums with guest artists together in one folder |
| Artist | The artist folder, if there's no album artist. Also used in `--flat` names |
| Album | The album folder |
| Track number | The number at the front: `01 - ` |
| Disc number | Added for albums with several discs: `2-01 - ` |
| Title | The file name |

Missing tags get sensible defaults: no artist → `Unknown Artist`, no album → `Unknown Album`, no title → the original
file name is kept, no track number → no number in front.

Characters that aren't allowed in file names (`/ \ : * ? " < > |`) are replaced with `_`. For example, `AC/DC` becomes
`AC_DC`.

**Song types it reads:** `.mp3 .flac .m4a .aac .ogg .oga .opus .wma .wav .aif .aiff .ape .wv`.
Other files, like cover images and playlists, are counted as "ignored" and left alone.

## Good to know

- **By default nothing in `input` is changed.** Songs are copied, so you can check the result before deleting anything.
- **Use `--dry-run` first** if you're unsure. It prints exactly what would happen.
- **The music itself is never changed.** Files are only copied or moved and renamed, and the audio and tags stay as they were.
- **Exact duplicates are skipped.** If the same song file is in `input` twice (even with different names), or is
  already in the output folder from an earlier run, it's only kept once. With `--move`, duplicates stay in `input`.
- **Running it again is safe.** Songs that were already organized are recognized as duplicates and skipped.
- **Different songs that end up with the same name** are never overwritten. The second one gets ` (2)` added.
- **Cover images aren't copied.** Most music players read the cover from inside the song file anyway.
- **Badly tagged songs** end up in `Unknown Artist`. Fix their tags with a free tag editor like **Mp3tag** (Windows)
  or **MusicBrainz Picard** (any system, and it can fill in tags automatically), then run the script again.

## Troubleshooting

**`Error: mutagen is not installed`**
Run `pip install -r requirements.txt` from inside the `music_organizer` folder.

**Lots of songs end up in `Unknown Artist`**
Those files have no tags. Check one in your music player: if it shows no artist there either, the tags are really
missing. Use a tag editor (see above) to add them.

**The same artist is split into two folders**
The tags are spelled differently, for example `The Beatles` and `Beatles`. Fix the tags so they match.

**`the output folder can't be inside the input folder`**
Choose an output folder somewhere else, otherwise the script would sort its own results.

**`'python' is not recognized`**
Python isn't on your PATH. On Windows, try `py organize_music.py` instead, or reinstall Python with "Add Python to PATH" ticked.
