# DigitalBrain

DigitalBrain is an independent, modular software project for building an autonomous digital assistant that can reason over goals, manage memory, use tools, write and test code, and improve through measured experiments.

The project is developed incrementally. The first milestone is a small, testable Python core—not a claim of general intelligence.

## Current status

**Milestone 0 — Foundation**

- [x] Repository and project structure
- [x] Minimal Python package
- [x] Goal intake and deterministic planning baseline
- [x] Command-line entry point
- [x] Automated tests
- [ ] Persistent memory
- [ ] Language-model provider interface
- [ ] Tool permissions and sandboxed execution

## Requirements

- Python 3.11 or newer
- No paid services or API keys are required for the foundation milestone.

## Run

    python -m pip install -e .
    digitalbrain "Create a simple personal finance application"

Run tests:

    python -m unittest discover -s tests -v

## Design principles

1. **Modular:** reasoning, memory, tools, execution, and evolution remain replaceable components.
2. **Observable:** every action should have a traceable input, output, and status.
3. **Test-first:** generated changes must pass tests before promotion.
4. **Safe by default:** no unrestricted shell, filesystem, network, or credential access.
5. **Local-first:** prefer local models and free tooling; external providers are optional.
6. **Human-governed evolution:** experiments happen on isolated branches/workspaces; production changes require validation and explicit approval.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md).
