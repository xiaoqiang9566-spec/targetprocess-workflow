import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tp_codex.benchmarks import (
    build_history_mode_benchmark_doc_section,
    build_history_mode_benchmark_markdown,
    build_history_mode_benchmark_matrix,
    summarize_benchmark_result,
)
from tp_codex.cli import run_cli


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    summaries = []
    for item in build_history_mode_benchmark_matrix(limit=args.limit):
        stdout_buffer = io.StringIO()
        started = time.perf_counter()
        with contextlib.redirect_stdout(stdout_buffer):
            exit_code = run_cli(item["argv"])
        elapsed = time.perf_counter() - started
        if exit_code != 0:
            print(
                json.dumps(
                    {
                        "workflow": item["workflow"],
                        "history_mode": item["history_mode"],
                        "exit_code": exit_code,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return exit_code
        payload = json.loads(stdout_buffer.getvalue())
        summaries.append(
            summarize_benchmark_result(
                workflow=item["workflow"],
                history_mode=item["history_mode"],
                limit=args.limit,
                elapsed_seconds=elapsed,
                payload=payload,
            )
        )

    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    print()
    print("Markdown summary:")
    print(build_history_mode_benchmark_markdown(summaries))
    print()
    print("Doc section:")
    print(build_history_mode_benchmark_doc_section(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
