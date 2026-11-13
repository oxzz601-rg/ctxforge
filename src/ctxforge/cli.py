"""The ``ctxforge`` command line."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import __version__
from .core import build_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ctxforge",
        description="Pack a repository into a token-budgeted context bundle for an LLM prompt.",
    )
    parser.add_argument("path", nargs="?", default=".", help="repository root (default: current directory)")
    parser.add_argument("-q", "--query", default="", help="what the context is for, e.g. 'fix retry logic'")
    parser.add_argument("-b", "--budget", type=int, default=60000, help="token budget (default: 60000)")
    parser.add_argument("--include", action="append", default=[], help="glob of paths to include (repeatable)")
    parser.add_argument("--exclude", action="append", default=[], help="glob of paths to skip (repeatable)")
    parser.add_argument("--max-file-tokens", type=int, default=8000, help="cap for a single file (default: 8000)")
    parser.add_argument("--no-import-boost", action="store_true", help="do not pull in imported files")
    parser.add_argument("-o", "--output", help="write the bundle to a file instead of stdout")
    parser.add_argument("--json", action="store_true", help="print the manifest instead of the bundle")
    parser.add_argument("--list", action="store_true", help="list selected files with scores")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if args.budget < 100:
        print("ctxforge: budget must be at least 100 tokens", file=sys.stderr)
        return 2
    try:
        bundle = build_bundle(
            args.path,
            query=args.query,
            budget=args.budget,
            include=tuple(args.include),
            exclude=tuple(args.exclude),
            max_file_tokens=args.max_file_tokens,
            boost_imports=not args.no_import_boost,
        )
    except NotADirectoryError as exc:
        print("ctxforge: {}".format(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(bundle.manifest(), indent=2))
        return 0
    if args.list:
        for item in sorted(bundle.files, key=lambda entry: (-entry.score, entry.path)):
            print("{:>8.2f}  {:>7}  {}".format(item.score, item.tokens, item.path))
        print(
            "{} file(s), {} of {} tokens".format(len(bundle.files), bundle.total_tokens, bundle.budget),
            file=sys.stderr,
        )
        return 0

    text = bundle.render()
    if args.output:
        pathlib.Path(args.output).write_text(text, encoding="utf-8")
        print(
            "wrote {}: {} file(s), {} of {} tokens".format(
                args.output, len(bundle.files), bundle.total_tokens, bundle.budget
            ),
            file=sys.stderr,
        )
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
