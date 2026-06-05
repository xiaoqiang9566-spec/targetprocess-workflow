import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tp_codex.cli import run_cli


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity", required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    command = ["entities", "list", "--entity", args.entity]
    if args.limit:
        command.extend(["--limit", str(args.limit)])
    raise SystemExit(run_cli(command))
