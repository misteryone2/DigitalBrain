"""Command-line interface for the DigitalBrain prototype."""

from __future__ import annotations

import argparse

from digitalbrain.core.brain import DigitalBrain
from digitalbrain.memory import MemoryType, SQLiteMemoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="digitalbrain",
        description="Submit an objective to the DigitalBrain prototype or inspect memory.",
    )
    parser.add_argument(
        "goal",
        nargs="?",
        help="The objective the brain should process.",
    )
    parser.add_argument(
        "--memory-db",
        help="SQLite file for persisting or reading memory records.",
    )
    parser.add_argument(
        "--list-memory",
        action="store_true",
        help="List memory records from --memory-db instead of processing a goal.",
    )
    parser.add_argument(
        "--memory-type",
        choices=[m.value for m in MemoryType],
        help="Filter listed memory records by type.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of memory records to list (default: 10).",
    )
    parser.add_argument(
        "--include-superseded",
        action="store_true",
        help="Include superseded memory records when listing.",
    )
    return parser


def _print_memory_records(store: SQLiteMemoryStore, args: argparse.Namespace) -> int:
    records = store.list_records(
        limit=args.limit,
        memory_type=args.memory_type,
        include_superseded=args.include_superseded,
    )
    if not records:
        print("No memory records found.")
        return 0

    for record in records:
        state = "active" if record.is_active else f"superseded-by={record.superseded_by}"
        print(f"[{record.created_at}] {record.id} {record.memory_type} {state}")
        print(f"  source: {record.source}")
        print(f"  confidence: {record.confidence}")
        print(f"  content: {record.content}")
        if record.supersedes:
            print(f"  supersedes: {record.supersedes}")
        if record.metadata:
            print(f"  metadata: {record.metadata}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_memory:
        if not args.memory_db:
            parser.error("--list-memory requires --memory-db")
        with SQLiteMemoryStore(args.memory_db) as memory:
            return _print_memory_records(memory, args)

    if not args.goal:
        parser.error("goal is required unless --list-memory is used")

    memory = SQLiteMemoryStore(args.memory_db) if args.memory_db else None
    try:
        result = DigitalBrain(memory=memory).process_goal(args.goal)
    finally:
        if memory is not None:
            memory.close()

    print(f"Goal: {result.goal}")
    print(f"Status: {result.status}")
    if result.memory_record_id:
        print(f"Memory record: {result.memory_record_id}")
    print("\nInitial plan:")
    for index, step in enumerate(result.plan, start=1):
        print(f"{index}. {step}")
    print(
        "\nNote: this prototype uses a deterministic baseline planner and optional "
        "SQLite memory. It does not yet perform autonomous reasoning, learning, "
        "tool execution, or self-modification."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
