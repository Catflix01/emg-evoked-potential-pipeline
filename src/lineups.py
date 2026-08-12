"""The channel lineups you can choose from.

A lineup says which muscle each channel of the recording holds, and which channels carry
the stimulus trigger. It describes how the amplifier was wired, so it is the same for
every participant and says nothing about anyone.

These were taken from lineups in real use, with every participant and date dropped: what
remains is a channel number and a muscle name. A made-up example would teach the wrong
shape, and there is no reason to invent one when the real arrangement carries no personal
information.

If none of these matches your setup, the tool can read one out of a spreadsheet or a saved
file, and it then behaves like any other entry in the list.

The lineups themselves live in lineups.json beside this file, as plain data. That is so the
pre-publish check can read them using nothing but the standard library, which lets it run
before anything is installed.
"""
import json
from pathlib import Path

PRESET_FILE = Path(__file__).with_name("lineups.json")


def read_preset_file(path=PRESET_FILE):
    """The presets as they sit in the file: names, and channel numbers as numbers."""
    stored = json.loads(Path(path).read_text())
    return stored["trigger_prefix"], {
        entry["name"]: {int(c): name for c, name in entry["channels"].items()}
        for entry in stored["lineups"]
    }


# Anything not starting with this is treated as a muscle.
TRIGGER_PREFIX, PRESETS = read_preset_file()

DEFAULT = next(iter(PRESETS))


def describe(lineup):
    """A one-line summary, for confirming a choice at a glance."""
    muscles = [n for n in lineup.values() if not n.startswith(TRIGGER_PREFIX)]
    triggers = sorted(n for n in lineup.values() if n.startswith(TRIGGER_PREFIX))
    return f"{len(muscles)} muscles on channels {min(lineup)}-{max(lineup)}, " \
           f"triggers: {', '.join(t.replace('trigger_', '') for t in triggers)}"


def as_rows(lineup):
    """The lineup laid out for display: one row per channel, in channel order."""
    return [{"channel": c, "what is on it": name,
             "kind": "stimulus trigger" if name.startswith(TRIGGER_PREFIX) else "muscle"}
            for c, name in sorted(lineup.items())]


def as_table(lineup):
    """The same rows as a table, for the apps to show."""
    import pandas as pd
    return pd.DataFrame(as_rows(lineup))


def from_workbook(path_or_buffer, sheet_name=0, participant=None, date=None):
    """Read a lineup out of a channel-list spreadsheet.

    Takes the first row, or the row for a given participant and date if both are given.
    Only the channel columns are read; nothing else in the sheet is kept.
    """
    import pandas as pd
    table = pd.read_excel(path_or_buffer, sheet_name=sheet_name)
    if participant is not None and date is not None:
        wanted = (table["Participant"] == participant) & (table["Date"] == date)
        table = table[wanted]
    if not len(table):
        raise ValueError("No row found in that spreadsheet")

    row = table.iloc[0]
    channels = [c for c in table.columns if isinstance(c, int)]
    return {c: str(row[c]).strip().strip("*") for c in channels if pd.notna(row[c])}


def from_json(path_or_text):
    """Read a lineup previously saved from this tool."""
    raw = (json.loads(Path(path_or_text).read_text())
           if isinstance(path_or_text, (str, Path)) and Path(path_or_text).exists()
           else json.loads(path_or_text))
    lineup = raw.get("channels", raw)
    return {int(c): str(name) for c, name in lineup.items()}


def to_json(lineup, name="my lineup"):
    """Save a lineup so it can be chosen again without setting it up twice."""
    return json.dumps({"name": name, "channels": {str(c): n for c, n in sorted(lineup.items())}},
                      indent=2)
