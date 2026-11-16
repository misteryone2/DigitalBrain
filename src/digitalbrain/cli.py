"""Command-line interface for the first DigitalBrain milestone."""

from __future__ import annotations

import argparse

from digitalbrain.core.brain import DigitalBrain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="digitalbrain",
        description="Submit an objective to the DigitalBrain prototype.",
    )
    parser.add_argument("goal", help="The objective the brain should process.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = DigitalBrain().process_goal(args.goal)

    print(f"Goal: {result.goal}")
    print(f"Status: {result.status}")
    print("\nInitial plan:")
    for index, step in enumerate(result.plan, start=1):
        print(f"{index}. {step}")
    print("\nNote: this milestone uses a deterministic baseline planner; "
          "it does not yet perform model-based reasoning or execute code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
