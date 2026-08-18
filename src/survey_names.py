"""Can every recording in a folder even be read?

    python main.py survey --data <folder>

Measuring is checked against five recordings kept beside the code. Those five are all one
participant and all conventionally named, so they said nothing about the other shapes a
real study contains — and 71% of one turned out to be unreadable without anyone noticing,
because a file that cannot be parsed is skipped rather than shouted about.

This reads only the names. It opens no recordings, so it is quick on a whole study, and it
prints counts and shapes rather than filenames, so the output can be shared.
"""
import argparse
import collections
import re
import sys
from pathlib import Path

from harmonize import find_recordings, parse_filename


def shape_of(stem):
    """A filename with the details removed, so like-named files group together."""
    shape = re.sub(r"\d{8}-\d{2}-\d{2}-\d{2}", "<timestamp>", stem)
    shape = re.sub(r"\d+", "N", shape)
    pieces = shape.split("_")
    # the first three are subject, visit and target; what varies is the rest
    return "_".join(pieces[3:]) if len(pieces) > 3 else shape


def survey(folder):
    """Every recording under a folder: how many can be read, and what the rest look like."""
    recordings = find_recordings(folder)
    readable, unreadable = 0, []
    for recording in recordings:
        try:
            parse_filename(recording)
            readable += 1
        except ValueError as e:
            unreadable.append((shape_of(recording.stem), str(e).split(":", 1)[-1].strip()))
    return recordings, readable, unreadable


def report(folder):
    recordings, readable, unreadable = survey(folder)
    lines = ["FILENAME SURVEY",
             f"  {len(recordings)} recordings under {folder}",
             f"  {readable} can be read",
             f"  {len(unreadable)} cannot"]

    if unreadable:
        lines += ["", "  the shapes that cannot be read, most common first:"]
        for (shape, reason), count in collections.Counter(unreadable).most_common(15):
            lines.append(f"    {count:5}  {shape}")
            lines.append(f"           {reason}")
        lines += ["",
                  "  Each of these is skipped rather than measured. If they hold real",
                  "  recordings, that is data going missing quietly."]
    else:
        lines += ["", "  Every recording can be read."]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check every recording's name can be read.")
    parser.add_argument("--data", required=True, help="folder of recordings; searched right down")
    args = parser.parse_args()

    folder = Path(args.data).expanduser()
    if not folder.exists():
        print(f"No such folder: {folder}")
        return 1
    print(report(folder))
    return 0


if __name__ == "__main__":
    sys.exit(main())
