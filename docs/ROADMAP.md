# Roadmap

## M0 — Foundation
- [x] Python package and CLI
- [x] Deterministic goal intake and starter plan
- [x] Unit tests

## M1 — Memory
- [ ] SQLite storage layer
- [ ] Memory records with timestamps, type, source, and confidence
- [ ] Correction and supersession support
- [ ] Tests for persistence and retrieval

## M2 — Model interface
- [ ] Provider protocol
- [ ] Local model adapter
- [ ] Timeouts, error handling, and structured outputs
- [ ] No provider-specific logic in the core

## M3 — Reasoning and planning
- [ ] Structured task plans
- [ ] Plan validation and progress state
- [ ] Evaluation of proposed plans

## M4 — Safe tools and coding
- [ ] Typed tool registry and permission model
- [ ] Read-only repository inspection
- [ ] Patch generation and review
- [ ] Sandboxed test execution

## M5 — Controlled evolution
- [ ] Isolated candidate workspaces
- [ ] Baseline benchmarks and regression suite
- [ ] Candidate comparison and rollback
- [ ] Human approval for production promotion

## M6 — Agent network and clients
- [ ] Bounded specialist agents
- [ ] Coordinator and task handoff
- [ ] Authenticated API
- [ ] Responsive desktop/mobile client
