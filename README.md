# EMG-Pipeline

SCI evoked-potential analysis. Reads raw EMG recordings and produces one tidy table:
a row per muscle per stimulus pulse, with peak-to-peak and area-under-curve measured
in a pre-stimulus window and a response window.

Recordings and the channel-lineup workbook are never part of this repository: they are
human-subjects material. Everything here runs on data you supply.

## The site

**<https://catflix01.github.io/emg-evoked-potential-pipeline/>** — what the tool is, the
downloads, the guides, and the browser version itself at `/app/`.

## Three ways to run it without a terminal

**The Windows download** and **the Mac download**, for real work. Both read folders straight
off the disk, so a whole session, participant or study is no problem. Take them from the
[Releases](https://github.com/Catflix01/emg-evoked-potential-pipeline/releases) page, which
needs no GitHub account. Every push also builds them, and those builds are under the
Actions tab for anyone signed in.

Both are unsigned, so the first time you open one your computer will warn you: on Windows,
More info then Run anyway; on a Mac, System Settings → Privacy & Security → Open Anyway.
The Windows executable is built and started automatically on every change, but **has not
yet been opened on a real Windows desktop by anyone.**

**The browser version**, for a quick look at a few recordings, with nothing installed. The
Python runs inside your own browser, so nothing is uploaded, but a browser can only hold a
few hundred megabytes, which is less than one session here.

All three run the same pipeline and give the same numbers.

[**docs/forPIs.md**](docs/forPIs.md) is the one-page guide for anyone using it this way.

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
python main.py
```

This opens in your browser and runs entirely on your own machine. Nothing is uploaded.

**Command line**, processes everything in `data/raw/` and writes to `outputs/`:

```bash
python main.py process
```

Both use the same code in `src/harmonize.py`, so they produce the same numbers.

## What you get

| file | precision | for |
|---|---|---|
| `outputs/master_results.parquet` | full | analysis: the source of truth |
| `outputs/master_results.csv` | 4 decimal places | opening in Excel |

The CSV is a view for reading. Anything doing real analysis should read the parquet,
which also keeps column types (dates stay dates) that a CSV round-trip would lose.

Figures: `python main.py figures` writes to `outputs/figures/`.

## What the columns mean

`docs/Table-layout.csv` is the agreed column layout. Each row records the measurement
windows it used, so the numbers are never ambiguous about where they came from.

## Checking it against your own data

```bash
python main.py check                       # checks the configured folder
python main.py check --data <YOUR FOLDER> # checks anywhere else
```

Replace `<YOUR FOLDER>` with a real path, in Terminal you can type `--data ` and then drag
the folder in from Finder. Add `> report.txt` to save the output to a file.

Prints what the pipeline found, folder names, triggers, skipped files, and whether the
timing numbers land where physiology says they should. It holds counts, protocol names and
millisecond values; no EMG samples. It does print session folder names, which are subject
codes plus dates, so add `--anonymise` before sharing outside the lab. Also available as
the "Check my data" tab in the app.

Some columns are not yet verified against known-correct data. `python main.py check` says
which, every time it runs.

## Checking that every recording can even be read

A recording whose filename the pipeline cannot parse is skipped quietly. To ask, for a
whole study at once, without opening any of the recordings:

```bash
python main.py survey --data <YOUR FOLDER>
```

It reports how many names can be read and groups the rest by shape. This is worth running
against a new study before trusting any results from it: it is how 920 recruitment
recordings, 71% of one study, turned out to be going missing without any error appearing.

## Publishing it

The browser version is published as a page anyone can open, and it asks each visitor for
their own recordings; no data of any kind travels with it. Run `python main.py
safe-to-publish` before any push. It refuses if a recording, the manifest, or a participant
code would be committed, and the same check runs again on GitHub for every push.

The site is built from this repository:

```bash
pip install markdown
python web/build_site.py --out site     # landing page, guides, 404, the app
python web/check_site.py --site site    # every link resolves, nothing left unfilled
```

The guides under `/guides/` are generated from `docs/*.md`, so the markdown stays the one
place they are written. `markdown` is not in `requirements.txt` on purpose: it is needed
only to build the site and should never end up inside the desktop downloads.

## Documentation

- **[docs/pipeline-notes.md](docs/pipeline-notes.md)**, why the code does what it does:
  what `baseline` is, which window each protocol uses, why dates are ISO, why there are
  two output files.
- **[docs/cusum-method.md](docs/cusum-method.md)**, how response onset, offset and EMG
  resumption are found, the stimulus artifact, and the papers behind it.
- **[docs/forPIs.md](docs/forPIs.md)**, how to use the browser version: open the link,
  choose your files, read the table, download the results.

## Tests

The suite is maintained alongside the code but is **not published in this repository yet**.
It pins known results from a real recording, so a change that alters any number fails
loudly, which is deliberate: most edits here should change nothing.

If you have it locally:

```bash
python -m pytest
```

To publish it, delete the TESTS block in `.gitignore`. Worth doing when this repository
goes to other labs, since the suite is what makes the numbers checkable by someone else
rather than taken on trust.
