# EMG-Pipeline

**A research tool for standardized analysis of surface EMG responses to non-invasive brain, spinal, and peripheral nerve stimulation, with support for voluntary force and strength-task data.**

EMG-pipeline reads raw surface EMG recordings and produces a standardized, tidy dataset with measurements for each muscle and stimulus channel.

The pipeline is designed to support EMG analysis during: 
- Brain stimulation (TMS)
- Spinal stimulation (TSS)
- Peripheral nerve stimulation (PNS)
- Resting or light voluntary muscle contraction during stimulation
- Voluntary strength (STR) tasks, including tip-to-tip (TIP) pinch, pad-to-pad (PLP) pinch, lateral key (KEY) pinch, hand grip (GSP), and wrist (WRT) flexion/extension

For evoked motor responses, the pipeline can measure peak-to-peak amplitude, area-under-curve (AUC), response onset and offset, EMG resumption, and other response characteristics within defined pre-stimulus (background EMG) and response windows.

Force generated during voluntary strength tasks is treated separately from evoked EMG responses. Force-channel analysis and automated classification of active versus resting conditions are under development and require further validation. 

The goal is to make EMG analysis reproducible, standardized, and scalable across participants, sessions, protocols, and studies, while allowing the pipeline to accommodate different laboratory data structures and naming conventions.

Recordings and channel configuration information are never part of this repository: they are human-subjects material and/or laboratory-specific metadata. Everything here runs on data you supply.


## The site

**<https://catflix01.github.io/emg-evoked-potential-pipeline/>** — the landing page, documentation, guides, downloads, and browser-based application `/app/`.


## Three ways to run it without a terminal

**Windows and Mac downloads** - recommended for research use

**Windows** and **Mac** downloads, for real work. The Windows and Mac desktop versions are intended for real-world analysis. Both can read folders straight
off your computer, so you can process individual recordings, sessions, participants, or larger study datasets. 

Download the latest versions from the release page
[Releases](https://github.com/Catflix01/emg-evoked-potential-pipeline/releases). A GitHub account is not required to download them. Every push also builds them, and those builds are under the Actions tab for anyone signed in.

Both versions use the same underlying analysis pipeline and are intended to produce the same results. 

The applications are currently unsigned, so your operating system may display a security warning the first time you open one. Your computer will warn you: 
- Windows: **More info → Run anyway**
- Mac: **System Settings → Privacy & Security → Open Anyway**

The Windows executable is automatically built with every change, but **has not
yet been independently tested on a real Windows desktop (yet).**


**Browser version** - quick analysis and demonstration

**The browser version**, allow you to run the pipeline without installing anything. The Python code runs inside your browser, so your recordings are not uploaded to a server. However, browser memory limits mean that it is intended for smaller datasets (a
few hundred megabytes), or a limited number of recordings rather than an entire session or study.

The browser, Windows, and Mac versions use the same underlying analysis pipeline and are intended to produce the same results.

[**docs/forPIs.md**](docs/forPIs.md) is the one-page guide for anyone using the application without a terminal.


**Data organization and naming conventions**

The EMG-pipeline uses metadata contained in folder and file names to identify and organize recordings. The current laboratory naming convention follows a structure format such as:

'P1S01_V1T0_RFDI_TMS_REC_09032026-13-21-41.csv'

In this example, the filename encodes information such as:

**| Component | Example | Meaning |**
|---|---|---|
| Study code | 'P1' | Study-level identifier |
| Group code | 'S' | Group-level identifier |
| Subject ID | '01' | Participant identifier |
| Visit | 'V'# | Visit number |
| Timepoint | 'T'# | Timepoint |
| Side | 'R' | Side of body |
| Muscle | 'FDI' | Muscle abbreviation |
| Stimulation | 'TMS' | Stimulation type |
| Protocol | 'REC' | Recording/protocol type |
| Date | '09032026' | Date (MMDDYYYY) |
| Timestamp | '13-21-41' | Recording timestamp |

The exact positions and meanings above reflect our current laboratory naming convention and should not be assumed to be universal. 


**TBA.** **Making the pipeline portable across laboratories**

**TBA.** Ideally, the pipeline should allow users to provide their own channel configuration reference so that the same analysis code can accommodate different EMG systems, channel assignments, and historical configurations.   


## Setup

Everything below describes running the pipeline from a terminal. This is primarily useful for developers, advanced users, batch processing, validation, and additional comparison and self-check tools.

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

This opens in your browser and runs entirely on your own machine. No EMG recordings are uploaded.

**Command line**

Processes everything in `data/raw/` and writes results to `outputs/`:

```bash
python main.py process
```

Both interfaces use the same code in `src/harmonize.py`, so they produce the same numbers.

## What you get

| file | precision | for |
|---|---|---|
| `outputs/master_results.parquet` | full | analysis: the source of truth |
| `outputs/master_results.csv` | 4 decimal places | opening in Excel |

The CSV is a view for reading. Anything doing real analysis should read the parquet,
which also perserves column types (dates stay dates) that a CSV round-trip would lose.

Figures can be generated with: 

`python main.py figures` 

which writes to `outputs/figures/`.

## What the columns mean

`docs/Table-layout.csv` contains the agreed column layout. 

Each row records the measurement windows and parameters used to generate the measurements, so that the resulting values remain traceable to the analysis conditions.

## Checking it against your own data

```bash
python main.py check                       # checks the configured folder
python main.py check --data <YOUR FOLDER> # checks anywhere else
```

Replace `<YOUR FOLDER>` with a real path. In Terminal you can type `--data ` and then drag the folder in from Finder. 

Add `> report.txt` to save the output to a file.

The check reports folder structure, protocol names, triggers, skipped recordings, and timing values. It holds counts, protocol names, microvolt and millisecond values; it does not include EMG samples. 

It does print session folder names, which can contain subject codes and dates, so add `--anonymise` before sharing outside the lab.

The same functionality is available in the "Check my data" tab in the application. 

Some output columns have not yet been verified against known-correct data. `python main.py check` identifies these columns each time it runs.

## Checking that every recording can even be read

A recording whose filename the pipeline cannot parse is skipped. To check an entire study before processing the recordings:

```bash
python main.py survey --data <YOUR FOLDER>
```

It reports how many filenames can be read and groups the remaining files by filename pattern. 

This is recommended when processing a new study or a new laboratory naming convention. It can identify recordings that would otherwise be excluded from analysis. It is how 920 recruitment recordings, 71% of one study, turned out to be going missing without any error appearing.

## Publishing it

The browser version is published as a page anyone can open. Each user supplied their own recordings; no recordings or human-subject data are included with the published site. 

Run: 

`python main.py
safe-to-publish` 

before any push. 

It refuses if a recording, manifest, or a participant code would be committed. The same check runs again on GitHub for every push.

The site is built from this repository:

```bash
pip install markdown
python web/build_site.py --out site     # landing page, guides, 404, the app
python web/check_site.py --site site    # every link resolves, nothing left unfilled
```

The guides under `/guides/` are generated from `docs/*.md`, so the markdown remains the single source for the documentation. 

`markdown` is not in `requirements.txt` on purpose: it is needed only to build the site and should never end up inside the desktop downloads.

## Documentation

- **[docs/pipeline-notes.md](docs/pipeline-notes.md)**, explains why the code does what it does, including baseline definitions, analysis windows, date formatting, and output files.
- **[docs/cusum-method.md](docs/cusum-method.md)**, describes how response onset, response offset, and EMG resumption are determined, how the stimulus artifact is handled, and the supporting literature.
- **[docs/forPIs.md](docs/forPIs.md)**, is a one-page guide for investigators: open the application, select recordings, review the results, and download the output.

## Tests

The test suite is maintained alongside the code but is **not yet published in this repository**.

It pins known results from a real recording, so a change that alters any number fails
loudly. This is deliberate. Changes to the analysis code should not alter validated results unexpectedly.

If you have the test suite locally:

```bash
python -m pytest
```

To publish it, delete the TESTS block in `.gitignore`. 

Publishing the test suite would allow other laboratories to independently verify that changes to the pipeline do not alter established results. 


## Licence

The code is under the [MIT licence](LICENSE): use it, change it, build on it, in a lab or in a product, as long as the copyright notice comes along.

**The licence covers the code and nothing else.** Recordings, the channel-lineup workbook,
and any results computed from patient data are human-subjects material. They are not in
this repository, they are not distributed with it, and no permission to use them is granted here. 

Whether a given recording may be shared at all is an IRB, data-use, and institutional question, not a software licensing question.
