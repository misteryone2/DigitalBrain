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
        "--memory-stats",
        action="store_true",
        help="Show memory statistics from --memory-db.",
    )
    parser.add_argument(
        "--get-memory",
        help="Fetch a specific memory record by id from --memory-db.",
    )
    parser.add_argument(
        "--search-memory",
        help="Search memory records by content substring.",
    )
    parser.add_argument(
        "--correct-memory",
        help="Correct a memory record by id, creating a superseding record.",
    )
    parser.add_argument(
        "--content",
        help="New content when using --correct-memory.",
    )
    parser.add_argument(
        "--source",
        help="Source filter for listing, or source override for --correct-memory.",
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
        help="Include superseded memory records when listing/searching.",
    )
    return parser


def _print_record(record: object) -> None:
    state = "active" if record.is_active else f"superseded-by={record.superseded_by}"
    print(f"[{record.created_at}] {record.id} {record.memory_type} {state}")
    print(f"  source: {record.source}")
    print(f"  confidence: {record.confidence}")
    print(f"  content: {record.content}")
    if record.supersedes:
        print(f"  supersedes: {record.supersedes}")
    if record.metadata:
        print(f"  metadata: {record.metadata}")


def _print_memory_records(store: SQLiteMemoryStore, args: argparse.Namespace) -> int:
    records = store.list_records(
        limit=args.limit,
        memory_type=args.memory_type,
        source=args.source,
        include_superseded=args.include_superseded,
        search=args.search_memory,
    )
    if not records:
        print("No memory records found.")
        return 0
    for record in records:
        _print_record(record)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    memory_actions = [
        args.list_memory,
        args.memory_stats,
        bool(args.get_memory),
        bool(args.correct_memory),
    ]
    if sum(1 for a in memory_actions if a) > 1:
        parser.error(
            "Use only one of --list-memory, --memory-stats, --get-memory, or --correct-memory"
        )

    if args.correct_memory:
        if not args.memory_db:
            parser.error("--correct-memory requires --memory-db")
        if not args.content:
            parser.error("--correct-memory requires --content")
        with SQLiteMemoryStore(args.memory_db) as memory:
            try:
                record = memory.correct(
                    args.correct_memory,
                    args.content,
                    source=args.source,
                )
            except ValueError as exc:
                print(f"Error: {exc}")
                return 1
        print(f"Corrected record: {args.correct_memory}")
        print(f"New record: {record.id}")
        return 0

    if args.list_memory or args.memory_stats or args.get_memory:
        if not args.memory_db:
            parser.error("Memory inspection commands require --memory-db")
        with SQLiteMemoryStore(args.memory_db) as memory:
            if args.memory_stats:
                stats = memory.stats()
                for key, value in stats.items():
                    print(f"{key}: {value}")
                return 0
            if args.get_memory:
                record = memory.get(args.get_memory)
                if record is None:
                    print(f"Memory record not found: {args.get_memory}")
                    return 1
                _print_record(record)
                return 0
            return _print_memory_records(memory, args)

    if not args.goal:
        parser.error("goal is required unless a memory command is used")

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
