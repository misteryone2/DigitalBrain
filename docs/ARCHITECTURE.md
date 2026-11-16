# DigitalBrain architecture

## Architectural direction

DigitalBrain is a local-first, modular agent system. The language model (when connected) is one replaceable reasoning component, not the whole application.

### Main subsystems

- **Core:** lifecycle, orchestration, configuration, and event flow.
- **Reasoning and planning:** interpret goals, create plans, evaluate alternatives, and track completion.
- **Memory:** working context plus persistent episodic and semantic stores, with provenance and correction/supersession.
- **Learning:** evaluate outcomes and update strategies based on evidence.
- **Model providers:** interchangeable local or remote model adapters.
- **Tools and coding:** typed tool interfaces for repository inspection and code changes.
- **Execution:** isolated, resource-limited test and build environments.
- **Evolution:** propose changes, run evaluations, compare against a baseline, and prepare rollback.
- **Agent network:** delegate bounded tasks to specialist agents.
- **Interfaces:** CLI first, then responsive web/mobile clients.

## Trust boundaries

1. Model output is untrusted input.
2. Tools expose narrow, typed capabilities; no unrestricted command execution.
3. Code execution occurs in a disposable sandbox with resource and network limits.
4. Secrets are never placed in prompts, logs, or repository files.
5. Self-modification starts in a separate worktree/branch.
6. A candidate version must pass tests and evaluation before promotion.
7. Production promotion and permission expansion require explicit human approval.

## Initial data flow

User goal -> Core -> Planner -> Plan -> User-visible result

Later:

Goal -> Core -> Reasoning provider -> Planner -> Permission-checked tools -> Sandbox -> Evaluator -> Memory

## Platform strategy

The Python core runs on desktop and can be hosted behind an authenticated API. A responsive TypeScript client can then serve desktop browsers and mobile browsers. Native mobile packaging is a later decision, not a requirement for the first milestone.

## Current implementation boundary

Milestone 0 contains only goal validation and a deterministic starter plan. It does not yet connect an LLM, persist memory, call external tools, execute generated code, or modify itself.
