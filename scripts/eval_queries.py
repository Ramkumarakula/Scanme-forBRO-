"""Index a design library and check each query against its expected folder.

    python scripts/eval_queries.py [data_dir]          (default: mock_data)

data_dir must contain designs/ and queries/expected.csv with columns
query,expected_folder (expected_folder empty = design should NOT be in the library).
The same layout works for real samples, which is how the match threshold will be tuned.
"""

import csv
import sys
import tempfile
from pathlib import Path

from designfinder.fingerprint import fingerprint_file
from designfinder.index import connect, index_roots
from designfinder.search import Index


def evaluate(data_dir: Path) -> list[dict]:
    designs = (data_dir / "designs").resolve()
    with tempfile.TemporaryDirectory() as tmp:
        conn = connect(Path(tmp) / "eval.db")
        index_roots(conn, [designs])
        index = Index(conn)
        conn.close()

    results = []
    with open(data_dir / "queries" / "expected.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            matches = index.search(fingerprint_file(data_dir / "queries" / row["query"]), top=2)
            top = matches[0]
            expected = str(designs / row["expected_folder"]) if row["expected_folder"] else ""
            results.append(dict(
                query=row["query"],
                expected=row["expected_folder"] or "(new design)",
                got=Path(top.folder).relative_to(designs).as_posix(),
                score=top.score,
                runner_up=matches[1].score if len(matches) > 1 else 0.0,
                correct=top.folder == expected if expected else None,
            ))
    return results


def main() -> int:
    data_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "mock_data")
    results = evaluate(data_dir)
    print(f"{'query':30} {'expected':26} {'top match':26} {'score':>5} {'2nd':>5}  result")
    for r in results:
        verdict = {True: "OK", False: "WRONG", None: "(should be new)"}[r["correct"]]
        print(f"{r['query']:30} {r['expected']:26} {r['got']:26} "
              f"{r['score']:5.2f} {r['runner_up']:5.2f}  {verdict}")

    known = [r for r in results if r["correct"] is not None]
    new = [r for r in results if r["correct"] is None]
    print(f"\nTop-1 correct: {sum(r['correct'] for r in known)}/{len(known)}")
    if known and new:
        lowest_match = min(r["score"] for r in known if r["correct"])
        highest_new = max(r["score"] for r in new)
        print(f"Lowest correct-match score: {lowest_match:.2f}   "
              f"highest score for a new design: {highest_new:.2f}")
    return 0 if all(r["correct"] for r in known) else 1


if __name__ == "__main__":
    sys.exit(main())
