"""CLI entrypoint: `subforge` launches the TUI (PRD §7)."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subforge", description="Local-first subtitle generation and translation"
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("project_dir", nargs="?", help="optional project directory to open")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.version:
        from subforge import __version__

        print(f"subforge {__version__}")
        return
    from subforge.tui.app import run

    run(project_dir=args.project_dir)


if __name__ == "__main__":
    sys.exit(main())
