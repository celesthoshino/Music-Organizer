"""
Music Organizer
---------------
Put songs in the "input" folder, run this script, and they get sorted into
artist and album folders in the "output" folder, named from their tags:

    output/Artist/Album/01 - Song Title.mp3

    python organize_music.py              # copy into Artist/Album folders
    python organize_music.py --dry-run    # only show what would happen
    python organize_music.py --move       # move instead of copy
    python organize_music.py --flat       # output/Artist - Title.mp3, no folders

See README.md for all the details.
"""

import argparse
import filecmp
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

try:
    import mutagen
except ImportError:
    sys.exit("Error: mutagen is not installed.\nFix it by running:  pip install -r requirements.txt")

# The input/output folders live next to this script, so it works no matter
# which folder you run it from.
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wma",
                    ".wav", ".aif", ".aiff", ".ape", ".wv"}

# Each file type stores the same song info under different names (tags).
# These are the names to look for, for each piece of info.
TAG_NAMES = {
    "artist":      ["artist", "TPE1", "Author"],
    "albumartist": ["albumartist", "album artist", "TPE2", "WM/AlbumArtist"],
    "album":       ["album", "TALB", "WM/AlbumTitle"],
    "title":       ["title", "TIT2", "Title"],
    "track":       ["tracknumber", "track", "TRCK", "WM/TrackNumber"],
    "disc":        ["discnumber", "disc", "TPOS", "WM/PartOfSet"],
}

UNKNOWN_ARTIST = "Unknown Artist"
UNKNOWN_ALBUM = "Unknown Album"

# Characters Windows doesn't allow in file and folder names, and names it reserves.
BAD_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}


def read_tag(tags, names: list[str]) -> str:
    """The first non-empty value found under any of `names`, as text."""
    for name in names:
        try:
            value = tags[name]
        except (KeyError, ValueError, TypeError):
            continue
        if hasattr(value, "text"):          # mp3/wav/aiff tags keep the text inside
            value = value.text
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        value = getattr(value, "value", value)  # wma tags keep it in .value
        text = str(value).split("\x00")[0].strip()
        if text:
            return text
    return ""


def read_wav_info_tags(path: Path) -> dict:
    """
    WAV files can store tags in their own 'INFO' section (Windows and many programs
    do this), which mutagen doesn't read. Returns e.g. {b"IART": "Artist", ...}.
    """
    found = {}
    with open(path, "rb") as f:
        header = f.read(12)
        if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            return found
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id, size = chunk_header[:4], int.from_bytes(chunk_header[4:], "little")
            if chunk_id != b"LIST":
                f.seek(size + (size & 1), 1)  # skip the audio and other sections
                continue
            data = f.read(size + (size & 1))
            if data[:4] != b"INFO":
                continue
            pos = 4
            while pos + 8 <= len(data):
                item_id, item_size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], "little")
                raw = data[pos + 8:pos + 8 + item_size].split(b"\x00")[0]
                try:
                    found[item_id] = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    found[item_id] = raw.decode("latin-1").strip()
                pos += 8 + item_size + (item_size & 1)
    return found


def read_song_info(path: Path) -> dict:
    """Artist, album, title, track and disc from the file's tags. Empty values if it has none."""
    try:
        audio = mutagen.File(path, easy=True)
    except Exception:
        audio = None  # damaged or unreadable tags: treat as untagged
    tags = getattr(audio, "tags", None)
    if tags:
        return {field: read_tag(tags, names) for field, names in TAG_NAMES.items()}

    info = {field: "" for field in TAG_NAMES}
    if path.suffix.lower() == ".wav":
        try:
            wav = read_wav_info_tags(path)
        except OSError:
            wav = {}
        info.update(artist=wav.get(b"IART", ""), album=wav.get(b"IPRD", ""),
                    title=wav.get(b"INAM", ""), track=wav.get(b"ITRK") or wav.get(b"IPRT", ""))
    return info


def parse_number(text: str):
    """'3/12' -> (3, 12), '05' -> (5, None), '' -> (None, None)"""
    match = re.match(r"\s*(\d+)(?:\s*/\s*(\d+))?", text or "")
    if not match or int(match[1]) == 0:
        return None, None
    return int(match[1]), int(match[2]) if match[2] else None


def safe_name(text: str, fallback: str) -> str:
    """Make text usable as a file or folder name on any system."""
    text = BAD_CHARACTERS.sub("_", text or "").strip()
    text = text[:120].rstrip(". ")  # Windows doesn't allow names ending in a dot or space
    if not text:
        return fallback
    if text.split(".")[0].upper() in RESERVED_NAMES:
        text = "_" + text
    return text


def destination(path: Path, info: dict, flat: bool) -> Path:
    """Where the song goes, relative to the output folder."""
    ext = path.suffix.lower()
    title = info["title"] or path.stem
    if flat:
        name = f"{info['artist']} - {title}" if info["artist"] else title
        return Path(safe_name(name, path.stem) + ext)

    # Album artist keeps albums with guest artists (or compilations) together in one folder.
    artist = safe_name(info["albumartist"] or info["artist"], UNKNOWN_ARTIST)
    album = safe_name(info["album"], UNKNOWN_ALBUM)
    track, _ = parse_number(info["track"])
    disc, discs = parse_number(info["disc"])
    if track and disc and (disc > 1 or (discs or 1) > 1):
        name = f"{disc}-{track:02d} - {title}"  # multi-disc albums: 1-01, 1-02, ..., 2-01
    elif track:
        name = f"{track:02d} - {title}"
    else:
        name = title
    return Path(artist, album, safe_name(name, path.stem) + ext)


class DuplicateFinder:
    """
    Spots exact copies (same content, any name) going into the same folder.
    Only files with the same size are compared byte by byte, so it stays fast.
    """

    def __init__(self):
        self.folders = {}  # folder -> {file size: [(file to compare with, where it is/will be in output)]}

    def _index(self, folder: Path) -> dict:
        key = str(folder).lower()
        if key not in self.folders:
            index = {}
            if folder.is_dir():
                for path in folder.iterdir():
                    if path.is_file():
                        index.setdefault(path.stat().st_size, []).append((path, path))
            self.folders[key] = index
        return self.folders[key]

    def find(self, src: Path, folder: Path):
        """Where an identical file already is (or will be) in the output, or None."""
        for compare_with, location in self._index(folder).get(src.stat().st_size, []):
            if filecmp.cmp(src, compare_with, shallow=False):
                return location
        return None

    def add(self, folder: Path, size: int, compare_with: Path, location: Path):
        self._index(folder).setdefault(size, []).append((compare_with, location))


def free_name(wanted: Path, taken: set) -> Path:
    """`wanted`, or if that name is used, the same name with (2), (3), ... added."""
    candidate, number = wanted, 2
    # Windows treats "Song.mp3" and "song.mp3" as the same name, hence the lower().
    while candidate.exists() or str(candidate).lower() in taken:
        candidate = wanted.with_name(f"{wanted.stem} ({number}){wanted.suffix}")
        number += 1
    return candidate


def scan(input_dir: Path):
    """All songs in input_dir and its subfolders, plus a count of other files."""
    songs, ignored = [], Counter()
    for path in sorted(input_dir.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            songs.append(path)
        else:
            ignored[path.suffix.lower() or "(no extension)"] += 1
    return songs, ignored


def main():
    parser = argparse.ArgumentParser(description="Sort songs into Artist/Album folders using their tags.")
    parser.add_argument("--flat", action="store_true",
                        help="no folders, just rename to 'Artist - Title.mp3'")
    parser.add_argument("--move", action="store_true",
                        help="move files instead of copying them (the input folder gets emptied)")
    parser.add_argument("--dry-run", action="store_true",
                        help="only show what would happen, without copying or moving anything")
    parser.add_argument("-i", "--input", type=Path, default=INPUT_DIR,
                        help="folder to read songs from, including subfolders (default: the input folder)")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_DIR,
                        help="folder to sort songs into (default: the output folder)")
    args = parser.parse_args()

    args.input.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.output.resolve().is_relative_to(args.input.resolve()):
        sys.exit("Error: the output folder can't be inside the input folder.")

    print(f"Looking in: {args.input} (and its subfolders)")
    songs, ignored = scan(args.input)
    if ignored:
        kinds = ", ".join(f"{count} {ext}" for ext, count in ignored.most_common())
        print(f"  Ignoring {sum(ignored.values())} file(s) that aren't songs ({kinds})")
    if not songs:
        print("No songs found. Put them in that folder, then run this again.")
        return

    action = "move" if args.move else "copy"
    if args.dry_run:
        print("DRY RUN: nothing will be copied or moved, this only shows what would happen.")
    print(f"Found {len(songs)} song(s).\n")

    duplicate_finder = DuplicateFinder()
    taken_names = set()  # needed for --dry-run, where nothing is actually created
    artists = set()
    done = duplicates = untagged = failed = 0
    for src in songs:
        try:
            info = read_song_info(src)
            wanted = args.output / destination(src, info, args.flat)
            folder = wanted.parent

            existing = duplicate_finder.find(src, folder)
            if existing:
                shown = existing.relative_to(args.output).as_posix()
                print(f"  [duplicate] {src.name} (an identical file is already at {shown})")
                duplicates += 1
                continue

            dest = free_name(wanted, taken_names)
            size = src.stat().st_size
            note = ""
            if not (info["artist"] or info["albumartist"]):
                note = "  (no artist tag)"
                untagged += 1
            label = f"would {action}" if args.dry_run else ("moved" if args.move else "copied")
            print(f"  [{label}] {src.name} -> {dest.relative_to(args.output).as_posix()}{note}")
            if not args.dry_run:
                folder.mkdir(parents=True, exist_ok=True)
                if args.move:
                    shutil.move(str(src), str(dest))
                else:
                    shutil.copy2(src, dest)  # copy2 keeps the file's original dates
            taken_names.add(str(dest).lower())
            duplicate_finder.add(folder, size, src if args.dry_run else dest, dest)
            artists.add((info["albumartist"] or info["artist"] or UNKNOWN_ARTIST).lower())
            done += 1
        except Exception as error:
            print(f"  [fail] {src.name}: {error}")
            failed += 1

    past = "moved" if args.move else "copied"
    verb = f"would be {past}" if args.dry_run else past
    print(f"\nDone: {done} song(s) {verb}, {duplicates} duplicate(s) skipped, {failed} failed.")
    if not args.flat and done:
        print(f"{len(artists)} artist folder(s).")
    if untagged:
        where = "named after the file" if args.flat else f"in '{UNKNOWN_ARTIST}'"
        print(f"  Note: {untagged} song(s) had no artist tag, so they're {where}.\n"
              "  You can add tags with a free tag editor like Mp3tag (Windows) or MusicBrainz Picard.")
    if not args.dry_run:
        print(f"Organized songs are in: {args.output}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)
