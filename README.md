# EMG-Pipeline

SCI evoked-potential analysis. Reads raw EMG recordings and produces one tidy table:
a row per muscle per stimulus pulse, with peak-to-peak and area-under-curve measured
in a pre-stimulus window and a response window.

Raw data and the manifest are gitignored: they are human-subjects material.
`docs/legacy/` is the inherited MATLAB, kept for reference only.

## Nothing to install: use it in a browser

Open the published page, choose your recordings, and read the results. The Python runs
inside your own browser, so recordings are read from your machine and never sent anywhere.
Works on Windows and Mac, needs no terminal and no admin rights.

[**docs/for-the-pi.md**](docs/for-the-pi.md) is the one-page guide for anyone using it this
way. The link to the page itself appears once GitHub Pages is switched on for the
repository, under Settings, Pages.

Everything below is for running it from a terminal instead, which is faster and adds the
comparison and self-check tools.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running it

**Point-and-click**, pick a folder, adjust the windows, download the results:

```bash
streamlit run app.py
```

This opens in your browser and runs entirely on your own machine. Nothing is uploaded.

**Command line**, processes everything in `data/raw/` and writes to `outputs/`:

```bash
python src/harmonize.py
```

Both use the same code in `src/harmonize.py`, so they produce the same numbers.

## What you get

| file | precision | for |
|---|---|---|
| `outputs/master_results.parquet` | full | analysis: the source of truth |
| `outputs/master_results.csv` | 4 decimal places | opening in Excel |

The CSV is a view for reading. Anything doing real analysis should read the parquet,
which also keeps column types (dates stay dates) that a CSV round-trip would lose.

Figures: `python src/visuals.py` writes to `outputs/figures/`.

## What the columns mean

`docs/Table-layout.csv` is the agreed column layout. Each row records the measurement
windows it used, so the numbers are never ambiguous about where they came from.

## Checking it against your own data

```bash
python src/selfcheck.py                      # checks data/raw
python src/selfcheck.py --data <YOUR FOLDER> # checks anywhere else
```

Replace `<YOUR FOLDER>` with a real path, in Terminal you can type `--data ` and then drag
the folder in from Finder. Add `> report.txt` to save the output to a file.

Prints what the pipeline found, folder names, triggers, skipped files, and whether the
timing numbers land where physiology says they should. It holds counts, protocol names and
millisecond values; no EMG samples. It does print session folder names, which are subject
codes plus dates, so add `--anonymise` before sharing outside the lab. Also available as
the "Check my data" tab in the app.

Some columns are not yet verified against known-correct data, `selfcheck.py` says which,
and [docs/data-needed.md](docs/data-needed.md) lists what would settle them.

## Publishing it

See [docs/publishing.md](docs/publishing.md). In short: the app can be published as a public
demo carrying only synthetic recordings, while real analysis stays on lab machines. Run
`python src/check_before_publish.py` before any push: it refuses if a recording, the
manifest, or a subject code would be committed.

## Documentation

- **[docs/pipeline-notes.md](docs/pipeline-notes.md)**, why the code does what it does:
  what `baseline` is, which window each protocol uses, why dates are ISO, why there are
  two output files.
- **[docs/cusum-method.md](docs/cusum-method.md)**, how response onset, offset and EMG
  resumption are found, the stimulus artifact, and the papers behind it.
- **[docs/data-needed.md](docs/data-needed.md)**, what is still unverified and what would
  settle it.
- **[docs/publishing.md](docs/publishing.md)**, how to publish safely.

## Tests

```bash
python -m pytest
```

The suite pins known results from a real recording, so a change that alters any number
fails loudly. That is deliberate, most edits here should change nothing.
