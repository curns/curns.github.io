#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import json
import re
import socket
import sys
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "_data"
OUTPUT_PATH = DATA_DIR / "contents_links.json"
OVERRIDES_PATH = DATA_DIR / "contents_manual_overrides.json"
AUDIT_PATH = REPO_ROOT / "local_reports" / "contents-link-audit.md"
GITHUB_BASE = "https://curns.github.io"
REQUEST_TIMEOUT = 4
MUSAK_CUTOFF_DATE = dt.date(2008, 11, 11)
SITE_BASES = {
    "musak": "https://www.musak.org",
    "curnow": "https://www.curnow.org",
}
ROOT_PAGES = ("archive.md",)
SKIP_DIRS = {"vendor", "_site", ".git", "category", "year", "local_info", "local_logs", "local_reports"}
DATE_STAMP_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$")
URL_RE = re.compile(r"https?://(?:www\.)?(?:musak\.org|curnow\.org)[^\s)>\]\"']+")
HINT_MARKDOWN_RE = re.compile(r"\boriginally\b|\[(?:musak(?:\.org)?|curnow\.org)\]", re.I)
HTML_TRAIL_RE = re.compile(r"[).,;:!?]+$")
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
AUTO_LINK_RE = re.compile(r"<(https?://[^>]+)>")
RAW_URL_RE = re.compile(r"https?://\S+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HTML_TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[\w'’\-]+", re.UNICODE)


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text

    front_matter: dict[str, str] = {}
    for raw_line in text[4:end].splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        front_matter[key.strip()] = value.strip().strip("'\"")
    return front_matter, text[end + 5 :]


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
    text = re.sub(r"\[\^.+?\]", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def content_word_count(body: str) -> int:
    plain = markdown_to_plain_text(body)
    return len(WORD_RE.findall(plain))


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\([^)]*\)", "", value)
    value = value.replace("&", " and ")
    value = value.replace("’", "").replace("'", "")
    value = re.sub(r"[^a-z0-9_]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-_")


def root_page_title(path: Path, front_matter: dict[str, str]) -> str:
    if path.name == "index.md":
        return "Home"
    return front_matter.get("title", path.stem)


def github_url_for(path: Path, front_matter: dict[str, str]) -> str:
    if path.name == "index.md":
        return f"{GITHUB_BASE}/"
    if "_posts" in path.parts:
        match = DATE_STAMP_RE.match(path.stem)
        if not match:
            raise ValueError(f"Unexpected post name: {path}")
        year, month, day, rest = match.groups()
        section = path.parts[0].lower()
        return f"{GITHUB_BASE}/{section}/{year}/{month}/{day}/{rest}.html"
    return f"{GITHUB_BASE}/{path.stem}.html"


def looks_like_article_link(url: str, year: str, month: str, domain: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if domain not in host:
        return False
    path = parsed.path.lower()
    return f"/{year}/{month}/" in path


def extract_hint_links(body: str, year: str, month: str) -> dict[str, list[str]]:
    links = {"musak": [], "curnow": []}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or not HINT_MARKDOWN_RE.search(line):
            continue
        for match in URL_RE.findall(line):
            url = HTML_TRAIL_RE.sub("", match).replace("http://www.musak.org", SITE_BASES["musak"])
            url = url.replace("http://www.curnow.org", SITE_BASES["curnow"])
            host = urlparse(url).netloc.lower()
            if "musak.org" in host and looks_like_article_link(url, year, month, "musak"):
                links["musak"].append(url)
            if "curnow.org" in host and looks_like_article_link(url, year, month, "curnow"):
                links["curnow"].append(url)
    return links


def generated_candidates(path: Path, title: str) -> dict[str, list[str]]:
    match = DATE_STAMP_RE.match(path.stem)
    if not match:
        return {"musak": [], "curnow": []}

    year, month, _day, rest = match.groups()
    file_slug_dash = rest.lower().replace("_", "-")
    title_slug = slugify(title)

    common_slugs = []
    for slug in (file_slug_dash, title_slug):
        if slug and slug not in common_slugs:
            common_slugs.append(slug)

    return {
        "musak": [f"{SITE_BASES['musak']}/{year}/{month}/{slug}/" for slug in common_slugs],
        "curnow": [f"{SITE_BASES['curnow']}/{year}/{month}/{slug}/" for slug in common_slugs],
    }


def load_overrides() -> dict[str, dict[str, str | None]]:
    if not OVERRIDES_PATH.exists():
        return {}
    data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return data.get("overrides", {})


def front_matter_override(front_matter: dict[str, str], domain: str) -> str | None | object:
    key = f"{domain}-url"
    if key not in front_matter:
        return "__missing__"
    value = front_matter.get(key, "").strip()
    if not value:
        return None
    return value


def url_status(url: str, cache: dict[str, dict[str, object]]) -> dict[str, object]:
    if url in cache:
        return cache[url]

    headers = {"User-Agent": "curns-contents-audit/1.0"}
    result: dict[str, object] = {"ok": False, "url": url, "final_url": url, "status": None}
    for method in ("HEAD", "GET"):
        req = request.Request(url, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                result = {
                    "ok": response.status == 200,
                    "url": url,
                    "final_url": response.geturl(),
                    "status": response.status,
                }
                break
        except error.HTTPError as exc:
            result = {
                "ok": False,
                "url": url,
                "final_url": exc.geturl() or url,
                "status": exc.code,
            }
            if method == "HEAD" and exc.code in (403, 405):
                continue
            break
        except (error.URLError, socket.timeout, TimeoutError):
            result = {"ok": False, "url": url, "final_url": url, "status": "network-error"}
            break
    cache[url] = result
    return result


def same_domain(final_url: str, domain: str) -> bool:
    host = urlparse(final_url).netloc.lower()
    expected = "musak.org" if domain == "musak" else "curnow.org"
    return expected in host


def first_verified_url(
    rel_path: str,
    domain: str,
    front_matter: dict[str, str],
    overrides: dict[str, dict[str, str | None]],
    inline_links: list[str],
    generated_links: list[str],
    cache: dict[str, dict[str, object]],
) -> tuple[str | None, str, list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    front_matter_value = front_matter_override(front_matter, domain)
    if front_matter_value != "__missing__":
        if front_matter_value in (None, ""):
            return None, "front-matter-blank", attempts
        status = url_status(str(front_matter_value), cache)
        attempts.append({"source": "front-matter", **status})
        if status["ok"] and same_domain(str(status["final_url"]), domain):
            return str(status["final_url"]), "front-matter", attempts
        return None, "front-matter-invalid", attempts

    manual_value = overrides.get(rel_path, {}).get(f"{domain}_url", "__missing__")
    if manual_value != "__missing__":
        if manual_value in (None, ""):
            return None, "manual-blank", attempts
        status = url_status(str(manual_value), cache)
        attempts.append({"source": "manual", **status})
        if status["ok"]:
            return str(status["final_url"]), "manual", attempts
        return None, "manual-invalid", attempts

    for source_name, candidates in (("inline", inline_links), ("generated", generated_links)):
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            status = url_status(candidate, cache)
            attempts.append({"source": source_name, **status})
            if status["ok"] and same_domain(str(status["final_url"]), domain):
                return str(status["final_url"]), source_name, attempts
    return None, "not-found", attempts


def collect_pages() -> list[Path]:
    pages: list[Path] = []
    for root_page in ROOT_PAGES:
        path = REPO_ROOT / root_page
        if path.exists():
            pages.append(path)

    for path in sorted(REPO_ROOT.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT)
        if rel.name == "contents.md":
            continue
        if set(rel.parts) & SKIP_DIRS:
            continue
        if rel.name in ROOT_PAGES:
            continue
        if "_posts" in rel.parts:
            pages.append(path)
    return pages


def write_outputs(entries: list[dict[str, object]], audit_lines: list[str]) -> None:
    total_word_count = sum(int(entry["word_count"] or 0) for entry in entries if entry["kind"] == "post")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "total_word_count": total_word_count,
                "entries": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")


def build() -> int:
    overrides = load_overrides()
    cache: dict[str, dict[str, object]] = {}
    entries: list[dict[str, object]] = []
    audit_lines = [
        "# Contents Link Audit",
        "",
        f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        "This report lists how musak.org and curnow.org links were resolved for the hidden contents page.",
        "",
    ]

    for path in collect_pages():
        rel = str(path.relative_to(REPO_ROOT))
        front_matter, body = parse_front_matter(path)
        github_url = github_url_for(path.relative_to(REPO_ROOT), front_matter)
        entry: dict[str, object] = {
            "title": root_page_title(path, front_matter) if path.name in ROOT_PAGES else front_matter.get("title", path.stem),
            "github_url": github_url,
            "source_path": rel,
            "kind": "page" if path.name in ROOT_PAGES else "post",
            "date": None,
            "date_display": "",
            "word_count": None,
            "musak_url": None,
            "curnow_url": None,
            "musak_match": "",
            "curnow_match": "",
        }

        audit_lines.append(f"## {entry['title']}")
        audit_lines.append("")
        audit_lines.append(f"- Source file: `{rel}`")
        audit_lines.append(f"- GitHub page: {github_url}")

        if path.name not in ROOT_PAGES:
            match = DATE_STAMP_RE.match(path.stem)
            if not match:
                raise ValueError(f"Unexpected post path: {rel}")
            year, month, day, _rest = match.groups()
            post_date = dt.date(int(year), int(month), int(day))
            entry["date"] = f"{year}-{month}-{day}"
            entry["date_display"] = f"{day}/{month}/{year}"
            entry["word_count"] = content_word_count(body)
            inline_links = extract_hint_links(body, year, month)
            generated = generated_candidates(path, str(entry["title"]))
            for domain in ("musak", "curnow"):
                if domain == "musak" and post_date > MUSAK_CUTOFF_DATE:
                    entry[f"{domain}_url"] = None
                    entry[f"{domain}_match"] = "date-cutoff"
                    audit_lines.append(f"- {domain}.org match: date-cutoff")
                    audit_lines.append(
                        f"  - Skipped automatically because the post date is after {MUSAK_CUTOFF_DATE.isoformat()}."
                    )
                    continue
                chosen_url, match_type, attempts = first_verified_url(
                    rel,
                    domain,
                    front_matter,
                    overrides,
                    inline_links[domain],
                    generated[domain],
                    cache,
                )
                entry[f"{domain}_url"] = chosen_url
                entry[f"{domain}_match"] = match_type
                audit_lines.append(f"- {domain}.org match: {match_type}")
                if chosen_url:
                    audit_lines.append(f"  - Selected: {chosen_url}")
                if attempts:
                    for attempt in attempts[:8]:
                        audit_lines.append(
                            f"  - Tried ({attempt['source']}): {attempt['url']} -> {attempt['status']}"
                        )
                else:
                    audit_lines.append("  - No candidate URLs tried.")
        else:
            for domain in ("musak", "curnow"):
                chosen_url, match_type, attempts = first_verified_url(
                    rel,
                    domain,
                    front_matter,
                    overrides,
                    [],
                    [],
                    cache,
                )
                entry[f"{domain}_url"] = chosen_url
                entry[f"{domain}_match"] = match_type
                audit_lines.append(f"- {domain}.org match: {match_type}")
                if chosen_url:
                    audit_lines.append(f"  - Selected: {chosen_url}")
                if attempts:
                    for attempt in attempts[:8]:
                        audit_lines.append(
                            f"  - Tried ({attempt['source']}): {attempt['url']} -> {attempt['status']}"
                        )
                else:
                    audit_lines.append("  - No candidate URLs tried.")

        audit_lines.append("")
        entries.append(entry)

    def sort_key(item: dict[str, object]) -> tuple[int, str, str]:
        if item["kind"] == "page":
            order = {"archive.md": "0"}.get(str(item["source_path"]), "9")
            return (0, order, str(item["title"]).lower())
        return (1, str(item["date"] or ""), str(item["title"]).lower())

    entries.sort(key=sort_key)
    write_outputs(entries, audit_lines)
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {AUDIT_PATH}")
    unresolved = [
        entry
        for entry in entries
        if entry["kind"] == "post" and (not entry["musak_url"] or not entry["curnow_url"])
    ]
    print(f"Entries written: {len(entries)}")
    print(f"Posts with at least one blank sister-site cell: {len(unresolved)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(build())
    except KeyboardInterrupt:
        raise SystemExit(130)
