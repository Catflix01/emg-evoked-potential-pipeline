"""Check that nothing patient-related would be published.

    python src/check_before_publish.py

Run this before the first push to GitHub, and before any deploy. It looks at what git
would *actually* commit — not at what .gitignore is supposed to say — and refuses if it
finds subject codes, recordings, or the manifest.

Exits 0 when safe, 1 when not, so it can also be used as a pre-commit hook.

This file uses nothing but the standard library, on purpose. It is the one thing that has to
run on any machine before anything is installed, so it must never need pandas or anything
else. src/tests/test_publish_check.py holds that line.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A study participant code: P, digits, S, two digits. No trailing \b — in a filename the
# code is followed by an underscore, which counts as a word character, so a trailing
# boundary would miss the code-underscore-visit form, which is the one that matters most.
SUBJECT_CODE = re.compile(r"(?<![A-Za-z0-9])P\d+S\d{2}")

# A code together with a session date: identifies a person and when they were recorded.
# Never acceptable in the repository, not even in prose or a comment.
SUBJECT_WITH_DATE = re.compile(r"(?<![A-Za-z0-9])P\d+S\d{2}\w*[_\\/-]\d{8}")

# Codes invented for tests and the demo set. They follow the real shape on purpose, so
# the parsing is genuinely exercised, but they belong to nobody.
SYNTHETIC = re.compile(r"(?<![A-Za-z0-9])(P9S\d{2}|DEMO\w*)")

# Text files worth scanning. .m is included: the inherited MATLAB carries example paths.
SCANNED_SUFFIXES = {".csv", ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".m",
                    ".toml", ".cfg", ".ini", ".ipynb", ""}

MUST_BE_IGNORED = [
    "data/raw",
    "docs/Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx",
    "docs/Pharma-rundown.xlsx",
    "docs/Table-layout.csv",
    "outputs/master_results.csv",
    "outputs/master_results.parquet",
    "report.txt",
]

# No exceptions. The documentation explains the naming convention with a placeholder
# (P1Sxx), so nothing in the repository needs to name a real participant — and a check
# with no allowlist is one nobody can quietly widen.
ALLOWED_TO_MENTION = set()


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.splitlines()


def files_git_would_publish():
    """Everything tracked or untracked-but-not-ignored — i.e. what a `git add .` takes."""
    return [Path(p) for p in git("ls-files", "--cached", "--others", "--exclude-standard")]


def line(label, detail, ok):
    dots = "." * max(3, 52 - len(label))
    return f"  {label} {dots} {detail:<24}{'[OK]' if ok else '[PROBLEM]'}"


def main():
    report, problems = ["PRE-PUBLISH CHECK", ""], []
    publishable = files_git_would_publish()

    # 1. the named sensitive paths must all be excluded
    for target in MUST_BE_IGNORED:
        exists = (ROOT / target).exists()
        included = any(str(p).startswith(target) for p in publishable)
        if not exists:
            report.append(line(f"{target} (absent)", "nothing to leak", True))
        elif included:
            problems.append(f"{target} would be committed")
            report.append(line(target, "WOULD BE COMMITTED", False))
        else:
            report.append(line(target, "ignored", True))

    # 2. no publishable file may be a recording
    recordings = [p for p in publishable
                  if p.suffix == ".csv" and "_eventonly" in p.name]
    report.append(line("recordings among publishable files",
                       f"{len(recordings)} found", not recordings))
    problems += [f"{p} looks like a recording" for p in recordings]

    # 3. a subject code beside a session timestamp identifies a person and a moment.
    #    Never allowed anywhere, including in the prose files.
    def real_only(pattern, text):
        """Matches for real participants, ignoring the synthetic test and demo codes."""
        return [m.group() for m in pattern.finditer(text)
                if not SYNTHETIC.match(m.group())]

    timestamped, named = [], []
    for path in publishable:
        full = ROOT / path
        text = ""
        if full.suffix in SCANNED_SUFFIXES:
            try:
                text = full.read_text(errors="ignore")
            except OSError:
                text = ""
        haystack = f"{path.name}\n{text}"
        dated = real_only(SUBJECT_WITH_DATE, haystack)
        if dated:
            timestamped.append(f"{path} — {dated[0]}")
            continue
        # a bare code is lower risk, and the prose files need it to explain the convention
        if str(path) in ALLOWED_TO_MENTION:
            continue
        codes = real_only(SUBJECT_CODE, haystack)
        if codes:
            named.append(f"{path} — {codes[0]}")

    report.append(line("subject code beside a session date",
                       f"{len(timestamped)} found", not timestamped))
    report.append(line("publishable files naming a subject",
                       f"{len(named)} found", not named))
    problems += timestamped + named

    # 4. the shipped lineups must stay what they are: channel numbers and muscle names.
    #    They are publishable precisely because they carry nothing about a participant.
    #    Read straight out of the file rather than through src/lineups.py, so this check
    #    keeps needing nothing but Python and can run before anything is installed.
    try:
        stored = json.loads((ROOT / "src" / "lineups.json").read_text())
        leaked = []
        for entry in stored["lineups"]:
            text = f"{entry['name']} {entry['channels']}"
            leaked += [f"the lineup {entry['name']!r} contains {m}"
                       for m in real_only(SUBJECT_CODE, text) + real_only(SUBJECT_WITH_DATE, text)]
        report.append(line("shipped lineups carry no participant data",
                           f"{len(stored['lineups'])} checked", not leaked))
        problems += leaked
    except Exception as e:
        report.append(line("shipped lineups", f"could not check: {e}", False))
        problems.append(f"the lineups could not be checked: {e}")

    # 5. the demo recordings are excluded on purpose, so their absence is fine either way.
    #    What matters is that if any exist locally, none of them reached the commit.
    demo_committed = [p for p in publishable if str(p).startswith("data/")]
    report.append(line("data/ excluded from the commit",
                       f"{len(demo_committed)} files would go", not demo_committed))
    problems += [f"{p} is under data/ and would be committed" for p in demo_committed]

    report.append("")
    if problems:
        report.append("  NOT SAFE TO PUBLISH")
        report.append("")
        for problem in problems:
            report.append(f"    - {problem}")
        report.append("")
        report.append("  Add these to .gitignore, or remove them, then run this again.")
    else:
        report.append("  SAFE TO PUBLISH")

    print("\n".join(report))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
