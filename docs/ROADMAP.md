# Roadmap

This roadmap turns the [founding vision](VISION.md) into incremental, verifiable milestones. Items are marked complete only when implemented, tested, and documented.

## M0 — Foundation
- [x] Python package and CLI
- [x] Deterministic goal intake and starter plan
- [x] Unit tests
- [x] Founding vision and architecture alignment

## M1 — Memory
- [x] SQLite persistence layer
- [x] Memory records with id, timestamp, type, source, content, confidence, and metadata
- [x] Correction and supersession support with traceability
- [x] Retrieval/query API with tests (basic filters; extend as needed)
- [x] Core integration for recording goal processing events
- [x] CLI support for memory persistence and inspection
- [x] Legacy episodic store removed; `SQLiteMemoryStore` is the single canonical memory model
- [x] Memory API hardening: search/stats/get/correct CLI, source filter, schema versioning (`PRAGMA user_version`)
- [ ] Memory migrations beyond v1 and richer query/indexing (FTS, pagination)

## M2 — Knowledge and context
- [x] Structured knowledge records/facts with provenance
- [x] Knowledge persistence/query/correction with tests
- [x] CLI knowledge commands (add/list/search/stats)
- [x] Context assembly baseline from memory and knowledge
- [x] Basic confidence/conflict detection surfaced in context summary
- [x] Deterministic conflict policy and confidence-weighted context selection
- [x] Deterministic context-aware planning baseline with tests
- [x] Append-only audit baseline for context/plan/goal events

## M3 - Reasoning and planning
- [x] Internal deterministic planning interface (`PlannerProtocol`, no external LLM dependency)
- [x] Structured plans with states, dependencies, verification, source rules
- [x] Conflict-aware warnings and blocked validation steps
- [x] Append-only plan version storage for replanning history
- [x] Explicit replanning command/workflow with audit trail
- [x] Explicit alternatives recorded in plan steps (no autonomous selection)
- [x] Plan lifecycle statuses and deterministic execution gate
- [x] Step outcome recording (explicit command/API) and gate metadata refresh
- [x] Failure-driven replanning proposals (explicit, non-autonomous)
- [x] Measurable deterministic benchmarks: planning structure, failure->replan proposal, explicit replanning versioning (`planning.benchmarks`, `tests/test_planning_benchmarks.py`)
## M4 - Safe execution and tools
- [x] Read-only tool registry (`list_dir`, `read_file`, `grep`, workspace-bounded)
- [x] Permission model baseline: default-deny allowlist, mutating tools blocked by default
- [x] Execution gate awareness: read-only inspection allowed with `needs_review` reason; mutating requires `ready`
- [x] Explicit approval model for mutating execution (`plan.execution_approved`, metadata; no auto-execution)
- [x] Scoped approval metadata (optional tool/risk class) and policy enforcement
- [x] Single-use approval reserve/finalize lifecycle for mutating execution
- [x] Approval expiration (`expires_at`) enforced in policy/store reserve path
- [x] Admin approval recovery: explicit list/resolve reserved approvals (audited, no auto-recovery)
- [x] Controlled mutating low-risk tools: `write_file`, `mkdir` (policy-gated, CLI opt-in + approval + ready gate required)
- [x] Sandbox hardening baseline: subprocess worker for default tools, timeout, best-effort process-tree kill, arg/output limits, per-tool output caps, symlink-path rejection, risk-class enforcement
- [x] Docker container sandbox mode (`host|container|auto|required`) with network-off/read-only/cpu/memory/pids/cap-drop/no-new-privileges/tmpfs
- [x] Policy: mutating tools denied unless sandbox resolves to container
- [x] Hardening options: digest requirement/allowlist, optional/required seccomp/apparmor, env+signed policy file, attestation file verification, Windows host Job Object limits (best-effort), container manifest audit (`tool.sandbox_manifest`)
- [x] Audit logs for tool actions/decisions (`tool.requested/allowed/denied/executed/failed`) and approval lifecycle events
- [x] CLI tool inspection/execution commands (`--list-tools`, `--run-tool`, `--approve-plan-execution`, `--allow-mutating-tools`, `--list-approvals`, `--resolve-approval`, sandbox/policy options)
- [ ] Hardened container-grade isolation by default across environments (full Sigstore/cosign provenance, mandatory profiles everywhere, centralized signed/PKI policy distribution, non-Docker/containerd parity)
- [ ] Broader mutating tool set with per-tool risk classes and human approval workflow

## M5 — Learning and metacognition
- [x] Outcome recording and evaluation (`SQLiteOutcomeStore`, CLI record/summary)
- [x] Capability and error tracking baseline (`learning.metacognition.capability_report`)
- [x] Performance metrics summary (deterministic, from recorded outcomes)
- [ ] Strategy/behavior updates based on evidence (no auto-modification of code/prompt/policy without audit/approval)
- [ ] Regression detection across baselines/candidates

## M6 — Controlled evolution
- [x] Environment promotion/rollback records (`lab/validation/production`, SQLite promotion store, CLI)
- [ ] Isolated candidate workspaces and execution isolation for experiments
- [ ] Baseline benchmarks, candidate comparison, automated rollback triggers
- [ ] Human approval for promotion and high-impact changes (policy-enforced)

## M7 — Interfaces and observability
- [x] Authenticated read-only API baseline (`digitalbrain.api.server`, token env, no mutation endpoints)
- [ ] Dashboard reflecting real system state
- [ ] 3D architecture visualization backed by live data
- [ ] Desktop/mobile client access
