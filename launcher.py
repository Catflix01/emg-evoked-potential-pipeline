"""Start the app and open it in a browser. Used by the packaged Windows download.

Someone double-clicks the program, this starts Streamlit and opens the page. There is no
terminal involved, which is the whole point of the packaged version.

The browser version at docs/for-the-pi.md does the same job without any download, and is
the one that has actually been tested. This exists for people who would rather have a
program on their machine.
"""
import os
import sys
import threading
import webbrowser
from pathlib import Path

PORT = 8501


def app_directory():
    """Where the bundled files sit, whether packaged or run from the source tree."""
    if getattr(sys, "frozen", False):        # running from a PyInstaller build
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def open_browser_when_ready():
    """Give the server a moment to start, then open the page."""
    import time
    import urllib.request

    for _ in range(60):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}", timeout=1)
            webbrowser.open(f"http://localhost:{PORT}")
            return
        except Exception:
            continue
    print(f"The app did not start. Try opening http://localhost:{PORT} yourself.")


def main():
    root = app_directory()
    os.chdir(root)
    sys.path.insert(0, str(root / "src"))

    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    from streamlit.web import cli
    sys.argv = [
        "streamlit", "run", str(root / "pi_app.py"),
        f"--server.port={PORT}",
        "--server.address=localhost",     # this computer only, never the network
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(cli.main())


if __name__ == "__main__":
    main()
