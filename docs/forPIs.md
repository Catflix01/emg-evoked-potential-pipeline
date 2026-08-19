# Measuring EMG recordings: how to use it

This turns raw EMG recordings into one organised table, with a row for every muscle and
every stimulus pulse. You can look at the results on screen and download them as a
spreadsheet.

There are three ways to run it, and which you want depends on how much data you have.

| | what it is for | how you get it |
|---|---|---|
| **The Windows download** | whole sessions, participants, the entire study | one file from the project's Releases page, then double-click. No account needed |
| **The Mac download** | the same, on a Mac | a `.zip` from the same page; unzip it and open the app inside |
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

## Using the download

**1. Get it and open it.**

From the Releases page, take `EMG-Pipeline.exe` on Windows or `EMG-Pipeline-Mac.zip` on a
Mac. There is nothing to install: double-click it and it opens in your web browser, which
is only how it draws its screen. Everything runs on your own machine.

The first time, your computer will refuse to open it, because the program does not carry a
paid signing certificate. Nothing is wrong with it: your computer simply has no way to
check who made it. Telling it you trust the program is a one-off, and the steps differ by
system.

**On Windows:** click **More info**, then **Run anyway**.

**On a Mac**, unzip the file, then:

1. Double-click the app. macOS says it cannot verify the app is free of malware. Click
   **Done**.
2. Open **System Settings**, then **Privacy & Security**.
3. Scroll down to **Security**. There is a line saying the app was blocked, with an
   **Open Anyway** button. Click it.
4. Confirm with your fingerprint or password, then click **Open Anyway** once more.

Do steps 2 to 4 shortly after step 1, because that button only appears for a while after
the app was blocked. If you find older instructions saying to right-click the app and
choose Open, that stopped working in macOS 15; the steps above are the current way.

**2. Point it at your recordings.**

Click **Browse for a folder…** and choose the folder holding them: a session, a
participant, or the whole store. Everything below it is searched, so you can give it the
top folder and leave it. Nothing is copied or uploaded; the files are read where they sit,
which is why size does not matter here.

The chooser is a separate window, so it can open *behind* the browser. If nothing seems to
happen, look for it in your Dock or task bar. Clicking Cancel simply changes nothing.

You can also paste a folder's path straight into the box underneath, which is quicker if
you already have it copied.

**3. Choose the channel list**, exactly as described below, then click **Process
recordings**.

You also get two extra tabs: **Check my data**, which reports what it found without
measuring anything, and **Compare with the old pipeline**, which measures every recording
both the old MATLAB way and the new way so the two can be compared.

---

## Using the web page

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
| `stimulus_intensity` | for recruitment recordings, how hard the stimulator was driven; blank for everything else |
| `response_window`, `prestim_window` | which stretch of the recording each number came from |

**Four figures**, each answering one question: which muscles responded, whether each
protocol did what it should, and whether the two measurements agree with each other.

**A download button** that saves the table as a `.csv` you can open in Excel.

---

## If something does not work

**Nothing happens when you open it.** It is almost certainly already running. A computer
will not start a second copy of a program that is already open, so the second double-click
does nothing you can see. Open **http://localhost:8501** in your browser and it will be
there. To start it fresh instead, quit it first: right-click its icon in the Dock or task
bar and choose Quit.

**A recording is listed as skipped.** Open the "could not be measured" section. It gives
the reason for each one. The most common are that the channel list has no entry for that
participant and date, or that no stimulus was detected in the file.

**Are any recordings being skipped before they are even measured?** A recording whose name
cannot be read is passed over, which is quiet by design and easy to miss. To check a whole
study at once, without opening any of the recordings:

```bash
python main.py survey --data <your folder>
```

It prints how many names can be read, and groups the ones that cannot by shape.

**Two columns are empty.** `session` and `experiment` come from the names of the folders
your recordings sit in. On the web page's *A few files* tab they will be blank, because a
file picker hands over files without their folders. Giving it a zipped folder instead fills
them in, and the download always has them because it reads the folders directly.

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
