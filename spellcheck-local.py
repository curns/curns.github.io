#!/usr/bin/env python3

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import warnings
from pathlib import Path
from urllib.parse import quote

warnings.filterwarnings(
    "ignore",
    message=r".*urllib3 v2 only supports OpenSSL 1\.1\.1\+.*",
)

try:
    import language_tool_python
except ImportError as exc:
    raise SystemExit(
        "language_tool_python is required. Install the MusakChecker requirements first."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parent
REPORT_DIR = REPO_ROOT / "local_reports"
DEFAULT_REPORT = REPORT_DIR / "spellcheck-report.html"
DEFAULT_GROUPED_REPORT = REPORT_DIR / "spellcheck-grouped.html"
MUSAK_CUSTOM_WORDS_FILE = (
    Path.home() / "Documents" / "Codex" / "MusakChecker" / "custom_words.txt"
)
DEFAULT_CUSTOM_WORDS = {"weeknotes", "prioritising"}
DEFAULT_ROOT_PAGES = ("about.md", "contents.md")
OPTIONAL_ROOT_PAGES = ("index.md", "archive.md")
SKIP_DIRS = {"vendor", "_site", ".git", "category", "year"}
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
AUTO_LINK_RE = re.compile(r"<(https?://[^>]+)>")
RAW_URL_RE = re.compile(r"https?://\S+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HTML_TAG_RE = re.compile(r"<[^>]+>")
FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
WORD_RE = re.compile(r"[\w'’\-]+", re.UNICODE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spell-check the explicit Jekyll content pages in this repo."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_REPORT),
        help="HTML report destination. Defaults to local_reports/spellcheck-report.html",
    )
    parser.add_argument(
        "--grouped-output",
        default=str(DEFAULT_GROUPED_REPORT),
        help="Grouped HTML review destination. Defaults to local_reports/spellcheck-grouped.html",
    )
    parser.add_argument(
        "--editor-url-template",
        default=os.environ.get("SPELLCHECK_EDITOR_URL_TEMPLATE", ""),
        help=(
            "Optional editor URL template for one-click editing. "
            "Supported placeholders: {path}, {path_url}, {line}"
        ),
    )
    parser.add_argument(
        "--include-index",
        action="store_true",
        help="Include index.md in the spell check run.",
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Include archive.md in the spell check run.",
    )
    parser.add_argument(
        "--entry-path",
        default="",
        help="Optional single Markdown path to spell-check instead of the default repo scan.",
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="Emit a JSON summary for the checked entries instead of writing HTML reports.",
    )
    return parser.parse_args()


def normalize_word(value: str) -> str:
    return value.strip().strip(".,;:!?()[]{}\"'“”’`").lower()


def load_custom_words() -> set[str]:
    words = set(DEFAULT_CUSTOM_WORDS)
    if MUSAK_CUSTOM_WORDS_FILE.exists():
        for raw_line in MUSAK_CUSTOM_WORDS_FILE.read_text(encoding="utf-8").splitlines():
            word = raw_line.strip()
            if word and not word.startswith("#"):
                words.add(word.lower())
    return words


def find_entries(args: argparse.Namespace) -> list[Path]:
    if args.entry_path:
        target = Path(args.entry_path).expanduser()
        if not target.is_absolute():
            target = (REPO_ROOT / target).resolve()
        if not target.exists():
            raise SystemExit(f"Entry path does not exist: {target}")
        return [target]

    entries: list[Path] = []
    root_pages = list(DEFAULT_ROOT_PAGES)
    if args.include_index:
        root_pages.append("index.md")
    if args.include_archive:
        root_pages.append("archive.md")

    for name in root_pages:
        path = REPO_ROOT / name
        if path.exists():
            entries.append(path)

    for path in sorted(REPO_ROOT.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT)
        parts = set(rel.parts)
        if parts & SKIP_DIRS:
            continue
        if rel.name in DEFAULT_ROOT_PAGES or rel.name in OPTIONAL_ROOT_PAGES:
            continue
        if "_posts" in rel.parts:
            entries.append(path)
    return sorted(entries)


def parse_front_matter_and_body(text: str) -> tuple[dict[str, str], str]:
    front_matter: dict[str, str] = {}
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return front_matter, text

    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        front_matter[key.strip()] = value.strip().strip("'\"")
    return front_matter, text[match.end() :]


def markdown_to_plain_text(body: str) -> str:
    text = body.replace("\r\n", "\n")
    text = HTML_COMMENT_RE.sub("\n", text)
    text = CODE_FENCE_RE.sub("\n", text)
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = IMAGE_RE.sub(r"\1", text)
    text = LINK_RE.sub(r"\1", text)
    text = AUTO_LINK_RE.sub(r"\1", text)
    text = RAW_URL_RE.sub("", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"^\s{0,3}#+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = text.replace("*", "")
    text = text.replace("_", " ")
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def issue_word(issue, text: str) -> str:
    matched = getattr(issue, "matchedText", "") or ""
    if matched:
        return matched

    offset = getattr(issue, "offset", None)
    length = (
        getattr(issue, "errorLength", None)
        or getattr(issue, "error_length", None)
        or getattr(issue, "length", None)
    )
    if offset is None or length is None:
        return ""
    return text[offset : offset + length]


def line_for_offset(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text[:offset].count("\n") + 1


def build_editor_url(template: str, path: Path, line: int) -> str:
    if not template:
        return ""
    return template.format(
        path=str(path),
        path_url=quote(str(path), safe="/"),
        line=line,
    )


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def route_for_path(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT)
    if rel.name == "index.md":
        return "/"
    if rel.parts[-2:-1] == ("_posts",):
        slug = rel.stem
        year, month, day, rest = slug.split("-", 3)
        section = rel.parts[0].lower()
        return f"/{section}/{year}/{month}/{day}/{rest}.html"
    return f"/{rel.stem}.html"


STYLE_RULE_PREFIXES = (
    "COMMA_COMPOUND_SENTENCE",
    "EN_COMPOUNDS_",
)
STYLE_RULES = {
    "OXFORD_SPELLING_Z_NOT_S",
    "ENGLISH_WORD_REPEAT_BEGINNING_RULE",
    "ENGLISH_WORD_REPEAT_RULE",
    "RECOMMENDED_COMPOUNDS",
    "SEND_PRP_AN_EMAIL",
    "NOT_SURE_IT_WORKS",
    "EN_GB_SIMPLE_REPLACE_VACATION",
    "IN_A_X_MANNER",
    "THERE_RE_CONTRACTION_UNCOMMON",
}
TEMPLATE_WORDS = {
    "endfor",
    "endif",
    "%d",
    "%b",
    "%y",
    "star",
    "title",
    "date",
    "posts",
    "categories",
    "items",
    "site",
}
ACCEPTABLE_WORDS = {
    "time out",
    "understage",
    "mansell",
    "brundle",
    "finnair",
    "scallies",
    "middle-englandness",
    "shirls",
    "youtubed",
    "euston",
    "allaire",
    "homesite",
    "icra",
    "notsosoft",
    "trabaca",
    "posterboy",
    "eric",
    "photoblog",
    "overyourhead",
    "hammersley",
    "bloggety",
    "soho",
    "fuddland",
    "airwaves",
    "wm",
    "starmakers",
    "lynam",
    "buerk",
    "jenni",
    "newsnight",
    "paul heiney",
    "darke",
    "hemmings",
    "juste",
    "witchell",
    "klingenfelt",
    "macneil",
}


def classify_issue(entry: dict, issue: dict) -> str:
    path = str(entry["path"].relative_to(REPO_ROOT))
    word = (issue["word"] or "").lower()
    rule = issue["rule_id"]

    if path in {"archive.md", "index.md"}:
        if rule in {"WHITESPACE_RULE", "LC_AFTER_PERIOD"}:
            return "template"
        if rule == "MORFOLOGIK_RULE_EN_GB" and word in TEMPLATE_WORDS:
            return "template"
        if rule == "THERE_RE_MANY" and word == "site":
            return "template"

    if word in {"the what"}:
        return "acceptable"

    if word in {"uk", "selction", "guiding principal", "many other website", "the you", "nee"}:
        return "fix"

    if word in ACCEPTABLE_WORDS:
        return "acceptable"

    if rule in STYLE_RULES or any(rule.startswith(prefix) for prefix in STYLE_RULE_PREFIXES):
        return "style"

    if rule in {"WHITESPACE_RULE", "CONSECUTIVE_SPACES", "LC_AFTER_PERIOD", "EN_UNPAIRED_BRACKETS", "EN_UNPAIRED_QUOTES", "COMMA_PARENTHESIS_WHITESPACE"}:
        return "fix"

    if rule in {"MORFOLOGIK_RULE_EN_GB", "EN_MULTITOKEN_SPELLING_TWO"}:
        return "fix"

    return "fix"


def check_entry(path: Path, tool, custom_words: set[str]) -> dict:
    raw_text = path.read_text(encoding="utf-8")
    front_matter, body = parse_front_matter_and_body(raw_text)
    title = front_matter.get("title") or path.stem
    plain_text = markdown_to_plain_text(body)
    matches = []
    for issue in tool.check(plain_text):
        word = normalize_word(issue_word(issue, plain_text))
        if word and word in custom_words:
            continue
        offset = getattr(issue, "offset", 0) or 0
        line = line_for_offset(plain_text, offset)
        replacements = getattr(issue, "replacements", None) or []
        replacements_text = ", ".join(replacements[:5])
        matches.append(
            {
                "rule_id": getattr(issue, "ruleId", "") or getattr(issue, "rule_id", ""),
                "message": (getattr(issue, "message", "") or getattr(issue, "msg", "")).strip(),
                "context": (getattr(issue, "context", "") or "").strip(),
                "word": word or issue_word(issue, plain_text).strip(),
                "line": line,
                "replacements": replacements_text,
            }
        )

    return {
        "path": path,
        "title": title,
        "route": route_for_path(path),
        "issues": matches,
        "word_count": len(WORD_RE.findall(plain_text)),
    }


def render_html(report_path: Path, entries: list[dict], editor_template: str, custom_words: set[str]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    total_issues = sum(len(entry["issues"]) for entry in entries)
    checked_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    editor_note = (
        "Editor links are enabled from SPELLCHECK_EDITOR_URL_TEMPLATE."
        if editor_template
        else (
            "Editor links are not enabled. Browsers can open a file:// link, but they cannot "
            "edit and save Markdown back into the repo by themselves. For one-click editing, rerun "
            "with SPELLCHECK_EDITOR_URL_TEMPLATE set to something like "
            "'vscode://file/{path_url}:{line}' or another editor URL scheme you use."
        )
    )

    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("<!doctype html>\n<html><head><meta charset='utf-8'>\n")
        handle.write("<title>Local Spell Check Report</title>\n")
        handle.write(
            """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #222; }
h1, h2, h3 { margin-bottom: 0.35rem; }
.meta { color: #666; margin-bottom: 1rem; }
.entry { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin: 18px 0; }
.entry.clean { border-color: #cfe7cf; background: #f7fcf7; }
.links a { margin-right: 12px; }
.path { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 0.92rem; }
table { width: 100%; border-collapse: collapse; margin-top: 12px; }
th, td { text-align: left; vertical-align: top; padding: 8px; border-top: 1px solid #e5e5e5; }
th { font-size: 0.9rem; color: #555; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #f0f0f0; font-size: 0.85rem; }
.ok { color: #1d6b2c; }
.warn { color: #8a5a00; }
</style>
"""
        )
        handle.write("</head><body>\n")
        handle.write("<h1>Local Spell Check Report</h1>\n")
        handle.write(
            f"<div class='meta'>Generated {html.escape(checked_at)}. "
            f"Checked {len(entries)} explicit pages and found {total_issues} issues.</div>\n"
        )
        handle.write(
            f"<div class='meta'>Shared custom words file: "
            f"<a href='{html.escape(file_url(MUSAK_CUSTOM_WORDS_FILE))}'>"
            f"{html.escape(str(MUSAK_CUSTOM_WORDS_FILE))}</a> "
            f"({len(custom_words)} words loaded).</div>\n"
        )
        handle.write(f"<div class='meta'>{html.escape(editor_note)}</div>\n")

        for entry in entries:
            path = entry["path"]
            source_url = file_url(path)
            local_page = f"http://127.0.0.1:4000{entry['route']}"
            issue_count = len(entry["issues"])
            css_class = "entry clean" if issue_count == 0 else "entry"
            handle.write(f"<section class='{css_class}'>\n")
            handle.write(f"<h2>{html.escape(entry['title'])}</h2>\n")
            handle.write(
                f"<div class='path'>{html.escape(str(path.relative_to(REPO_ROOT)))}</div>\n"
            )
            handle.write(
                f"<div class='meta'>Words checked: {entry['word_count']} "
                f"&nbsp;|&nbsp; Issues: {issue_count}</div>\n"
            )
            handle.write("<div class='links'>")
            handle.write(f"<a href='{html.escape(source_url)}'>Open source file</a>")
            handle.write(
                f"<a href='{html.escape(local_page)}' target='_blank' rel='noopener'>Open local page</a>"
            )
            if issue_count:
                first_line = entry["issues"][0]["line"]
            else:
                first_line = 1
            editor_url = build_editor_url(editor_template, path, first_line)
            if editor_url:
                handle.write(f"<a href='{html.escape(editor_url)}'>Edit in configured editor</a>")
            handle.write("</div>\n")

            if not entry["issues"]:
                handle.write("<p class='ok'>No spelling or grammar issues found for this entry.</p>\n")
                handle.write("</section>\n")
                continue

            handle.write("<table>\n")
            handle.write(
                "<thead><tr><th>Line</th><th>Word</th><th>Rule</th><th>Message</th>"
                "<th>Context</th><th>Suggestions</th></tr></thead><tbody>\n"
            )
            for issue in entry["issues"]:
                line = issue["line"]
                issue_editor_url = build_editor_url(editor_template, path, line)
                line_html = str(line)
                if issue_editor_url:
                    line_html = f"<a href='{html.escape(issue_editor_url)}'>{line}</a>"
                handle.write("<tr>")
                handle.write(f"<td>{line_html}</td>")
                handle.write(f"<td><span class='pill'>{html.escape(issue['word'] or '(n/a)')}</span></td>")
                handle.write(f"<td>{html.escape(issue['rule_id'])}</td>")
                handle.write(f"<td>{html.escape(issue['message'])}</td>")
                handle.write(f"<td>{html.escape(issue['context'])}</td>")
                handle.write(f"<td>{html.escape(issue['replacements'])}</td>")
                handle.write("</tr>\n")
            handle.write("</tbody></table>\n")
            handle.write("</section>\n")

        handle.write("</body></html>\n")


def render_grouped_html(report_path: Path, entries: list[dict], editor_template: str) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checked_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    totals = {"fix": 0, "acceptable": 0, "style": 0, "template": 0}

    grouped_entries = []
    for entry in entries:
        grouped = {"fix": [], "acceptable": [], "style": [], "template": []}
        for issue in entry["issues"]:
            bucket = classify_issue(entry, issue)
            grouped[bucket].append(issue)
            totals[bucket] += 1
        grouped_entries.append((entry, grouped))

    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("<!doctype html><html><head><meta charset='utf-8'>\n")
        handle.write("<title>Grouped Spell Check Review</title>\n")
        handle.write(
            """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #222; }
.meta { color: #666; margin-bottom: 1rem; }
.entry { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin: 18px 0; }
.bucket { margin-top: 12px; }
.bucket h3 { margin-bottom: 0.35rem; }
.bucket ul { margin-top: 0.25rem; }
.links a { margin-right: 12px; }
.path { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 0.92rem; }
.fix h3 { color: #8a1c1c; }
.acceptable h3 { color: #1d5f8a; }
.style h3 { color: #7b5a00; }
.template h3 { color: #555; }
</style>
"""
        )
        handle.write("</head><body>\n")
        handle.write("<h1>Grouped Spell Check Review</h1>\n")
        handle.write(
            f"<div class='meta'>Generated {html.escape(checked_at)}. "
            f"Likely fixes: {totals['fix']} | Acceptable names/terms: {totals['acceptable']} | "
            f"Style or house style: {totals['style']} | Template/Liquid noise: {totals['template']}.</div>\n"
        )
        handle.write(
            "<div class='meta'>This grouped view is heuristic. It is meant to speed up review, "
            "not to replace judgement on the final wording.</div>\n"
        )

        bucket_labels = {
            "fix": "Likely Fix",
            "acceptable": "Likely Acceptable Name/Term",
            "style": "Likely Style/House Style",
            "template": "Likely Template/Liquid False Positive",
        }

        for entry, grouped in grouped_entries:
            handle.write("<section class='entry'>\n")
            handle.write(f"<h2>{html.escape(entry['title'])}</h2>\n")
            handle.write(
                f"<div class='path'>{html.escape(str(entry['path'].relative_to(REPO_ROOT)))}</div>\n"
            )
            handle.write("<div class='links'>")
            handle.write(f"<a href='{html.escape(file_url(entry['path']))}'>Open source file</a>")
            handle.write(
                f"<a href='http://127.0.0.1:4000{html.escape(entry['route'])}' target='_blank' rel='noopener'>Open local page</a>"
            )
            first_line = entry["issues"][0]["line"] if entry["issues"] else 1
            editor_url = build_editor_url(editor_template, entry["path"], first_line)
            if editor_url:
                handle.write(f"<a href='{html.escape(editor_url)}'>Edit in configured editor</a>")
            handle.write("</div>\n")

            if not entry["issues"]:
                handle.write("<p>No issues found for this entry.</p>\n")
                handle.write("</section>\n")
                continue

            for bucket in ("fix", "acceptable", "style", "template"):
                items = grouped[bucket]
                if not items:
                    continue
                handle.write(f"<div class='bucket {bucket}'>\n")
                handle.write(f"<h3>{bucket_labels[bucket]} ({len(items)})</h3>\n<ul>\n")
                for issue in items:
                    editor_url = build_editor_url(editor_template, entry["path"], issue["line"])
                    line_label = f"line {issue['line']}"
                    if editor_url:
                        line_label = f"<a href='{html.escape(editor_url)}'>{line_label}</a>"
                    handle.write(
                        "<li>"
                        f"{line_label}: "
                        f"<strong>{html.escape(issue['word'] or '(n/a)')}</strong> "
                        f"({html.escape(issue['rule_id'])})"
                        f" - {html.escape(issue['message'])}"
                        "</li>\n"
                    )
                handle.write("</ul>\n</div>\n")
            handle.write("</section>\n")

        handle.write("</body></html>\n")


def build_json_summary(entries: list[dict]) -> dict:
    totals = {"fix": 0, "acceptable": 0, "style": 0, "template": 0}
    summary_entries = []

    for entry in entries:
        grouped = {"fix": [], "acceptable": [], "style": [], "template": []}
        for issue in entry["issues"]:
            bucket = classify_issue(entry, issue)
            totals[bucket] += 1
            grouped[bucket].append(
                {
                    "line": issue["line"],
                    "word": issue["word"],
                    "rule_id": issue["rule_id"],
                    "message": issue["message"],
                    "context": issue["context"],
                    "replacements": issue["replacements"],
                }
            )

        summary_entries.append(
            {
                "path": str(entry["path"]),
                "title": entry["title"],
                "route": entry["route"],
                "word_count": entry["word_count"],
                "issue_count": len(entry["issues"]),
                "grouped": grouped,
            }
        )

    return {
        "pages_checked": len(entries),
        "issues": sum(len(entry["issues"]) for entry in entries),
        "fixes": totals["fix"],
        "acceptable": totals["acceptable"],
        "style": totals["style"],
        "template": totals["template"],
        "entries": summary_entries,
    }


def main() -> int:
    args = parse_args()
    entries = find_entries(args)
    custom_words = load_custom_words()
    tool = language_tool_python.LanguageTool("en-GB", new_spellings=sorted(custom_words))
    try:
        checked_entries = [check_entry(path, tool, custom_words) for path in entries]
    finally:
        tool.close()

    if args.json_summary:
        print(json.dumps(build_json_summary(checked_entries), ensure_ascii=False))
        return 0

    report_path = Path(args.output).expanduser().resolve()
    grouped_report_path = Path(args.grouped_output).expanduser().resolve()
    render_html(report_path, checked_entries, args.editor_url_template, custom_words)
    render_grouped_html(grouped_report_path, checked_entries, args.editor_url_template)
    try:
        from repo_activity import log_spellcheck_run

        totals = {"fix": 0, "acceptable": 0, "style": 0, "template": 0}
        for entry in checked_entries:
            for issue in entry["issues"]:
                totals[classify_issue(entry, issue)] += 1

        log_spellcheck_run(
            {
                "pages_checked": len(checked_entries),
                "issues": sum(len(entry["issues"]) for entry in checked_entries),
                "fixes": totals["fix"],
                "acceptable": totals["acceptable"],
                "style": totals["style"],
                "template": totals["template"],
                "include_index": args.include_index,
                "include_archive": args.include_archive,
                "custom_words_file": str(MUSAK_CUSTOM_WORDS_FILE),
                "report_path": str(report_path),
                "grouped_report_path": str(grouped_report_path),
            }
        )
    except Exception:
        pass
    print(report_path)
    print(grouped_report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
