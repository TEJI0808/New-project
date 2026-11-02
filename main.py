#!/usr/bin/env python3
"""System Health Monitor & Security Auditing Daemon."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from modules.config import ConfigError, load_config, apply_cli_overrides
from modules.security import SecurityError, check_identity, add_delegate, remove_delegate, list_delegates
from modules.logging_system import setup_logging
from modules.monitoring import check_storage
from modules.audit import process_audit_files, prune_old_archives, get_archive_summary

EXIT_SUCCESS = 0
EXIT_GENERIC_ERROR = 1
EXIT_IDENTITY_VIOLATION = 2
EXIT_CONFIGURATION_MISSING = 3
EXIT_INVALID_WORKSPACE = 4
EXIT_DISK_CEILING_REACHED = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sysaudit",
        description=(
            "System Health Monitor & Security Auditing Daemon. "
            "With no arguments, this help is displayed. The service runs with --daemon."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  python3 main.py --once
  python3 main.py --once --workspace ./demo_audit
  python3 main.py --daemon
  python3 main.py --delegate-user alice
  python3 main.py --list-delegates
  python3 main.py --revoke-delegate alice

Configuration file:
  sysaudit.cfg (INI format). The --config option selects another file.
  Command-line settings override the config file for this run only.

Exit codes:
  0  SUCCESS
  1  GENERIC_ERROR
  2  IDENTITY_VIOLATION
  3  CONFIGURATION_MISSING
  4  INVALID_WORKSPACE
  5  DISK_CEILING_REACHED
"""
    )
    parser.add_argument("--config", default=str(Path(__file__).with_name("sysaudit.cfg")),
                        help="Path to the INI configuration file.")
    parser.add_argument("--once", action="store_true",
                        help="Run one maintenance cycle immediately, then exit.")
    parser.add_argument("--daemon", action="store_true",
                        help="Run continuously and perform maintenance at midnight every N days.")
    parser.add_argument("--workspace", help="Override audit workspace for this run.")
    parser.add_argument("--log-file", help="Override log file for this run.")
    parser.add_argument("--max-storage-mb", type=float, help="Override storage ceiling for this run.")
    parser.add_argument("--retention-days", type=int, help="Override archive retention for this run.")
    parser.add_argument("--interval-days", type=int, help="Override daemon interval for this run.")
    parser.add_argument("--delegate-user", metavar="USERNAME",
                        help="Register a local Linux account as a delegated user (run as auditmanager).")
    parser.add_argument("--revoke-delegate", metavar="USERNAME",
                        help="Remove a delegated local Linux account (run as auditmanager).")
    parser.add_argument("--list-delegates", action="store_true",
                        help="List delegated accounts (run as auditmanager).")
    return parser


def run_cycle(config, logger) -> int:
    workspace = Path(config["paths"]["workspace"])
    if not workspace.exists() or not workspace.is_dir():
        logger.error("Invalid workspace: %s", workspace)
        print(f"ERROR: invalid workspace: {workspace}", file=sys.stderr)
        return EXIT_INVALID_WORKSPACE

    try:
        size_bytes, over_limit = check_storage(config, logger)
        if over_limit:
            logger.warning(
                "Storage ceiling exceeded: %.2f MB used; limit is %.2f MB",
                size_bytes / (1024 * 1024), config["storage"]["max_storage_mb"]
            )
            if config["storage"].get("stop_on_limit", False):
                print("ERROR: storage ceiling reached.", file=sys.stderr)
                return EXIT_DISK_CEILING_REACHED

        result = process_audit_files(config, logger)
        prune_old_archives(config, logger)
        summary = get_archive_summary(config, logger)

        logger.info(
            "Cycle complete. Raw files archived=%s; archives=%s; largest=%s; largest_bytes=%s; largest_mtime=%s",
            result["archived_count"], summary["archive_count"], summary["largest_name"],
            summary["largest_size_bytes"], summary["largest_modified"]
        )
        return EXIT_SUCCESS
    except Exception as exc:
        logger.exception("Maintenance cycle failed: %s", exc)
        print(f"ERROR: maintenance cycle failed: {exc}", file=sys.stderr)
        return EXIT_GENERIC_ERROR


def next_midnight(now: datetime) -> datetime:
    tomorrow = now.date() + timedelta(days=1)
    return datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)


def daemon_loop(config, logger) -> int:
    """Run first at the next midnight, then every configured interval; catch up if overdue."""
    state_file = Path(config["paths"]["state_file"])
    interval = int(config["schedule"]["interval_days"])
    last_run = None

    if state_file.exists():
        try:
            raw = state_file.read_text(encoding="utf-8").strip()
            if raw:
                last_run = datetime.fromisoformat(raw)
                if last_run.tzinfo is None:
                    last_run = last_run.astimezone()
        except Exception:
            logger.warning("Could not read last-run state; schedule will restart from next midnight.")

    now = datetime.now().astimezone()
    due = next_midnight(now) if last_run is None else last_run + timedelta(days=interval)

    logger.info("Daemon started. Next maintenance time: %s", due.isoformat())
    while True:
        now = datetime.now().astimezone()
        if now >= due:
            logger.info("Scheduled maintenance loop starting.")
            code = run_cycle(config, logger)
            if code == EXIT_SUCCESS:
                state_file.parent.mkdir(parents=True, exist_ok=True)
                state_file.write_text(datetime.now().astimezone().isoformat(), encoding="utf-8")
                due = datetime.now().astimezone() + timedelta(days=interval)
                # Keep the next run at midnight local time.
                due = due.replace(hour=0, minute=0, second=0, microsecond=0)
                if due <= datetime.now().astimezone():
                    due += timedelta(days=1)
                logger.info("Next maintenance time: %s", due.isoformat())
            else:
                logger.error("Scheduled cycle failed with exit code %s; retrying in 15 minutes.", code)
                time.sleep(900)
                continue
        time.sleep(min(30, max(1, (due - datetime.now().astimezone()).total_seconds())))


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # argparse help exits before identity validation. No arguments also prints help.
    if argv is None and len(sys.argv) == 1:
        parser.print_help()
        return EXIT_SUCCESS

    try:
        config = load_config(args.config)
        config = apply_cli_overrides(config, args)
    except FileNotFoundError as exc:
        print(f"ERROR: configuration file not found: {exc}", file=sys.stderr)
        return EXIT_CONFIGURATION_MISSING
    except ConfigError as exc:
        print(f"ERROR: invalid configuration: {exc}", file=sys.stderr)
        return EXIT_CONFIGURATION_MISSING

    try:
        check_identity(config)
        if args.delegate_user:
            add_delegate(args.delegate_user, config)
            print(f"Delegated access registered for: {args.delegate_user}")
            return EXIT_SUCCESS
        if args.revoke_delegate:
            remove_delegate(args.revoke_delegate, config)
            print(f"Delegated access removed for: {args.revoke_delegate}")
            return EXIT_SUCCESS
        if args.list_delegates:
            for username in list_delegates(config):
                print(username)
            return EXIT_SUCCESS
    except SecurityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_IDENTITY_VIOLATION

    if not args.once and not args.daemon:
        parser.print_help()
        return EXIT_SUCCESS

    try:
        logger = setup_logging(config)
    except Exception as exc:
        print(f"ERROR: cannot initialize log: {exc}", file=sys.stderr)
        return EXIT_GENERIC_ERROR

    if args.once:
        return run_cycle(config, logger)
    try:
        return daemon_loop(config, logger)
    except KeyboardInterrupt:
        logger.info("Daemon stopped by keyboard interrupt.")
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
