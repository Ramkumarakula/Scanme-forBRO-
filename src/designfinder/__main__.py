"""Command line: index design folders and search by image."""

import argparse
import sys
from pathlib import Path

from .fingerprint import fingerprint_file
from .index import connect, index_roots
from .search import Index

DEFAULT_DB = Path("data") / "index.db"


def _cmd_index(args) -> int:
    conn = connect(args.db)
    stats = index_roots(conn, args.roots,
                        on_error=lambda p, e: print(f"  skipped {p}: {e}", file=sys.stderr))
    print(f"added {stats.added}, updated {stats.updated}, unchanged {stats.unchanged}, "
          f"removed {stats.removed}, failed {stats.failed}")
    return 0


def _cmd_search(args) -> int:
    index = Index(connect(args.db))
    if not len(index):
        print("Index is empty. Run: python -m designfinder index <folder>")
        return 1
    matches = index.search(fingerprint_file(args.image), top=args.top)
    for rank, m in enumerate(matches, 1):
        print(f"{rank}. {m.score:.2f}  {m.folder}")
        print(f"     image:  {Path(m.best_image).name}")
        if m.masters:
            print(f"     master: {', '.join(p.name for p in m.masters)}")
        else:
            print("     master: (no .skp/.skb in folder)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="designfinder")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="index file")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="scan folders for PNG images")
    p_index.add_argument("roots", nargs="+", type=Path)
    p_index.set_defaults(func=_cmd_index)

    p_search = sub.add_parser("search", help="find folders matching an image")
    p_search.add_argument("image", type=Path)
    p_search.add_argument("--top", type=int, default=5)
    p_search.set_defaults(func=_cmd_search)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
