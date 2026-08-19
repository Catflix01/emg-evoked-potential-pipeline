"""Build the published site.

    python web/build_site.py --out site

Assembles everything GitHub Pages serves: the landing page, the guides rendered from the
markdown in docs/, the 404 page, the app, and the search index. Running it locally builds
exactly what the workflow builds, so the site can be looked at before it is published.

The guides are generated rather than written twice. docs/*.md is what people read on
GitHub, and the site is a view of it — the same arrangement the pipeline uses for its
parquet and its CSV. Two hand-written copies would drift apart within a week.
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

REPOSITORY = "https://github.com/Catflix01/emg-evoked-potential-pipeline"
BASE = "/emg-evoked-potential-pipeline/"          # where GitHub Pages serves this from

# Which markdown becomes which page, and what each is for. Anything not listed stays off
# the site: docs/ also holds working notes that are not written for a visitor.
GUIDES = {
    "forPIs.md": ("Using the tool",
                  "Open it, choose your recordings, pick the channel list, and read the "
                  "table it produces."),
    "pipeline-notes.md": ("How it works",
                          "Why the pipeline does what it does: baseline, the measurement "
                          "windows, the output files, and the file shapes it reads."),
    "cusum-method.md": ("Response timing",
                        "How response onset, offset and EMG resumption are found with the "
                        "CUSUM method, and the papers behind it."),
}

# What the app needs beside it. The app is Python running in the visitor's browser, so its
# source has to be served like any other asset.
APP_PYTHON = ["src/harmonize.py", "src/cusum.py", "src/figures.py",
              "src/lineups.py", "src/lineups.json", "config/params.yaml"]


def last_updated():
    """The date of the last commit, so a page can say how current it is."""
    try:
        stamp = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cs"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return stamp or date.today().isoformat()
    except Exception:
        return date.today().isoformat()


def render_markdown(text):
    """Markdown to HTML. Needs the `markdown` package, which the site build installs."""
    try:
        import markdown
    except ImportError:
        sys.exit("The site build needs the markdown package:  pip install markdown")
    return markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])


def fill(template, **fields):
    for name, value in fields.items():
        template = template.replace("{{" + name + "}}", str(value))
    return template


def page(shell, content, *, title, description, root, updated):
    return fill(shell, content=content, title=title, description=description,
                root=root, repo=REPOSITORY, year=date.today().year, updated=updated)


def headings_for_search(markdown_text, url, page_title):
    """One search entry per heading: the heading, and the text underneath it.

    Searching whole documents would return every document for every common word. Searching
    sections lets a result point at the part that actually answers the question.
    """
    entries = []
    heading, body = page_title, []
    anchor = ""

    for line in markdown_text.splitlines():
        match = re.match(r"^(#{1,3})\s+(.*)", line)
        if match:
            if body:
                entries.append({"heading": heading, "page": page_title,
                                "url": url + anchor, "text": " ".join(body)[:600]})
            heading = re.sub(r"[`*_\[\]()]", "", match.group(2)).strip()
            # matches the id python-markdown's toc extension generates
            anchor = "#" + re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            body = []
        elif line.strip() and not line.startswith("```"):
            body.append(re.sub(r"[`*_>|]", "", line).strip())

    if body:
        entries.append({"heading": heading, "page": page_title,
                        "url": url + anchor, "text": " ".join(body)[:600]})
    return entries


def build(out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "guides").mkdir(parents=True)
    (out / "app").mkdir(parents=True)

    shell = (WEB / "templates" / "page.html").read_text()
    updated = last_updated()
    search = []

    # ---------------------------------------------------------------- the guides
    for source, (title, description) in GUIDES.items():
        markdown_text = (ROOT / "docs" / source).read_text()
        target = source.replace(".md", ".html")
        (out / "guides" / target).write_text(page(
            shell,
            f'<div class="wrap"><article class="prose">\n'
            f'{render_markdown(markdown_text)}\n</article></div>',
            title=title, description=description, root="../", updated=updated))
        search += headings_for_search(markdown_text, f"guides/{target}", title)

    # ---------------------------------------------------------------- landing and 404
    (out / "index.html").write_text(page(
        shell, fill((WEB / "pages" / "home.html").read_text(), repo=REPOSITORY, base=BASE),
        title="EMG evoked potentials",
        description="Measures every muscle's response to every stimulus pulse, and puts the "
                    "results in one table. Runs on your own computer; recordings are never "
                    "uploaded.",
        root="", updated=updated))

    # A 404 is served for any missing address, at any depth, so its links have to be
    # absolute — a relative one would resolve against a folder that does not exist.
    (out / "404.html").write_text(page(
        shell, fill((WEB / "pages" / "not-found.html").read_text(), base=BASE),
        title="Page not found",
        description="That page is not here. Links to the tool and the guides.",
        root=BASE, updated=updated))

    # ---------------------------------------------------------------- the app and assets
    shutil.copytree(WEB / "assets", out / "assets")
    shutil.copy(WEB / "app" / "index.html", out / "app" / "index.html")
    shutil.copy(WEB / "pi_app.py", out / "app" / "pi_app.py")
    for relative in APP_PYTHON:
        destination = out / "app" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, destination)

    (out / "search-index.json").write_text(json.dumps(search, indent=1))

    return out, len(search)


def main():
    parser = argparse.ArgumentParser(description="Build the published site.")
    parser.add_argument("--out", default="site", help="where to write it (default: site)")
    args = parser.parse_args()

    out, entries = build(args.out)
    pages = sorted(p.relative_to(out) for p in out.rglob("*.html"))
    print(f"built {len(pages)} pages into {out}/")
    for p in pages:
        print(f"   {p}")
    print(f"   search-index.json ({entries} sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
