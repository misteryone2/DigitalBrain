# DigitalBrain

DigitalBrain is an independent, modular software project for building an autonomous digital assistant that can reason over goals, manage memory, use tools, write and test code, and improve through measured experiments.

The project is developed incrementally. The first milestone is a small, testable Python core—not a claim of general intelligence.

## Current status

**Technical reset in progress (post-M1 baseline)**

- [x] Repository and project structure
- [x] Minimal Python package
- [x] Goal/message intake with deterministic intent classifier
- [x] Deterministic baseline planning
- [x] SQLite memory store with traceable records and correction/supersession
- [x] CLI memory persistence and inspection
- [x] Automated tests consolidated under `tests/`
- [x] Legacy episodic store removed; canonical SQLite memory model
- [x] Memory hardening (search/stats/get/correct CLI, source filter, schema versioning)
- [x] Knowledge store baseline (SQLite facts: subject/predicate/object, provenance, confidence, correction/supersession)
- [x] CLI knowledge commands (add/list/search/stats)
- [x] Deterministic context assembly baseline (memory + knowledge snapshot in goal processing)
- [ ] Knowledge/context use in planning decisions (still deterministic, testable)
- [ ] Clear Core contracts/protocols and module boundaries

## Requirements

- Python 3.11 or newer
- No paid services or API keys are required for the foundation milestone.

## Run

    python -m pip install -e .
    digitalbrain "Create a simple personal finance application"
    digitalbrain --memory-db .\data\memory.db "Track expenses"
    digitalbrain --memory-db .\data\memory.db --list-memory
    digitalbrain --memory-db .\data\memory.db --list-memory --source cli --memory-type goal
    digitalbrain --memory-db .\data\memory.db --search-memory expenses
    digitalbrain --memory-db .\data\memory.db --memory-stats
    digitalbrain --memory-db .\data\memory.db --get-memory <record-id>
    digitalbrain --memory-db .\data\memory.db --correct-memory <record-id> --content "Updated fact" --source cli
    digitalbrain --knowledge-db .\data\knowledge.db --add-fact DigitalBrain uses SQLite --fact-source docs
    digitalbrain --knowledge-db .\data\knowledge.db --list-facts
    digitalbrain --knowledge-db .\data\knowledge.db --knowledge-stats

Run tests:

    python -m unittest discover -s tests -v

## Design principles

1. **Modular:** reasoning, memory, tools, execution, and evolution remain replaceable components.
2. **Observable:** every action should have a traceable input, output, and status.
3. **Test-first:** generated changes must pass tests before promotion.
4. **Safe by default:** no unrestricted shell, filesystem, network, or credential access.
5. **Local-first:** prefer local models and free tooling; external providers are optional.
6. **Human-governed evolution:** experiments happen on isolated branches/workspaces; production changes require validation and explicit approval.

See [docs/VISION.md](docs/VISION.md) for the founding vision and principles, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the technical architecture, and [docs/ROADMAP.md](docs/ROADMAP.md) for the development roadmap.
