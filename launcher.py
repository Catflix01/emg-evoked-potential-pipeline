"""Start the app and open it in a browser. Used by the packaged Windows and Mac downloads.

Someone double-clicks the program, this starts Streamlit and opens the page. There is no
terminal involved, which is the whole point of the packaged version.

The browser version does the same job without any download, but it can only hold a few
recordings at a time. The downloads read folders straight off the disk, which is what a
whole session needs. docs/forPIs.md says which to use when.
"""
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

FIRST_PORT = 8501


def free_port(first=FIRST_PORT, tries=20):
    """A port nothing is listening on yet, so two copies cannot collide."""
    for port in range(first, first + tries):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return first


def already_serving(first=FIRST_PORT, tries=20):
    """The port an instance of this app is already answering on, if there is one.

    Opening the app twice is the normal thing to do when nothing seems to have happened.
    Starting a second server then leaves two running and shows neither, so instead the
    second launch just opens the page the first one is already serving.
    """
    import urllib.request

    for port in range(first, first + tries):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                continue                      # nothing here, keep looking
        try:
            with urllib.request.urlopen(
                    f"http://localhost:{port}/_stcore/health", timeout=2) as answer:
                if answer.status == 200:
                    return port
        except Exception:
            continue                          # something else owns this port
    return None


def app_directory():
    """Where the bundled files sit, whether packaged or run from the source tree."""
    if getattr(sys, "frozen", False):        # running from a PyInstaller build
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def open_browser_when_ready(port):
    """Give the server a moment to start, then open the page."""
    import time
    import urllib.request

    for _ in range(60):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://localhost:{port}", timeout=1)
            webbrowser.open(f"http://localhost:{port}")
            return
        except Exception:
            continue
    print(f"The app did not start. Try opening http://localhost:{port} yourself.")


def main():
    # Opening it again when it is already running should show the page, not start a
    # second copy or appear to do nothing at all.
    running = already_serving()
    if running is not None:
        print(f"The app is already running. Opening http://localhost:{running}")
        webbrowser.open(f"http://localhost:{running}")
        return 0

    port = free_port()

    root = app_directory()
    os.chdir(root)
    sys.path.insert(0, str(root / "src"))

    # Streamlit treats its own files not being in site-packages as "in development", which
    # is exactly how a packaged app looks, and then refuses to accept a port.
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")

    threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()

    from streamlit.web import cli
    sys.argv = [
        # app.py, not the browser version: this one can open a folder chooser and read
        # recordings where they sit, which is the whole reason to download anything.
        "streamlit", "run", str(root / "app.py"),
        f"--server.port={port}",
        "--server.address=localhost",     # this computer only, never the network
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(cli.main())


if __name__ == "__main__":
    main()
