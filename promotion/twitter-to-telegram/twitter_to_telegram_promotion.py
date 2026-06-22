#!/usr/bin/env python3
"""Config-driven Twitter/X → Telegram promotion CLI."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.config import load_config, load_env
from lib.log import setup_logging
from lib.promotion import NoPendingRows, PromotionError, delete_channel_posts, print_run_summary, run_promotion
from lib.status import print_status
from lib.validate import validate_all


def build_env(cfg) -> dict[str, str]:
    merged = load_env(cfg.config_dir / ".env")
    merged.update(os.environ)
    return merged


def cmd_validate(cfg, env) -> int:
    errors, warnings = validate_all(cfg, env)
    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}", file=sys.stderr)
    if errors:
        print(f"\nValidation failed ({len(errors)} error(s))", file=sys.stderr)
        return 1
    print("✅ Validation passed")
    if warnings:
        print(f"({len(warnings)} warning(s))")
    return 0


def cmd_status(cfg, env) -> int:
    print_status(cfg)
    return 0


def cmd_run(cfg, env, args) -> int:
    try:
        result = run_promotion(cfg, env, args.channel, dry_run=args.dry_run)
        print_run_summary(result)
        return 0
    except NoPendingRows as e:
        print(str(e))
        print("status=no_pending_rows")
        return 0
    except PromotionError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


def cmd_delete(cfg, env, args) -> int:
    try:
        delete_channel_posts(cfg, env, args.channel, args.post_index)
        return 0
    except PromotionError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Twitter/X to Telegram promotion")
    parser.add_argument("--config", default="config.json", help="Path to config file (default: ./config.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate config, env, CSV, and tools")

    sub.add_parser("status", help="Show channel state and resource counts")

    run_p = sub.add_parser("run", help="Run promotion for one channel")
    run_p.add_argument("--channel", required=True, help="Channel key from config")
    run_p.add_argument("--dry-run", action="store_true", help="Plan only; no side effects")

    del_p = sub.add_parser("delete", help="Delete posted Telegram messages")
    del_p.add_argument("--channel", required=True, help="Channel key from config")
    del_p.add_argument("--post-index", type=int, default=None, help="Delete only this post index")

    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (ROOT / config_path).resolve()

    try:
        cfg = load_config(config_path)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Failed to load config: {e}", file=sys.stderr)
        return 1

    env = build_env(cfg)

    handlers = {
        "validate": lambda: cmd_validate(cfg, env),
        "status": lambda: cmd_status(cfg, env),
        "run": lambda: cmd_run(cfg, env, args),
        "delete": lambda: cmd_delete(cfg, env, args),
    }
    return handlers[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
