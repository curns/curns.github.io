#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent
LOG_ROOT = REPO_ROOT / "local_logs"
STATE_FILE = LOG_ROOT / "activity_state.json"
LOG_NAME = "repo_activity"
ROOT_CONTENT_PAGES = {"about.md", "index.md", "archive.md", "contents.md"}


def monthly_log_dir(now: Optional[dt.datetime] = None) -> Path:
    now = now or dt.datetime.now()
    return LOG_ROOT / now.strftime("%Y-%m")


def monthly_log_path(now: Optional[dt.datetime] = None) -> Path:
    now = now or dt.datetime.now()
    month = now.strftime("%Y-%m")
    return monthly_log_dir(now) / f"{LOG_NAME}_{month}.log"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "event_counter": 0,
        "spellcheck_runs": 0,
        "commit_events": 0,
        "push_events": 0,
        "manual_events": 0,
    }


def save_state(state: dict) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def next_counter(key: str) -> tuple[dict, int, int]:
    state = load_state()
    state["event_counter"] = int(state.get("event_counter", 0)) + 1
    state[key] = int(state.get(key, 0)) + 1
    save_state(state)
    return state, int(state[key]), int(state["event_counter"])


def get_logger() -> logging.Logger:
    now = dt.datetime.now()
    log_path = monthly_log_path(now)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOG_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    target_path = str(log_path)
    existing_paths = {
        getattr(handler, "baseFilename", None)
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    }
    if target_path not in existing_paths:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def is_content_page(path_str: str) -> bool:
    path = Path(path_str)
    if path.name in ROOT_CONTENT_PAGES and len(path.parts) == 1:
        return True
    return "_posts" in path.parts and path.suffix == ".md"


def parse_name_status(output: str) -> dict:
    summary = {"added": [], "modified": [], "deleted": []}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        if not is_content_page(path):
            continue
        bucket = "modified"
        if status.startswith("A"):
            bucket = "added"
        elif status.startswith("D"):
            bucket = "deleted"
        summary[bucket].append(path)
    return summary


def working_tree_content_summary() -> dict:
    output = git("status", "--short", "--untracked-files=all", check=False)
    summary = {"added": [], "modified": [], "deleted": []}
    for raw_line in output.splitlines():
        if len(raw_line) < 4:
            continue
        status = raw_line[:2]
        path = raw_line[3:]
        if "->" in path:
            path = path.split("->", 1)[1].strip()
        if not is_content_page(path):
            continue
        if "??" in status or "A" in status:
            summary["added"].append(path)
        elif "D" in status:
            summary["deleted"].append(path)
        else:
            summary["modified"].append(path)
    return summary


def format_count_line(summary: dict) -> str:
    return (
        f"pages added={len(summary['added'])} "
        f"modified={len(summary['modified'])} "
        f"deleted={len(summary['deleted'])}"
    )


def log_spellcheck_run(summary: dict) -> None:
    logger = get_logger()
    _, run_number, event_number = next_counter("spellcheck_runs")
    logger.info(
        "------- SPELLCHECK RUN %s [Run %s] [Event %s] -------",
        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        run_number,
        event_number,
    )
    logger.info(
        "Spellcheck completed: pages_checked=%s issues=%s fixes=%s acceptable=%s style=%s template=%s",
        summary["pages_checked"],
        summary["issues"],
        summary["fixes"],
        summary["acceptable"],
        summary["style"],
        summary["template"],
    )
    logger.info(
        "Spellcheck options: include_index=%s include_archive=%s custom_words=%s",
        summary["include_index"],
        summary["include_archive"],
        summary["custom_words_file"],
    )
    logger.info("Spellcheck report written: %s", summary["report_path"])
    logger.info("Grouped spellcheck report written: %s", summary["grouped_report_path"])
    worktree = working_tree_content_summary()
    logger.info("Working tree snapshot: %s", format_count_line(worktree))
    if any(worktree.values()):
        logger.info(
            "Working tree pages: added=%s modified=%s deleted=%s",
            ", ".join(worktree["added"]) or "(none)",
            ", ".join(worktree["modified"]) or "(none)",
            ", ".join(worktree["deleted"]) or "(none)",
        )


def log_commit_event() -> int:
    logger = get_logger()
    _, commit_number, event_number = next_counter("commit_events")

    sha = git("rev-parse", "HEAD").strip()
    subject = git("log", "-1", "--pretty=%s").strip()
    status_output = git("show", "--name-status", "--format=", "--no-renames", "HEAD")
    summary = parse_name_status(status_output)

    logger.info(
        "------- COMMIT EVENT %s [Commit %s] [Event %s] -------",
        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        commit_number,
        event_number,
    )
    logger.info("Commit recorded: %s %s", sha[:12], subject)
    logger.info("Commit content summary: %s", format_count_line(summary))
    if any(summary.values()):
        logger.info(
            "Commit pages: added=%s modified=%s deleted=%s",
            ", ".join(summary["added"]) or "(none)",
            ", ".join(summary["modified"]) or "(none)",
            ", ".join(summary["deleted"]) or "(none)",
        )
    return 0


def empty_tree_sha() -> str:
    return git("hash-object", "-t", "tree", "/dev/null").strip()


def log_push_event(lines: list[str]) -> int:
    logger = get_logger()
    _, push_number, event_number = next_counter("push_events")
    logger.info(
        "------- PUSH EVENT %s [Push %s] [Event %s] -------",
        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        push_number,
        event_number,
    )

    if not lines:
        logger.info("Push event recorded with no ref data from hook stdin.")
        return 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        local_ref, local_sha, remote_ref, remote_sha = line.split()
        compare_base = remote_sha if set(remote_sha) != {"0"} else empty_tree_sha()
        diff_output = git("diff", "--name-status", compare_base, local_sha, check=False)
        summary = parse_name_status(diff_output)
        logger.info(
            "Push ref: local=%s remote=%s local_sha=%s remote_sha=%s",
            local_ref,
            remote_ref,
            local_sha[:12],
            remote_sha[:12] if remote_sha and set(remote_sha) != {"0"} else "(new)",
        )
        logger.info("Push content summary: %s", format_count_line(summary))
        if any(summary.values()):
            logger.info(
                "Push pages: added=%s modified=%s deleted=%s",
                ", ".join(summary["added"]) or "(none)",
                ", ".join(summary["modified"]) or "(none)",
                ", ".join(summary["deleted"]) or "(none)",
            )
        if remote_ref == "refs/heads/main":
            logger.info("Publish event: push to main detected, GitHub Pages republish likely triggered.")
    return 0


def log_manual_event(kind: str, message: str) -> int:
    logger = get_logger()
    _, note_number, event_number = next_counter("manual_events")
    logger.info(
        "------- MANUAL EVENT %s [%s %s] [Event %s] -------",
        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        kind.upper(),
        note_number,
        event_number,
    )
    logger.info("%s", message.strip())
    worktree = working_tree_content_summary()
    logger.info("Working tree snapshot: %s", format_count_line(worktree))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local activity logger for this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    spellcheck = subparsers.add_parser("spellcheck-run")
    spellcheck.add_argument("--pages-checked", type=int, required=True)
    spellcheck.add_argument("--issues", type=int, required=True)
    spellcheck.add_argument("--fixes", type=int, required=True)
    spellcheck.add_argument("--acceptable", type=int, required=True)
    spellcheck.add_argument("--style", type=int, required=True)
    spellcheck.add_argument("--template", type=int, required=True)
    spellcheck.add_argument("--include-index", action="store_true")
    spellcheck.add_argument("--include-archive", action="store_true")
    spellcheck.add_argument("--custom-words-file", required=True)
    spellcheck.add_argument("--report-path", required=True)
    spellcheck.add_argument("--grouped-report-path", required=True)

    subparsers.add_parser("post-commit")
    subparsers.add_parser("post-push")

    note = subparsers.add_parser("note")
    note.add_argument("--kind", default="note")
    note.add_argument("--message", required=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "spellcheck-run":
        log_spellcheck_run(
            {
                "pages_checked": args.pages_checked,
                "issues": args.issues,
                "fixes": args.fixes,
                "acceptable": args.acceptable,
                "style": args.style,
                "template": args.template,
                "include_index": args.include_index,
                "include_archive": args.include_archive,
                "custom_words_file": args.custom_words_file,
                "report_path": args.report_path,
                "grouped_report_path": args.grouped_report_path,
            }
        )
        return 0

    if args.command == "post-commit":
        return log_commit_event()

    if args.command == "post-push":
        return log_push_event(sys.stdin.read().splitlines())

    if args.command == "note":
        return log_manual_event(args.kind, args.message)

    return 1


if __name__ == "__main__":
    sys.exit(main())
