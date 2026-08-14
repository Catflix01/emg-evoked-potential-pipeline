"""EMG pipeline, the version that runs in a web browser.

Everything here happens on the computer the page is open on. The Python runs inside the
browser itself, so recordings are read from the hard drive and never sent anywhere.

The measurements come from src/harmonize.py and the figures from src/figures.py, the same
code the command-line version uses, so the numbers are identical either way.
"""
import io
import sys
import zipfile
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

sys.path.append("src")
from harmonize import (process_file, find_recordings, READABLE_DECIMALS,
                       NOT_A_RECORDING)
import figures
import lineups

st.set_page_config(page_title="EMG pipeline", page_icon="⚡", layout="wide")

st.title("EMG pipeline")
st.markdown(
    "Measures every muscle's response to every stimulus pulse, and puts the results in "
    "one table you can download."
)
st.success(
    "**Your recordings stay on this computer.** This page runs entirely inside your web "
    "browser. Nothing is sent over the internet and nothing is stored anywhere else.",
    icon="🔒",
)
st.info(
    "**This page is for looking at a few recordings.** A browser can hold a few hundred "
    "megabytes, so a whole session or participant is too big for it. For those, use the "
    "downloadable version, which reads folders straight off your hard drive. Both give "
    "the same numbers.",
    icon="ℹ️",
)


@st.cache_data(show_spinner=False)
def load_config():
    return yaml.safe_load(open("config/params.yaml"))


def to_temp_file(uploaded):
    """Streamlit hands over the file's contents; process_file wants something on disk."""
    target = Path(tempfile.gettempdir()) / uploaded.name
    target.write_bytes(uploaded.getbuffer())
    return target


# --------------------------------------------------------------- step 1: the recordings
st.header("Step 1. Choose your recordings")

whole_folder, single_files = st.tabs(["A whole folder (recommended)", "A few files"])

with whole_folder:
    st.markdown(
        "Right-click the folder for one participant, or one session inside it, and choose "
        "**Compress** on a Mac or **Send to → Compressed (zipped) folder** on Windows. "
        "Then drop that single file here."
    )
    st.caption("This keeps the folder names, which is how the session and experiment "
               "columns get filled in. One participant or one session at a time: a whole "
               "study is too large to open in a browser.")
    zipped = st.file_uploader("Zipped folder", type="zip", label_visibility="collapsed")

with single_files:
    st.caption("Quicker for one or two recordings. The session and experiment columns come "
               "out blank this way, because a file picker does not pass on folder names.")
    chosen = st.file_uploader("Recordings", type="csv", accept_multiple_files=True,
                              label_visibility="collapsed")


@st.cache_data(show_spinner="Opening the folder…")
def unpack(zip_bytes, name):
    """Unpack a zipped folder and find the recordings inside it.

    Extracted to a real directory so the pipeline sees the folder structure exactly as it
    sits on the machine the zip came from. That structure is where the session and
    experiment columns come from.
    """
    target = Path(tempfile.mkdtemp(prefix="emg_")) / "folder"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        # a zip should not be able to write outside the folder it is extracted into
        safe = [m for m in archive.namelist()
                if not m.startswith("/") and ".." not in Path(m).parts]
        archive.extractall(target, members=safe)
    return target, find_recordings(target)


# A browser holds the uploaded bytes once, again unzipped, and again as numbers while
# measuring. Past roughly this much the tab stops responding, so it is better to say so
# than to let someone watch it die.
BROWSER_LIMIT_MB = 250

recordings, folder_root = [], None

if zipped is not None and zipped.size > BROWSER_LIMIT_MB * 1024 * 1024:
    st.error(
        f"That folder is **{zipped.size / 1024 / 1024 / 1024:.1f} GB**, which is more than "
        "a web browser can open.\n\n"
        "This page is for looking at a few recordings at a time. For whole sessions, "
        "participants or the entire study, use the downloadable version: it reads folders "
        "straight off your hard drive, so size stops mattering and nothing is copied.\n\n"
        "If you only want a look, zip one of the folders inside instead, such as a single "
        "stimulation type.",
        icon="📦")
    zipped = None

if zipped is not None:
    folder_root, recordings = unpack(zipped.getbuffer().tobytes(), zipped.name)
    if recordings:
        st.success(f"Found **{len(recordings)}** recordings in `{zipped.name}`")
        with st.expander("Show what was found"):
            st.write([str(f.relative_to(folder_root)) for f in recordings])
    else:
        st.warning(
            "No recordings found in that zip. It should hold the folders as they sit on "
            "your computer, with the `.csv` recordings somewhere below. Result folders "
            "such as `2.PROCESSED-DATA` are skipped on purpose."
        )
elif chosen:
    recordings = [f for f in chosen if NOT_A_RECORDING not in f.name]
    if len(recordings) < len(chosen):
        st.caption(f"Ignoring {len(chosen) - len(recordings)} file(s) that hold stimulus "
                   "intensities rather than EMG.")

@st.cache_resource(show_spinner="Getting ready to read spreadsheets…")
def spreadsheet_support():
    """Make sure .xlsx files can be read.

    Pyodide does not ship openpyxl, so it is fetched here rather than listed with the
    other packages. Listed there, a failure would stop the whole app from starting;
    here it is one feature that can report its own problem.
    """
    try:
        import openpyxl                                        # noqa: F401
        return True, None
    except ImportError:
        pass
    try:
        import micropip                                        # only exists in a browser
        import asyncio
        asyncio.get_event_loop().run_until_complete(micropip.install("openpyxl"))
        import openpyxl                                        # noqa: F401
        return True, None
    except Exception as e:
        return False, str(e)


# --------------------------------------------------------------- step 2: the lineup
st.header("Step 2. Choose the channel list")
st.caption("Which muscle each channel of the recording holds. Pick the one matching how "
           "your amplifier is wired.")

WORK_IT_OUT = "Work it out from my recordings"

choice = st.selectbox("Channel list",
                      [WORK_IT_OUT] + list(lineups.PRESETS) + ["My lineup is not here"],
                      label_visibility="collapsed")

lineup = None

if choice == WORK_IT_OUT and recordings:
    # Each recording says which channels carry stimulus pulses, so a list calling one of
    # them a muscle is provably wrong for this equipment.
    paths = [r for r in recordings if isinstance(r, Path)]
    if not paths:
        st.caption("Pick a zipped folder above to have this worked out, or choose a "
                   "list yourself.")
    else:
        fitting = lineups.that_fit(paths, load_config())
        if fitting:
            choice = fitting[0]
            st.success(f"**{choice}**", icon="✅")
            st.caption("Chosen because the channels carrying stimulus pulses in your "
                       "recordings match it. Pick one yourself if you would rather.")
        else:
            st.error("None of the built-in channel lists matches these recordings. "
                     "Choose **My lineup is not here** and supply your own.", icon="🔌")
elif choice == WORK_IT_OUT:
    st.caption("Choose your recordings above and this will work out which list fits.")

if choice in lineups.PRESETS:
    lineup = lineups.PRESETS[choice]
    st.caption(lineups.describe(lineup))
    with st.expander("Show the channels"):
        st.dataframe(lineups.as_table(lineup), width="stretch", hide_index=True)
elif choice != WORK_IT_OUT:
    st.caption("Choose your channel-list spreadsheet, or a lineup saved from this tool "
               "earlier. It is read here and not sent anywhere.")
    can_read_excel, excel_problem = spreadsheet_support()
    if not can_read_excel:
        st.caption(f"Spreadsheets cannot be read here ({excel_problem}), so save your "
                   "channel list as a .json from the desktop version, or pick a preset.")
    supplied = st.file_uploader("Your channel list",
                                type=(["xlsx", "xls", "json"] if can_read_excel else ["json"]),
                                label_visibility="collapsed")
    if supplied is not None:
        try:
            if supplied.name.lower().endswith(".json"):
                lineup = lineups.from_json(supplied.getvalue().decode())
            else:
                sheet = st.text_input("Sheet name", value="draft-pharma")
                lineup = lineups.from_workbook(io.BytesIO(supplied.getbuffer()), sheet)
            st.success(lineups.describe(lineup))
            st.dataframe(lineups.as_table(lineup), width="stretch", hide_index=True)
            st.download_button("Save this lineup for next time",
                               lineups.to_json(lineup, supplied.name),
                               "my-lineup.json", "application/json")
        except Exception as e:
            st.error(f"Could not read that channel list: {e}")

# --------------------------------------------------------------- step 3: run it
st.header("Step 3. Measure")

if not recordings or lineup is None:
    st.info("Choose your recordings and a channel list above, then this button will work.")
    st.stop()

if st.button(f"Measure {len(recordings)} recording(s)", type="primary"):
    config = load_config()
    progress = st.progress(0.0, text="Starting")
    tables, skipped = [], []
    for i, item in enumerate(recordings, start=1):
        # from a zip these are already paths on disk, with their folders intact; from the
        # file picker they are uploads that have to be written out first
        path = item if isinstance(item, Path) else to_temp_file(item)
        label = str(path.relative_to(folder_root)) if folder_root else path.name
        progress.progress(i / len(recordings), text=f"{label} ({i} of {len(recordings)})")
        try:
            tables.append(process_file(path, None, config, lineup=lineup))
        except Exception as e:
            skipped.append({"file": label, "reason": str(e)})
    progress.empty()

    if not tables:
        st.error("None of the recordings could be measured.")
        st.dataframe(pd.DataFrame(skipped), width="stretch")
        st.stop()

    results = pd.concat(tables, ignore_index=True)
    results["protocol"] = (results["protocol_1"] + "_"
                           + results["protocol_2"].fillna("")).str.rstrip("_")
    st.session_state["results"] = results
    st.session_state["skipped"] = pd.DataFrame(skipped)

# --------------------------------------------------------------- results
if "results" not in st.session_state:
    st.stop()

results = st.session_state["results"]
skipped = st.session_state["skipped"]

st.header("Results")
left, middle, right = st.columns(3)
left.metric("Measurements", f"{len(results):,}")
middle.metric("Muscles", results.muscle.nunique())
right.metric("Recordings skipped", len(skipped))

if len(skipped):
    with st.expander(f"{len(skipped)} recording(s) could not be measured, and why"):
        st.dataframe(skipped, width="stretch")

st.subheader("The table")
st.caption(f"One row per muscle per stimulus pulse, rounded to {READABLE_DECIMALS} decimal "
           "places for reading. The download has the same numbers.")
st.dataframe(results.round(READABLE_DECIMALS), width="stretch", height=380)

st.download_button(
    "Download this table as a spreadsheet (.csv)",
    results.round(READABLE_DECIMALS).to_csv(index=False),
    "emg_results.csv", "text/csv", type="primary",
)

st.subheader("The figures")
st.caption("Four views, each answering one question about whether the numbers make sense.")

first, second = st.columns(2)
with first:
    st.markdown("**Which muscles responded?**")
    st.pyplot(figures.response_by_muscle(results, "auc"), clear_figure=True)
with second:
    st.markdown("**Did each protocol do what it should?**")
    heatmap, _ = figures.muscle_by_protocol(results, "auc")
    st.pyplot(heatmap, clear_figure=True)

st.markdown("**Do the two measurements agree with each other?**")
st.caption("They measure different things, so they should rise together without lying on a "
           "straight line.")
st.pyplot(figures.pk_pk_against_auc(results), clear_figure=True)

with st.expander("What the columns mean, and two things this browser version cannot do"):
    st.markdown(
        """
**The measurements**

- `pk_pk` is the peak-to-peak size of the response, the distance from its lowest point to
  its highest.
- `auc` is the area under the response once the resting level has been subtracted.
- `prestim_pk_pk` and `prestim_auc` are the same two measured just *before* the stimulus,
  so you can see how quiet the muscle was to begin with.
- `baseline` is where the channel was resting. A large or drifting value usually means a
  bad electrode.
- Each row records the measurement windows it used, so no number is ambiguous about where
  it came from.

**Two limitations of this browser version**

- The `session` and `experiment` columns come out blank. They are read from the names of
  the folders the recordings sit in, and a web browser hands over files without folders.
- The download is a .csv. The command-line version also writes a full-precision file that
  the browser cannot produce.
        """
    )
