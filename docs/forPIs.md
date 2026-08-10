# Measuring EMG recordings: how to use it

This turns raw EMG recordings into one organised table, with a row for every muscle and
every stimulus pulse. You can look at the results on screen and download them as a
spreadsheet.

There are two ways to run it, and which you want depends on how much data you have.

| | what it is for | how you get it |
|---|---|---|
| **The download** | whole sessions, participants, the entire study | one file from the project's Releases page, then double-click |
| **The web page** | a quick look at a handful of recordings | open a link, nothing to install |

They run the same code and give the same numbers.

**Sessions are large.** One is close to a gigabyte, which is far more than a web browser can
hold. So for real work use the download: it reads recordings straight off your hard drive
rather than loading them into a browser, and size stops being a problem. The web page is for
when you want to glance at a few files without installing anything.

---

## Your recordings stay on your computer

The page runs on your own machine, inside your web browser. When you choose your files,
they are read by your browser and measured there. They are not sent over the internet,
not stored on any server, and not visible to anyone else.

This is true even though it looks like a website: the software is downloaded to your
browser, and your data never travels the other way.

---

## Using it

**1. Open the link.**

The first time, give it about half a minute. Your browser is downloading the software.
After that it starts quickly.

**2. Choose your recordings.**

The easiest way is to give it a whole folder. Find the folder for one participant, or for
one session inside it. Right-click it and choose **Send to → Compressed (zipped) folder**
on Windows, or **Compress** on a Mac. That makes a single `.zip` file next to the original.
Drop that one file into the box.

Do one participant, or one session, at a time. A whole study is far too large to open in a
browser.

If you only want one or two recordings, the *A few files* tab lets you pick the `.csv`
files directly instead.

**3. Choose the channel list.**

This says which muscle each channel of the recording holds. Pick the one matching how your
amplifier is wired from the dropdown; the summary underneath tells you how many muscles it
covers and which channels carry the stimulus.

If none of them matches, choose **My lineup is not here** and give it your channel-list
spreadsheet once. It will offer to save that as a small file you can load in one click next
time.

**4. Click Measure.**

A progress bar shows how far along it is.

---

## What you get

**A table.** One row per muscle per stimulus pulse. The columns:

| column | what it is |
|---|---|
| `pk_pk` | the size of the response, lowest point to highest |
| `auc` | the area under the response, after the resting level is subtracted |
| `prestim_pk_pk`, `prestim_auc` | the same two, measured just *before* the stimulus, so you can see how quiet the muscle was |
| `baseline` | where the channel was sitting at rest; a large or drifting value usually means a bad electrode |
| `response_window`, `prestim_window` | which stretch of the recording each number came from |

**Four figures**, each answering one question: which muscles responded, whether each
protocol did what it should, and whether the two measurements agree with each other.

**A download button** that saves the table as a `.csv` you can open in Excel.

---

## If something does not work

**A recording is listed as skipped.** Open the "could not be measured" section. It gives
the reason for each one. The most common are that the channel list has no entry for that
participant and date, or that no stimulus was detected in the file.

**Two columns are empty.** `session` and `experiment` come from the names of the folders
your recordings sit in. If you used the *A few files* tab they will be blank, because a
file picker hands over files without their folders. Giving it a zipped folder instead fills
them in.

**The numbers look wrong.** Check the figure showing one recorded response with the
measurement windows shaded on it. If the green window is not sitting over the response,
the windows need adjusting, and every number in the table would be measuring the wrong
stretch of signal.

---

## What is measured, and what is still being checked

Peak-to-peak and area-under-curve are the established measurements, checked against known
values on every change to the software, and peak-to-peak agrees exactly with the previous
MATLAB analysis.

Response timing (`response_onset`, `response_offset`, `emg_resuming`) is newer and has not
yet been checked against traces scored by hand. Treat those columns as provisional. The
same goes for `is_active`, which guesses whether a muscle was contracting.

If you want to know exactly what is settled and what is not, ask whoever maintains this
tool; the list is kept alongside the code.
