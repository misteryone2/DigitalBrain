"""Command-line interface for the DigitalBrain prototype."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from digitalbrain.core.audit import AuditLog
from digitalbrain.core.brain import DigitalBrain
from digitalbrain.execution import ExecutionPolicy, SandboxPolicyConfig, ToolExecutor
from digitalbrain.knowledge import SQLiteKnowledgeStore
from digitalbrain.memory import MemoryType, SQLiteMemoryStore
from digitalbrain.planning import SQLitePlanStore


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
        "--audit-db",
        help="SQLite file for append-only audit events.",
    )
    parser.add_argument(
        "--plan-db",
        help="SQLite file for persisting plan versions.",
    )
    parser.add_argument(
        "--list-plans",
        action="store_true",
        help="List plan records from --plan-db.",
    )
    parser.add_argument(
        "--get-plan",
        help="Get a plan record by id from --plan-db.",
    )
    parser.add_argument(
        "--replan",
        help="Create a new plan version for a goal using --plan-db (and optional context DBs).",
    )
    parser.add_argument(
        "--reason",
        help="Reason for --replan, recorded in audit/details.",
    )
    parser.add_argument(
        "--set-plan-lifecycle",
        nargs=2,
        metavar=("PLAN_ID", "STATUS"),
        help="Set lifecycle status for a plan record in --plan-db.",
    )
    parser.add_argument(
        "--record-step-outcome",
        nargs=3,
        metavar=("PLAN_ID", "STEP_ID", "OUTCOME"),
        help="Record step outcome (passed|failed|skipped) in --plan-db.",
    )
    parser.add_argument(
        "--list-audit",
        action="store_true",
        help="List audit events from --audit-db.",
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
        help="Maximum number of records to list (default: 10).",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of records to skip when listing (default: 0).",
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
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available read-only execution tools.",
    )
    parser.add_argument(
        "--run-tool",
        help="Run an allowlisted tool by name (read-only by default; mutating requires explicit flags and approval).",
    )
    parser.add_argument(
        "--tool-args",
        default="{}",
        help="JSON object with arguments for --run-tool (default: {}).",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root for tool execution path boundary (default: current directory).",
    )
    parser.add_argument(
        "--tool-plan-id",
        help="Plan record id in --plan-db whose execution gate is used for --run-tool.",
    )
    parser.add_argument(
        "--approve-plan-execution",
        metavar="PLAN_ID",
        help="Explicitly approve a ready plan for future mutating execution (no auto-execution). Requires --plan-db.",
    )
    parser.add_argument(
        "--approve-tool",
        help="Optional tool name to scope --approve-plan-execution to a specific tool.",
    )
    parser.add_argument(
        "--approve-risk-class",
        help="Optional risk class label recorded with --approve-plan-execution.",
    )
    parser.add_argument(
        "--approve-expires-at",
        help="Optional ISO-8601 expiration for --approve-plan-execution (UTC recommended).",
    )
    parser.add_argument(
        "--allow-mutating-tools",
        action="store_true",
        help="Enable mutating tools in policy for this command. Mutating tools still require ready gate and explicit plan approval.",
    )
    parser.add_argument(
        "--sandbox-mode",
        choices=["host", "container", "auto", "required"],
        default=os.environ.get("DIGITALBRAIN_SANDBOX_MODE", "host"),
        help="Sandbox mode for tool execution: host (default), container, auto, or required. Can be set via DIGITALBRAIN_SANDBOX_MODE.",
    )
    parser.add_argument(
        "--container-image",
        default=os.environ.get("DIGITALBRAIN_CONTAINER_IMAGE", "python:3.12-slim"),
        help="Container image for container sandbox modes. Can be set via DIGITALBRAIN_CONTAINER_IMAGE.",
    )
    parser.add_argument(
        "--container-seccomp",
        default=os.environ.get("DIGITALBRAIN_CONTAINER_SECCOMP"),
        help="Optional seccomp profile for container sandbox (Docker --security-opt seccomp=...). Env: DIGITALBRAIN_CONTAINER_SECCOMP.",
    )
    parser.add_argument(
        "--container-apparmor",
        default=os.environ.get("DIGITALBRAIN_CONTAINER_APPARMOR"),
        help="Optional apparmor profile for container sandbox (Docker --security-opt apparmor=...). Env: DIGITALBRAIN_CONTAINER_APPARMOR.",
    )
    parser.add_argument(
        "--require-image-digest",
        action="store_true",
        default=os.environ.get("DIGITALBRAIN_REQUIRE_IMAGE_DIGEST", "").lower() in {"1", "true", "yes"},
        help="Require --container-image to include @sha256:... digest. Env: DIGITALBRAIN_REQUIRE_IMAGE_DIGEST.",
    )
    parser.add_argument(
        "--host-job-limits",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("DIGITALBRAIN_HOST_JOB_LIMITS", "1").lower() in {"1", "true", "yes", "on"},
        help="Apply Windows Job Object limits to host subprocess sandbox (default: enabled). Env: DIGITALBRAIN_HOST_JOB_LIMITS.",
    )
    parser.add_argument(
        "--sandbox-policy-file",
        help="Path to signed/central sandbox policy JSON. Env: DIGITALBRAIN_SANDBOX_POLICY_FILE.",
    )
    parser.add_argument(
        "--attestation-path",
        help="Path to image attestation JSON. Env: DIGITALBRAIN_ATTESTATION_PATH.",
    )
    parser.add_argument(
        "--list-approvals",
        action="store_true",
        help="List execution approvals from --plan-db (optionally --get-plan/--approval-state filters).",
    )
    parser.add_argument(
        "--approval-state",
        help="Filter --list-approvals by state (approved|reserved|executed|failed|cancelled).",
    )
    parser.add_argument(
        "--resolve-approval",
        nargs=3,
        metavar=("PLAN_ID", "APPROVED_AT", "STATE"),
        help="Admin-resolve a reserved approval (STATE: executed|failed|cancelled). Requires --plan-db.",
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
        offset=args.offset,
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


def _print_plan(record: object) -> None:
    lifecycle = getattr(record, "lifecycle_status", "active")
    print(f"[{record.created_at}] {record.id} v{record.version} status={record.status} lifecycle={lifecycle}")
    print(f"  goal: {record.goal}")
    print(f"  source: {record.source}")
    if record.parent_plan_id:
        print(f"  parent: {record.parent_plan_id}")
    if record.warnings:
        print(f"  warnings: {list(record.warnings)}")
    gate = getattr(record, "metadata", {}).get("execution_gate") if hasattr(record, "metadata") else None
    if isinstance(gate, dict):
        print(f"  execution_gate: {gate.get('status')} executable={gate.get('executable')}")
    print(f"  steps: {len(record.steps)}")


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
    plan_actions = [args.list_plans, bool(args.get_plan and not args.list_approvals), bool(args.replan), bool(args.set_plan_lifecycle), bool(args.record_step_outcome), bool(args.approve_plan_execution), args.list_approvals, bool(args.resolve_approval)]
    audit_actions = [args.list_audit]
    execution_actions = [args.list_tools, bool(args.run_tool)]
    groups = [any(memory_actions), any(knowledge_actions), any(plan_actions), any(audit_actions), any(execution_actions)]
    if sum(1 for a in memory_actions if a) > 1:
        parser.error(
            "Use only one of --list-memory, --memory-stats, --get-memory, or --correct-memory"
        )
    if sum(1 for a in knowledge_actions if a) > 1:
        parser.error("Use only one of --add-fact, --list-facts, or --knowledge-stats")
    if sum(1 for a in plan_actions if a) > 1:
        parser.error("Use only one plan action: --list-plans, --get-plan, --replan, --set-plan-lifecycle, --record-step-outcome, --approve-plan-execution, --list-approvals, or --resolve-approval")
    if sum(1 for a in execution_actions if a) > 1:
        parser.error("Use only one of --list-tools or --run-tool")
    if args.run_tool and args.tool_plan_id and not args.plan_db:
        parser.error("--tool-plan-id requires --plan-db")
    if args.approve_plan_execution and not args.plan_db:
        parser.error("--approve-plan-execution requires --plan-db")
    if (args.list_approvals or args.resolve_approval) and not args.plan_db:
        parser.error("Approval commands require --plan-db")
    if sum(groups) > 1:
        parser.error("Use memory, knowledge, plan, audit, or execution commands separately")

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

    if args.set_plan_lifecycle:
        if not args.plan_db:
            parser.error("--set-plan-lifecycle requires --plan-db")
        plan_id, lifecycle_status = args.set_plan_lifecycle
        audit = AuditLog(args.audit_db) if args.audit_db else None
        try:
            with SQLitePlanStore(args.plan_db) as plans:
                try:
                    rec = plans.set_lifecycle_status(plan_id, lifecycle_status, reason=args.reason)
                except ValueError as exc:
                    print(f"Error: {exc}")
                    return 1
            if audit is not None:
                audit.record(
                    "plan.lifecycle_changed",
                    actor="cli",
                    outcome=rec.lifecycle_status,
                    details={"plan_id": rec.id, "reason": args.reason},
                )
        finally:
            if audit is not None:
                audit.close()
        print(f"Plan record: {rec.id}")
        print(f"Lifecycle: {rec.lifecycle_status}")
        return 0

    if args.record_step_outcome:
        if not args.plan_db:
            parser.error("--record-step-outcome requires --plan-db")
        plan_id, step_id, outcome = args.record_step_outcome
        with SQLitePlanStore(args.plan_db) as plans:
            try:
                rec, event = plans.record_step_outcome(plan_id, step_id, outcome, reason=args.reason)
            except ValueError as exc:
                print(f"Error: {exc}")
                return 1
        gate = rec.metadata.get("execution_gate", {}) if isinstance(rec.metadata, dict) else {}
        if args.audit_db:
            with AuditLog(args.audit_db) as audit:
                audit.record("plan.step_outcome", actor="cli", outcome=event['outcome'], details={"plan_id": rec.id, "step_id": event['step_id'], "reason": event.get('reason')})
                proposal = event.get("replan_proposal")
                if isinstance(proposal, dict):
                    audit.record("plan.replan_proposed", actor="cli", outcome="proposed", details={"plan_id": rec.id, "step_id": event['step_id'], "reason": proposal.get('reason')})
        print(f"Plan record: {rec.id}")
        print(f"Step: {event['step_id']} outcome={event['outcome']}")
        print(f"Execution gate: {gate.get('status')} executable={gate.get('executable')}")
        proposal = event.get("replan_proposal")
        if isinstance(proposal, dict):
            print("Replan proposal (explicit, not executed):")
            print(f"- reason: {proposal.get('reason')}")
            print(f"- suggested: {proposal.get('suggested_command')}")
        return 0

    if args.approve_plan_execution:
        if not args.plan_db:
            parser.error("--approve-plan-execution requires --plan-db")
        audit = AuditLog(args.audit_db) if args.audit_db else None
        try:
            with SQLitePlanStore(args.plan_db) as plans:
                try:
                    rec = plans.approve_execution(
                        args.approve_plan_execution,
                        reason=args.reason,
                        actor="cli",
                        tool_name=args.approve_tool,
                        risk_class=args.approve_risk_class,
                        expires_at=args.approve_expires_at,
                    )
                except ValueError as exc:
                    print(f"Error: {exc}")
                    return 1
            if audit is not None:
                audit.record(
                    "plan.execution_approved",
                    actor="cli",
                    outcome="approved",
                    details={
                        "plan_id": rec.id,
                        "reason": args.reason,
                        "tool_name": args.approve_tool,
                        "risk_class": args.approve_risk_class,
                        "expires_at": args.approve_expires_at,
                    },
                )
        finally:
            if audit is not None:
                audit.close()
        gate = rec.metadata.get("execution_gate", {}) if isinstance(rec.metadata, dict) else {}
        approval = rec.metadata.get("execution_approval", {}) if isinstance(rec.metadata, dict) else {}
        print(f"Plan record: {rec.id}")
        print(f"Lifecycle: {rec.lifecycle_status}")
        print(f"Execution gate: {gate.get('status')} executable={gate.get('executable')}")
        print(f"Approved: {bool(approval.get('approved', False))}")
        if approval.get("tool_name"):
            print(f"Approved tool: {approval.get('tool_name')}")
        if approval.get("risk_class"):
            print(f"Risk class: {approval.get('risk_class')}")
        if approval.get("expires_at"):
            print(f"Expires at: {approval.get('expires_at')}")
        return 0

    if args.list_approvals:
        if not args.plan_db:
            parser.error("--list-approvals requires --plan-db")
        with SQLitePlanStore(args.plan_db) as plans:
            approvals = plans.list_execution_approvals(plan_id=args.get_plan, state=args.approval_state)
        if not approvals:
            print("No execution approvals found.")
            return 0
        for a in approvals:
            state = a.get("execution_state") or ("consumed" if a.get("consumed_at") else "approved")
            print(f"{a.get('plan_id')} {a.get('approved_at')} state={state} tool={a.get('tool_name')} risk={a.get('risk_class')}")
            if a.get("reason"):
                print(f"  reason: {a.get('reason')}")
            if a.get("execution_error"):
                print(f"  error: {a.get('execution_error')}")
        return 0

    if args.resolve_approval:
        if not args.plan_db:
            parser.error("--resolve-approval requires --plan-db")
        plan_id, approved_at, state = args.resolve_approval
        if state not in {"executed", "failed", "cancelled"}:
            print("Error: resolution state must be executed, failed, or cancelled.")
            return 1
        audit = AuditLog(args.audit_db) if args.audit_db else None
        try:
            with SQLitePlanStore(args.plan_db) as plans:
                approvals = plans.list_execution_approvals(plan_id=plan_id)
                match = next((a for a in approvals if a.get("approved_at") == approved_at), None)
                if match is None:
                    print("Error: approval not found.")
                    return 1
                try:
                    rec = plans.finalize_execution_approval(
                        plan_id,
                        approved_at=approved_at,
                        tool_name=str(match.get("tool_name") or ""),
                        risk_class=match.get("risk_class"),
                        ok=state == "executed",
                        error=args.reason if state != "executed" else None,
                        actor="cli-admin",
                        resolution=state,
                    )
                except ValueError as exc:
                    print(f"Error: {exc}")
                    return 1
            if audit is not None:
                audit.record(
                    "plan.execution_approval_resolved",
                    actor="cli-admin",
                    outcome=state,
                    details={"plan_id": plan_id, "approved_at": approved_at, "state": state, "reason": args.reason},
                )
        finally:
            if audit is not None:
                audit.close()
        print(f"Plan record: {rec.id}")
        print(f"Approval {approved_at} resolved: {state}")
        return 0

    if args.replan:
        if not args.plan_db:
            parser.error("--replan requires --plan-db")
        memory = SQLiteMemoryStore(args.memory_db) if args.memory_db else None
        knowledge = SQLiteKnowledgeStore(args.knowledge_db) if args.knowledge_db else None
        audit = AuditLog(args.audit_db) if args.audit_db else None
        try:
            with SQLitePlanStore(args.plan_db) as plans:
                brain = DigitalBrain(memory=memory, knowledge=knowledge, audit_log=audit, plan_store=plans)
                result = brain.replan_goal(args.replan, reason=args.reason)
        except ValueError as exc:
            print(f"Error: {exc}")
            return 1
        finally:
            if audit is not None:
                audit.close()
            if knowledge is not None:
                knowledge.close()
            if memory is not None:
                memory.close()
        print(f"Goal: {result.goal}")
        print(f"Status: {result.status.value}")
        if result.plan_record_id:
            print(f"Plan record: {result.plan_record_id}")
        if result.warnings:
            print("Warnings:")
            for warning in result.warnings:
                print(f"- {warning}")
        return 0

    if args.list_plans or args.get_plan:
        if not args.plan_db:
            parser.error("Plan commands require --plan-db")
        with SQLitePlanStore(args.plan_db) as plans:
            if args.get_plan:
                plan = plans.get(args.get_plan)
                if plan is None:
                    print(f"Plan record not found: {args.get_plan}")
                    return 1
                _print_plan(plan)
                return 0
            records = plans.list_plans(limit=args.limit, offset=args.offset)
            if not records:
                print("No plan records found.")
                return 0
            for rec in records:
                _print_plan(rec)
            return 0

    if args.list_tools or args.run_tool:
        if args.sandbox_policy_file:
            os.environ["DIGITALBRAIN_SANDBOX_POLICY_FILE"] = args.sandbox_policy_file
        if args.attestation_path:
            os.environ["DIGITALBRAIN_ATTESTATION_PATH"] = args.attestation_path
        sandbox_policy = SandboxPolicyConfig.from_env_and_file()
        audit = AuditLog(args.audit_db) if args.audit_db else None
        try:
            tools = None
            if args.list_tools:
                executor = ToolExecutor(
                    workspace_root=args.workspace,
                    audit_log=audit,
                    sandbox_mode=args.sandbox_mode,
                    container_image=args.container_image,
                    container_seccomp=args.container_seccomp,
                    container_apparmor=args.container_apparmor,
                    require_image_digest=bool(args.require_image_digest),
                    host_job_limits=bool(args.host_job_limits),
                    sandbox_policy=sandbox_policy,
                )
                for spec in executor.list_tools():
                    ro = "read-only" if spec["read_only"] else "mutating"
                    print(f"{spec['name']} ({ro}): {spec['description']}")
                return 0

            try:
                tool_args = json.loads(args.tool_args)
            except json.JSONDecodeError as exc:
                print(f"Error: invalid --tool-args JSON: {exc}")
                return 1
            if not isinstance(tool_args, dict):
                print("Error: --tool-args must be a JSON object.")
                return 1

            gate = None
            approval = None
            if args.tool_plan_id:
                with SQLitePlanStore(args.plan_db) as plans:
                    plan = plans.get(args.tool_plan_id)
                    if plan is None:
                        print(f"Plan record not found: {args.tool_plan_id}")
                        return 1
                    if isinstance(plan.metadata, dict):
                        gate = plan.metadata.get("execution_gate")
                        approval = plan.metadata.get("execution_approval")
                        if isinstance(approval, dict):
                            approval = {**approval, "plan_db_path": str(Path(args.plan_db))}

            # Build executor with explicit mutating opt-in; default remains read-only only.
            from digitalbrain.execution import default_tools
            all_tools = default_tools(Path(args.workspace).resolve())
            policy = ExecutionPolicy(
                allowed_tools=set(all_tools.keys()),
                allow_read_only=True,
                allow_mutating=bool(args.allow_mutating_tools),
            )
            executor = ToolExecutor(
                workspace_root=args.workspace,
                policy=policy,
                audit_log=audit,
                tools=all_tools,
                sandbox_mode=args.sandbox_mode,
                container_image=args.container_image,
                container_seccomp=args.container_seccomp,
                container_apparmor=args.container_apparmor,
                require_image_digest=bool(args.require_image_digest),
                host_job_limits=bool(args.host_job_limits),
                sandbox_policy=sandbox_policy,
            )

            result = executor.execute(args.run_tool, tool_args, execution_gate=gate, approval=approval)
            print(f"Tool: {result.tool}")
            print(f"Allowed: {result.allowed}")
            print(f"OK: {result.ok}")
            print(f"Policy: {result.policy_reason}")
            if result.error:
                print(f"Error: {result.error}")
            if result.output is not None:
                print(json.dumps(result.output, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if result.ok else 1
        finally:
            if audit is not None:
                audit.close()

    if args.list_audit:
        if not args.audit_db:
            parser.error("--list-audit requires --audit-db")
        with AuditLog(args.audit_db) as audit:
            events = audit.list_events(limit=args.limit)
            if not events:
                print("No audit events found.")
                return 0
            for e in events:
                print(f"[{e.created_at}] {e.id} {e.event_type} outcome={e.outcome} actor={e.actor}")
                if e.details:
                    print(f"  details: {e.details}")
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
                offset=args.offset,
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
        parser.error("goal is required unless a memory, knowledge, plan, or audit command is used")

    memory = SQLiteMemoryStore(args.memory_db) if args.memory_db else None
    knowledge = SQLiteKnowledgeStore(args.knowledge_db) if args.knowledge_db else None
    audit = AuditLog(args.audit_db) if args.audit_db else None
    plan_store = SQLitePlanStore(args.plan_db) if args.plan_db else None
    try:
        result = DigitalBrain(
            memory=memory,
            knowledge=knowledge,
            audit_log=audit,
            plan_store=plan_store,
        ).process_goal(args.goal)
    finally:
        if plan_store is not None:
            plan_store.close()
        if audit is not None:
            audit.close()
        if knowledge is not None:
            knowledge.close()
        if memory is not None:
            memory.close()

    print(f"Goal: {result.goal}")
    print(f"Status: {result.status.value}")
    if result.memory_record_id:
        print(f"Memory record: {result.memory_record_id}")
    if result.plan_record_id:
        print(f"Plan record: {result.plan_record_id}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    print("\nInitial plan:")
    for index, step in enumerate(result.plan, start=1):
        print(f"{index}. {step}")
    print(
        "\nNote: this prototype uses a deterministic baseline planner and optional "
        "SQLite memory/knowledge/audit. It does not yet perform autonomous reasoning, "
        "learning, tool execution, or self-modification."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
