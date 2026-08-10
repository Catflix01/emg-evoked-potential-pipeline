"""The way in.

    python main.py                       open the app in a browser
    python main.py process               measure the recordings, write the results
    python main.py figures               draw the figures
    python main.py check   --data FOLDER what the pipeline found, and does it look right
    python main.py compare --data FOLDER this pipeline against the old MATLAB
    python main.py demo                  generate synthetic recordings to try things on
    python main.py safe-to-publish       what git would commit, and whether it is safe

This only decides which piece of the pipeline to run. Every measurement lives in src/,
so running something through here and running its script directly give the same answer.
The old script paths still work.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def open_the_app():
    """Hand over to Streamlit, which needs to own the process."""
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py")])


def process(args):
    import harmonize
    harmonize.main(data=args.data)


def figures(args):
    import visuals
    visuals.main()


def check(args):
    import selfcheck
    sys.argv = ["selfcheck"] + (["--data", args.data] if args.data else []) \
                             + (["--anonymise"] if args.anonymise else [])
    selfcheck.main()


def compare(args):
    import compare_legacy
    sys.argv = ["compare_legacy"] + (["--data", args.data] if args.data else [])
    compare_legacy.main()


def demo(args):
    import make_demo_data
    make_demo_data.main()


def safe_to_publish(args):
    import check_before_publish
    raise SystemExit(check_before_publish.main())


COMMANDS = {
    "process": (process, "measure the recordings and write the results"),
    "figures": (figures, "draw the figures into outputs/figures/"),
    "check": (check, "report what the pipeline found, and whether it looks right"),
    "compare": (compare, "compare this pipeline against the old MATLAB"),
    "demo": (demo, "generate synthetic recordings to try things on"),
    "safe-to-publish": (safe_to_publish, "check nothing patient-related would be committed"),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="EMG pipeline. With no command, opens the app in a browser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run `python main.py <command> --help` for a command's own options.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    for name, (_, help_text) in COMMANDS.items():
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        if name in {"process", "check", "compare"}:
            sub.add_argument("--data", help="folder of recordings; defaults to the configured one")
        if name == "check":
            sub.add_argument("--anonymise", action="store_true",
                             help="replace session names, which contain subject codes and dates")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        return open_the_app()
    COMMANDS[args.command][0](args)


if __name__ == "__main__":
    main()
