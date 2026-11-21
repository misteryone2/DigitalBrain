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

## M2 — Knowledge and context
- [ ] Structured knowledge records/facts with provenance
- [ ] Context assembly from memory and knowledge
- [ ] Confidence and conflict handling
- [ ] Tests for retrieval, provenance, and updates

## M3 — Reasoning and planning
- [ ] Internal reasoning/planning interfaces (no external LLM dependency)
- [ ] Structured plans with validation and progress state
- [ ] Alternative evaluation and plan revision
- [ ] Measurable planning benchmarks

## M4 — Safe execution and tools
- [ ] Typed tool registry and permission model
- [ ] Read-only repository/system inspection tools
- [ ] Sandboxed execution with resource limits
- [ ] Audit logs for tool actions

## M5 — Learning and metacognition
- [ ] Outcome recording and evaluation
- [ ] Strategy/behavior updates based on evidence
- [ ] Capability and error tracking
- [ ] Performance metrics and regression detection

## M6 — Controlled evolution
- [ ] Laboratory/validation/production environment separation
- [ ] Isolated candidate workspaces
- [ ] Baseline benchmarks, candidate comparison, rollback
- [ ] Human approval for promotion and high-impact changes

## M7 — Interfaces and observability
- [ ] Authenticated API
- [ ] Dashboard reflecting real system state
- [ ] 3D architecture visualization backed by live data
- [ ] Desktop/mobile client access
