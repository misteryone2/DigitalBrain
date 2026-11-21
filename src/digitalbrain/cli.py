"""Command-line interface for the DigitalBrain prototype."""

from __future__ import annotations

import argparse

from digitalbrain.core.brain import DigitalBrain
from digitalbrain.knowledge import SQLiteKnowledgeStore
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
        "--knowledge-db",
        help="SQLite file for persisting or reading knowledge facts.",
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
        help="Include superseded memory/knowledge records when listing/searching.",
    )
    parser.add_argument(
        "--add-fact",
        nargs=3,
        metavar=("SUBJECT", "PREDICATE", "OBJECT"),
        help="Add a knowledge fact to --knowledge-db.",
    )
    parser.add_argument(
        "--list-facts",
        action="store_true",
        help="List knowledge facts from --knowledge-db.",
    )
    parser.add_argument(
        "--knowledge-stats",
        action="store_true",
        help="Show knowledge store statistics from --knowledge-db.",
    )
    parser.add_argument(
        "--search-facts",
        help="Search knowledge facts by subject/predicate/object substring.",
    )
    parser.add_argument(
        "--fact-source",
        default="cli",
        help="Source for --add-fact (default: cli).",
    )
    parser.add_argument(
        "--fact-confidence",
        type=float,
        default=1.0,
        help="Confidence for --add-fact (default: 1.0).",
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


def _print_fact(record: object) -> None:
    state = "active" if record.is_active else f"superseded-by={record.superseded_by}"
    print(f"[{record.created_at}] {record.id} {state}")
    print(f"  fact: {record.fact}")
    print(f"  source: {record.source}")
    print(f"  confidence: {record.confidence}")
    if record.supersedes:
        print(f"  supersedes: {record.supersedes}")
    if record.metadata:
        print(f"  metadata: {record.metadata}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    memory_actions = [
        args.list_memory,
        args.memory_stats,
        bool(args.get_memory),
        bool(args.correct_memory),
    ]
    knowledge_actions = [bool(args.add_fact), args.list_facts, args.knowledge_stats]
    if sum(1 for a in memory_actions if a) > 1:
        parser.error(
            "Use only one of --list-memory, --memory-stats, --get-memory, or --correct-memory"
        )
    if sum(1 for a in knowledge_actions if a) > 1:
        parser.error("Use only one of --add-fact, --list-facts, or --knowledge-stats")
    if any(memory_actions) and any(knowledge_actions):
        parser.error("Use memory commands separately from knowledge commands")

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

    if args.add_fact or args.list_facts or args.knowledge_stats:
        if not args.knowledge_db:
            parser.error("Knowledge commands require --knowledge-db")
        with SQLiteKnowledgeStore(args.knowledge_db) as knowledge:
            if args.knowledge_stats:
                for key, value in knowledge.stats().items():
                    print(f"{key}: {value}")
                return 0
            if args.add_fact:
                subject, predicate, obj = args.add_fact
                try:
                    record = knowledge.add_fact(
                        subject, predicate, obj,
                        source=args.fact_source,
                        confidence=args.fact_confidence,
                    )
                except ValueError as exc:
                    print(f"Error: {exc}")
                    return 1
                print(f"Knowledge record: {record.id}")
                print(f"Fact: {record.fact}")
                return 0
            facts = knowledge.list_facts(
                limit=args.limit,
                include_superseded=args.include_superseded,
                search=args.search_facts,
            )
            if not facts:
                print("No knowledge facts found.")
                return 0
            for fact in facts:
                _print_fact(fact)
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
        parser.error("goal is required unless a memory or knowledge command is used")

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
