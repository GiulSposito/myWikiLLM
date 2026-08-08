#!/usr/bin/env python3
"""
batch_ingest.py — CLI for the batch ingest pipeline.

Usage:
  python3 scripts/batch_ingest.py scan      <directory> [--reingest-changed]
  python3 scripts/batch_ingest.py submit    <staging/batch>
  python3 scripts/batch_ingest.py status    <staging/batch>
  python3 scripts/batch_ingest.py collect   <staging/batch>
  python3 scripts/batch_ingest.py normalize <staging/batch>
  python3 scripts/batch_ingest.py resolve   <staging/batch>
  python3 scripts/batch_ingest.py curate    <staging/batch>
  python3 scripts/batch_ingest.py plan      <staging/batch>
  python3 scripts/batch_ingest.py apply     <staging/batch> --plan-confirmed
  python3 scripts/batch_ingest.py resume    <staging/batch>
  python3 scripts/batch_ingest.py run       <directory>   [--reingest-changed]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is in sys.path when called directly
_VAULT_ROOT = Path(__file__).parent.parent
if str(_VAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(_VAULT_ROOT))

from scripts.batch.config import load_config
from scripts.batch.state import BatchState, make_batch_id, STAGING_ROOT
from scripts.batch.scanner import scan_directory


# ---------------------------------------------------------------------------
# Subcommand: scan
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    from scripts.batch.progress import pipeline_header
    pipeline_header("Scan")

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"Error: directory does not exist: {directory}", file=sys.stderr)
        return 1

    results = scan_directory(directory, reingest_changed=args.reingest_changed)

    scanned = [r for r in results if r.status == "scanned"]
    skipped = [r for r in results if r.status == "skipped_duplicate"]
    changed = [r for r in results if r.status == "changed-source"]

    print(f"Discovered:        {len(results):>6}")
    print(f"Already ingested:  {len(skipped):>6}")
    print(f"Changed sources:   {len(changed):>6}")
    print(f"Ready:             {len(scanned):>6}")

    if changed and not args.reingest_changed:
        print()
        print("Changed sources require --reingest-changed to process:")
        for r in changed:
            print(f"  {r.path.relative_to(directory)}")

    if not scanned:
        print("\nNothing to process.")
        return 0

    # Create batch state
    cfg = load_config()
    batch_id = make_batch_id(directory)
    batch_dir = STAGING_ROOT / batch_id

    if batch_dir.exists():
        print(f"\nBatch already exists: {batch_dir}")
        print("Use 'resume' to continue or delete the staging directory to restart.")
        return 1

    state = BatchState.create(
        batch_id,
        extraction_model=cfg.models.extraction,
        resolution_model=cfg.models.resolution,
        curation_model=cfg.models.curation,
    )

    from scripts.batch.state import BatchItem
    for r in results:
        rel_path = str(r.path.relative_to(_VAULT_ROOT))
        item = BatchItem(
            source_key=r.source_key,
            custom_id=r.custom_id,
            files=[rel_path],
            sha256=r.sha256,
            status=r.status,
            duplicate_of=r.duplicate_of,
        )
        state.add_item(item)

    state.save()
    print(f"\nBatch created: {batch_dir}")
    print(f"Batch ID: {batch_id}")
    print(f"\nNext step: python3 scripts/batch_ingest.py submit {batch_dir}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: submit
# ---------------------------------------------------------------------------

def cmd_submit(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    from scripts.batch.config import resolve_model_names
    from scripts.batch.progress import pipeline_header
    pipeline_header("Extract")
    cfg = load_config()
    resolve_model_names(cfg)
    items_to_submit = state.items_by_status("scanned")
    if not items_to_submit:
        print("No items in 'scanned' status. Nothing to submit.")
        return 0

    if cfg.provider == "litellm":
        try:
            from scripts.batch.litellm_sync import run_extraction_sync
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Provider: litellm (synchronous, {len(items_to_submit)} items)")
        collected, failed = run_extraction_sync(items_to_submit, state, cfg, _VAULT_ROOT)
        state.save()
        print(f"Extracted: {collected}  Failed: {failed}")
        if collected:
            print(f"\nNext step: python3 scripts/batch_ingest.py normalize {batch_dir}")
        return 0 if failed == 0 else 1

    # Default: Anthropic Message Batches API
    try:
        from scripts.batch.extractor import build_extraction_requests
        from scripts.batch.anthropic_batch import submit_extraction_batch
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Building {len(items_to_submit)} extraction requests...")
    requests = build_extraction_requests(items_to_submit, cfg, _VAULT_ROOT)

    print("Submitting extraction batch...")
    provider_batch_ids = submit_extraction_batch(requests, state, cfg)

    state.save()

    if provider_batch_ids == ["sync-fallback"]:
        extracted = len(state.items_by_status("extracted"))
        failed = len(state.items_by_status("failed_extraction"))
        print(f"Sync extraction complete: {extracted} extracted, {failed} failed")
        if extracted:
            print(f"\nNext step: python3 scripts/batch_ingest.py normalize {batch_dir}")
    else:
        for bid in provider_batch_ids:
            print(f"  Provider batch: {bid}")
        print(f"\nCheck status with: python3 scripts/batch_ingest.py status {batch_dir}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    try:
        from scripts.batch.anthropic_batch import check_batch_status
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    for batch_type, batch_ids in state.provider_batches.items():
        for bid in batch_ids:
            status = check_batch_status(bid)
            print(f"[{batch_type}] {bid}: {status.get('processing_status', 'unknown')}"
                  f" ({status.get('request_counts', {})})")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: collect
# ---------------------------------------------------------------------------

def cmd_collect(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    try:
        from scripts.batch.anthropic_batch import collect_extraction_results
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    collected, failed = collect_extraction_results(state, _VAULT_ROOT)
    print(f"Collected: {collected}, Failed: {failed}")
    state.save()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: normalize
# ---------------------------------------------------------------------------

def cmd_normalize(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    try:
        from scripts.batch.normalizer import normalize_batch
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    from scripts.batch.progress import pipeline_header
    pipeline_header("Normalize")
    count = normalize_batch(state, _VAULT_ROOT)
    print(f"Normalized: {count} items")
    state.save()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: resolve
# ---------------------------------------------------------------------------

def cmd_resolve(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    try:
        from scripts.batch.resolver import resolve_batch
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    from scripts.batch.config import resolve_model_names
    from scripts.batch.progress import pipeline_header
    pipeline_header("Resolve")
    cfg = load_config()
    resolve_model_names(cfg)
    resolved, deferred = resolve_batch(state, cfg, _VAULT_ROOT)
    print(f"Resolved: {resolved}, Deferred: {deferred}")
    state.save()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: curate
# ---------------------------------------------------------------------------

def cmd_curate(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    try:
        from scripts.batch.grouper import group_evidence
        from scripts.batch.curator import run_curation_batch
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    from scripts.batch.config import resolve_model_names
    from scripts.batch.progress import pipeline_header
    pipeline_header("Curate")
    cfg = load_config()
    resolve_model_names(cfg)
    groups = group_evidence(state, _VAULT_ROOT)
    print(f"Groups to curate: {len(groups)}")
    plans = run_curation_batch(groups, state, cfg, _VAULT_ROOT)
    print(f"Mutation plans produced: {len(plans)}")
    state.save()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: plan (dry-run)
# ---------------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    try:
        from scripts.batch.planner import build_update_plan, print_plan_summary
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    from scripts.batch.progress import pipeline_header
    pipeline_header("Plan")
    plan = build_update_plan(state, _VAULT_ROOT)
    print_plan_summary(plan)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: apply
# ---------------------------------------------------------------------------

def cmd_apply(args: argparse.Namespace) -> int:
    if not args.plan_confirmed:
        print("Error: --plan-confirmed flag required. Review the plan first with the 'plan' subcommand.",
              file=sys.stderr)
        return 1

    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    cfg = load_config()

    if cfg.apply.require_clean_git:
        import subprocess
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=_VAULT_ROOT,
        )
        if result.stdout.strip():
            print("Error: working tree is not clean. Commit or stash changes before applying.",
                  file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            return 1

    try:
        from scripts.batch.qa import run_qa_checks
        from scripts.batch.writer import apply_update_plan
        from scripts.batch.planner import build_update_plan
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    from scripts.batch.progress import pipeline_header
    pipeline_header("Apply")
    plan = build_update_plan(state, _VAULT_ROOT)

    qa_ok, qa_report = run_qa_checks(plan, state, _VAULT_ROOT)
    if not qa_ok:
        print("QA checks failed. Aborting apply.")
        print(qa_report)
        return 1

    apply_update_plan(plan, state, cfg, _VAULT_ROOT)
    state.save()
    print("Apply complete.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: resume
# ---------------------------------------------------------------------------

def cmd_resume(args: argparse.Namespace) -> int:
    """Auto-detect next step and execute it."""
    batch_dir = Path(args.batch).resolve()
    state = _load_state(batch_dir)
    if state is None:
        return 1

    # Determine next step by checking for items still pending in each stage
    if state.items_by_status("scanned"):
        print("Next step: submit")
        args.batch = str(batch_dir)
        return cmd_submit(args)

    if state.items_by_status("submitted"):
        extraction_batches = state.provider_batches.get("extraction", [])
        if extraction_batches:
            print("Next step: collect")
            return cmd_collect(args)

    if state.items_by_status("extracted"):
        print("Next step: normalize")
        return cmd_normalize(args)

    if state.items_by_status("normalized"):
        print("Next step: resolve")
        return cmd_resolve(args)

    if state.items_by_status("resolved"):
        print("Next step: curate")
        return cmd_curate(args)

    update_plan_path = batch_dir / "update-plan.json"
    if not update_plan_path.exists():
        print("Next step: plan")
        return cmd_plan(args)

    print("Batch is ready to apply. Review the update plan then run:")
    print(f"  python3 scripts/batch_ingest.py apply {batch_dir} --plan-confirmed")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: run (end-to-end)
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    """Full pipeline: scan → submit → wait → collect → normalize → resolve → curate → plan."""
    directory = Path(args.directory).resolve()

    # scan
    scan_args = argparse.Namespace(
        directory=str(directory),
        reingest_changed=getattr(args, "reingest_changed", False),
    )
    rc = cmd_scan(scan_args)
    if rc != 0:
        return rc

    # derive batch_dir
    from scripts.batch.state import make_batch_id
    batch_id = make_batch_id(directory)
    batch_dir = STAGING_ROOT / batch_id

    resume_args = argparse.Namespace(batch=str(batch_dir))

    import time

    # submit
    rc = cmd_submit(argparse.Namespace(batch=str(batch_dir)))
    if rc != 0:
        return rc

    # collect — only needed for async batches (skip sync-fallback)
    st = BatchState.load(batch_dir)
    async_batches = [
        bid for bid in st.provider_batches.get("extraction", [])
        if bid != "sync-fallback"
    ]
    if async_batches:
        print("Waiting for extraction to complete...")
        from scripts.batch.anthropic_batch import check_batch_status
        while True:
            all_done = all(
                check_batch_status(bid).get("processing_status") == "ended"
                for bid in async_batches
            )
            if all_done:
                break
            time.sleep(30)
        rc = cmd_collect(argparse.Namespace(batch=str(batch_dir)))
        if rc != 0:
            return rc

    # normalize → resolve → curate → plan
    for step_fn in (cmd_normalize, cmd_resolve, cmd_curate, cmd_plan):
        rc = step_fn(argparse.Namespace(batch=str(batch_dir)))
        if rc != 0:
            return rc

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state(batch_dir: Path) -> BatchState | None:
    try:
        return BatchState.load(batch_dir)
    except FileNotFoundError:
        print(f"Error: no batch found at {batch_dir}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="batch_ingest",
        description="Batch ingestion pipeline for myWikiLLM vault",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="Discover and classify source files")
    p_scan.add_argument("directory", help="Directory containing transcripts")
    p_scan.add_argument("--reingest-changed", action="store_true",
                        help="Allow re-ingesting changed sources")
    p_scan.set_defaults(func=cmd_scan)

    # submit
    p_submit = sub.add_parser("submit", help="Submit extraction batch to Anthropic")
    p_submit.add_argument("batch", help="Path to staging/batch directory")
    p_submit.set_defaults(func=cmd_submit)

    # status
    p_status = sub.add_parser("status", help="Check provider batch status")
    p_status.add_argument("batch", help="Path to staging/batch directory")
    p_status.set_defaults(func=cmd_status)

    # collect
    p_collect = sub.add_parser("collect", help="Collect extraction results from Anthropic")
    p_collect.add_argument("batch", help="Path to staging/batch directory")
    p_collect.set_defaults(func=cmd_collect)

    # normalize
    p_normalize = sub.add_parser("normalize", help="Normalize and dedup entity/concept mentions")
    p_normalize.add_argument("batch", help="Path to staging/batch directory")
    p_normalize.set_defaults(func=cmd_normalize)

    # resolve
    p_resolve = sub.add_parser("resolve", help="Resolve mentions to canonical wiki pages")
    p_resolve.add_argument("batch", help="Path to staging/batch directory")
    p_resolve.set_defaults(func=cmd_resolve)

    # curate
    p_curate = sub.add_parser("curate", help="Run curation batch to produce mutation plans")
    p_curate.add_argument("batch", help="Path to staging/batch directory")
    p_curate.set_defaults(func=cmd_curate)

    # plan
    p_plan = sub.add_parser("plan", help="Dry-run: show update plan without writing")
    p_plan.add_argument("batch", help="Path to staging/batch directory")
    p_plan.set_defaults(func=cmd_plan)

    # apply
    p_apply = sub.add_parser("apply", help="Apply update plan to wiki (destructive)")
    p_apply.add_argument("batch", help="Path to staging/batch directory")
    p_apply.add_argument("--plan-confirmed", action="store_true",
                         help="Required: confirms you have reviewed the update plan")
    p_apply.set_defaults(func=cmd_apply)

    # resume
    p_resume = sub.add_parser("resume", help="Auto-detect and execute next pipeline step")
    p_resume.add_argument("batch", help="Path to staging/batch directory")
    p_resume.set_defaults(func=cmd_resume)

    # run
    p_run = sub.add_parser("run", help="End-to-end: scan through plan")
    p_run.add_argument("directory", help="Directory containing transcripts")
    p_run.add_argument("--reingest-changed", action="store_true")
    p_run.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
