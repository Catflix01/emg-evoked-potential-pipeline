"""EMG pipeline, the version that runs in a web browser.

Everything here happens on the computer the page is open on. The Python runs inside the
browser itself, so recordings are read from the hard drive and never sent anywhere.

The measurements come from src/harmonize.py and the figures from src/figures.py, the same
code the command-line version uses, so the numbers are identical either way.
"""
import io
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

sys.path.append("src")
from harmonize import process_file, READABLE_DECIMALS, NOT_A_RECORDING
import figures

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
st.caption("The .csv files from the recording system. You can pick several at once.")
chosen = st.file_uploader(
    "Recordings", type="csv", accept_multiple_files=True, label_visibility="collapsed"
)
recordings = [f for f in (chosen or []) if NOT_A_RECORDING not in f.name]
if chosen and len(recordings) < len(chosen):
    st.caption(f"Ignoring {len(chosen) - len(recordings)} file(s) that hold stimulus "
               "intensities rather than EMG.")

# --------------------------------------------------------------- step 2: the lineup
st.header("Step 2. Choose the channel list")
st.caption("The spreadsheet saying which muscle was recorded on which channel. "
           "A .csv with the same columns works too.")

can_read_excel, excel_problem = spreadsheet_support()
if not can_read_excel:
    st.warning(
        "Spreadsheet (.xlsx) support could not be loaded, so please save your channel "
        f"list as a .csv and choose that instead. Technical detail: {excel_problem}",
        icon="⚠️")

manifest_types = (["xlsx", "xls", "csv"] if can_read_excel else ["csv"])
manifest_file = st.file_uploader(
    "Channel list", type=manifest_types, label_visibility="collapsed"
)
sheet = st.text_input("Sheet name inside that spreadsheet", value="draft-pharma",
                      disabled=not can_read_excel,
                      help="Ignored for a .csv, which has only one sheet.")

# --------------------------------------------------------------- step 3: run it
st.header("Step 3. Measure")

if not recordings or manifest_file is None:
    st.info("Choose your recordings and the channel list above, then this button will work.")
    st.stop()

if st.button(f"Measure {len(recordings)} recording(s)", type="primary"):
    try:
        raw = io.BytesIO(manifest_file.getbuffer())
        if manifest_file.name.lower().endswith(".csv"):
            manifest = pd.read_csv(raw)
        else:
            manifest = pd.read_excel(raw, sheet_name=sheet)
    except Exception as e:
        st.error(f"Could not read the channel list: {e}")
        st.stop()

    config = load_config()
    progress = st.progress(0.0, text="Starting")
    tables, skipped = [], []
    for i, uploaded in enumerate(recordings, start=1):
        progress.progress(i / len(recordings), text=f"{uploaded.name} ({i} of {len(recordings)})")
        try:
            tables.append(process_file(to_temp_file(uploaded), manifest, config))
        except Exception as e:
            skipped.append({"file": uploaded.name, "reason": str(e)})
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
