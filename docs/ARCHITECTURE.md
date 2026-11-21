# DigitalBrain architecture

This document translates the [founding vision](VISION.md) into a technical architecture. It distinguishes **target architecture** from **current implementation**. Components are considered real only when implemented, tested, and documented.

## Architectural direction

DigitalBrain is a local-first, modular cognitive system. Its cognitive capabilities must be developed internally through designed components, algorithms, memory, knowledge structures, reasoning, learning, and validation. External AI systems may assist development, but they are not cognitive dependencies of DigitalBrain.

## Target cognitive modules

| Module | Responsibility | Current state |
| --- | --- | --- |
| **CORE** | Orchestrate modules, manage the processing cycle, coordinate activity. | Minimal: goal intake and deterministic planning baseline. |
| **INPUT** | Acquire and contextualize input from users, interfaces, systems, and authorized sources. | Minimal: CLI goal string. |
| **MEMORY** | Store, organize, retrieve, and manage experiences, context, and relevant information. | Planned (M1). |
| **KNOWLEDGE** | Represent concepts, relations, facts, sources, and confidence levels. | Planned. |
| **REASONING** | Analyze, infer, compare, evaluate hypotheses, and solve problems. | Planned; no LLM-based reasoning. |
| **PLANNING** | Define goals, decompose problems, generate plans, evaluate alternatives, and adapt plans. | Baseline deterministic starter plan only. |
| **LEARNING** | Convert experiences, outcomes, errors, and feedback into verifiable improvements. | Planned. |
| **METACOGNITION** | Evaluate capabilities, uncertainty, limits, errors, and performance. | Planned. |
| **EXECUTION** | Execute planned actions through authorized tools with permissions and safety checks. | Planned. |
| **EVOLUTION** | Propose, run, and manage experiments and capability improvements in controlled environments. | Planned. |
| **VALIDATION** | Independently verify changes, capabilities, performance, compatibility, and safety. | Planned; CI tests exist as an early foundation. |

## Environments

The vision requires separated environments. These are architectural targets until implemented:

- **Production:** validated capabilities only. Unverified changes must not affect it.
- **Laboratory:** isolated experimentation, hypothesis testing, and candidate development. Failures must not compromise production.
- **Validation:** independent tests, benchmarks, safety checks, compatibility checks, and promotion criteria.

Promotion across environments must be traceable, reversible, and governed by explicit rules.

## Trust boundaries and safety

1. External input, model output, and tool output are untrusted data.
2. Tools expose narrow, typed capabilities; no unrestricted command execution.
3. Code execution occurs in disposable, resource-limited sandboxes.
4. Secrets are never placed in prompts, logs, or repository files.
5. Self-modification starts in isolated candidate workspaces/branches.
6. A candidate must pass independent tests and evaluation before promotion.
7. Production promotion, permission expansion, and high-impact actions require explicit human approval.
8. Core safety protections, backups, and audit records are not autonomously removable.

## Current data flow

```text
User goal -> CLI -> DigitalBrain.process_goal -> GoalResult(plan, status)
```

## Target data flow

```text
Input -> CORE -> Memory/Knowledge/Reasoning/Planning
      -> Permission-checked Execution/Tools
      -> Validation/Evaluation
      -> Learning/Memory updates
      -> Metacognition/Evolution (controlled)
```

## Platform strategy

- **Python:** cognitive components and backend.
- **SQLite:** initial persistence/memory.
- **FastAPI:** future API interface.
- **React + TypeScript:** dashboard/client.
- **Three.js:** 3D architecture visualization backed by real system state.
- **GitHub + CI/CD:** versioning, automated tests, and quality checks.

Technologies may evolve, but independence, modularity, verifiability, and safety remain mandatory.

## Current implementation boundary

Milestone 0 contains goal validation, a deterministic starter plan, CLI entry point, and unit tests. It does **not** yet provide persistent memory, knowledge representation, autonomous reasoning, learning, tool execution, self-modification, or a dashboard. Those capabilities must be added incrementally and verified before being reported as implemented.
