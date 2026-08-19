"""Check a built site before it is published.

    python web/check_site.py --site site

Three questions, all of which have caught a real fault here before:

  1. Does every link and asset the pages ask for actually exist? A stylesheet added to the
     page but not to the build publishes a bare document; a module the app imports but that
     is never copied publishes a page that fails on its first line.
  2. Is any template placeholder still showing? An unfilled {{...}} means a page is telling
     visitors about the machinery.
  3. Does the app still have every Python file it imports?

Exits non-zero on a problem, so the workflow refuses to deploy rather than publishing it.
"""
import argparse
import re
import sys
from pathlib import Path

# Links out to other sites are not this build's business, and checking them would make the
# deploy depend on somebody else's server being up.
EXTERNAL = re.compile(r"^(https?:|mailto:|tel:|#|data:)")


def links_in(page):
    """Every local address a page asks for: stylesheets, scripts, images, links."""
    html = page.read_text()
    found = re.findall(r'(?:href|src)="([^"]+)"', html)
    return [a for a in found if not EXTERNAL.match(a)]


def resolve(site, page, address):
    """Where a link points, as a path on disk."""
    address = address.split("#")[0].split("?")[0]
    if not address:
        return None
    # an absolute address is relative to the site root, not the filesystem root
    if address.startswith("/"):
        target = site / address.lstrip("/").split("/", 1)[-1] if address.count("/") > 1 \
                 else site
        # /<repo>/thing  ->  site/thing
        parts = [p for p in address.strip("/").split("/")][1:]
        target = site.joinpath(*parts) if parts else site
    else:
        target = (page.parent / address).resolve()
    if target.is_dir() or str(target).endswith("/"):
        target = target / "index.html"
    return target


def check(site):
    site = Path(site).resolve()
    pages = sorted(site.rglob("*.html"))
    problems = []

    if not pages:
        return [f"no pages were built into {site}"], 0, 0

    checked = 0
    for page in pages:
        where = page.relative_to(site)

        for placeholder in re.findall(r"\{\{(\w+)\}\}", page.read_text()):
            problems.append(f"{where}: unfilled placeholder {{{{{placeholder}}}}}")

        for address in links_in(page):
            checked += 1
            target = resolve(site, page, address)
            if target is None:
                continue
            if not target.exists():
                problems.append(f"{where}: link to {address} goes nowhere")

    # the app's Python is fetched by script rather than written in the HTML, so it is
    # listed in app.js and has to be checked from there
    app_js = site / "assets" / "app.js"
    if app_js.exists():
        listing = re.search(r"const sourceFiles = \[(.*?)\]", app_js.read_text(), re.S)
        if not listing:
            problems.append("assets/app.js no longer lists sourceFiles; the app is unchecked")
        else:
            for needed in re.findall(r'"([^"]+)"', listing.group(1)):
                checked += 1
                if not (site / "app" / needed).exists():
                    problems.append(f"the app imports {needed}, which was not published")

    return problems, len(pages), checked


def main():
    parser = argparse.ArgumentParser(description="Check a built site.")
    parser.add_argument("--site", default="site", help="the folder to check")
    args = parser.parse_args()

    problems, pages, links = check(args.site)
    print(f"checked {links} links and assets across {pages} pages")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"   {problem}")
        return 1
    print("every link resolves, and nothing is left unfilled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
