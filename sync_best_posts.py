#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent
RANKING_MARKER = "const POSTS = "
INITIAL_REVIEW_DATE_PATTERN = re.compile(r"Initial reviews (\d{4}-\d{2}-\d{2})")
MANAGED_FIELDS = (
    "star",
    "next_best",
    "best_rank",
    "best_description",
)
SELECTED_POST_COUNT = 10
RADIO_POST_COUNT = 3
NEXT_BEST_POST_COUNT = 7
DESCRIPTION_LIMIT = 220


class RankingSyncError(RuntimeError):
    """Raised when the Best Posts ranking cannot be applied safely."""


@dataclass(frozen=True)
class LocalPost:
    path: Path
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class RankedMatch:
    source_rank: int
    post: LocalPost
    ranking: dict[str, object]


@dataclass(frozen=True)
class RankingSyncResult:
    changed_paths: tuple[Path, ...]
    selected_paths: tuple[Path, ...]
    radio_paths: tuple[Path, ...]
    next_best_paths: tuple[Path, ...]
    matched_finalists: int

    def tier_for(self, path: Path) -> str:
        resolved = path.resolve()
        if resolved in {item.resolve() for item in self.selected_paths}:
            return "selected post"
        if resolved in {item.resolve() for item in self.radio_paths}:
            return "selected radio post"
        if resolved in {item.resolve() for item in self.next_best_paths}:
            return "next-best post"
        return "not selected in the current top twenty"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronise GitHub Pages Best Posts front matter with the ranked "
            "Musak Checker Best Posts list."
        )
    )
    parser.add_argument(
        "--ranking-file",
        type=Path,
        help=(
            "Path to Musak Checker's calendar/best_posts.html. By default the "
            "script uses MUSAK_CHECKER_DIR or the sibling MusakChecker project."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which post files need changes without writing them.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the ranking front matter is not already current.",
    )
    return parser.parse_args()


def default_ranking_file(repo_root: Path) -> Path:
    configured_dir = os.environ.get("MUSAK_CHECKER_DIR", "").strip()
    if configured_dir:
        return Path(configured_dir).expanduser() / "calendar" / "best_posts.html"
    return repo_root.parent / "MusakChecker" / "calendar" / "best_posts.html"


def scalar_value(raw_value: str) -> object:
    value = raw_value.strip()
    if not value:
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value[:1] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value.strip("'\"")
        if isinstance(parsed, (str, int, float, bool)):
            return parsed
    return value


def front_matter_parts(text: str, path: Path) -> tuple[list[str], int]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise RankingSyncError(f"{path}: missing opening front-matter delimiter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines, index
    raise RankingSyncError(f"{path}: missing closing front-matter delimiter")


def parse_front_matter(text: str, path: Path) -> dict[str, object]:
    lines, closing_index = front_matter_parts(text, path)
    metadata: dict[str, object] = {}
    for line in lines[1:closing_index]:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        if match:
            metadata[match.group(1)] = scalar_value(match.group(2))
    return metadata


def local_posts(repo_root: Path) -> list[LocalPost]:
    posts: list[LocalPost] = []
    for section in sorted(repo_root.iterdir(), key=lambda item: item.name.casefold()):
        post_dir = section / "_posts"
        if not post_dir.is_dir():
            continue
        for path in sorted(post_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            posts.append(
                LocalPost(
                    path=path.resolve(),
                    text=text,
                    metadata=parse_front_matter(text, path),
                )
            )
    if not posts:
        raise RankingSyncError(f"No post files were found under {repo_root}")
    return posts


def load_rankings(ranking_file: Path) -> list[dict[str, object]]:
    if not ranking_file.is_file():
        raise RankingSyncError(
            f"Musak Checker ranking file was not found: {ranking_file}"
        )
    source = ranking_file.read_text(encoding="utf-8")
    marker_index = source.find(RANKING_MARKER)
    if marker_index < 0:
        raise RankingSyncError(
            f"{ranking_file}: could not find the embedded Best Posts ranking"
        )
    json_source = source[marker_index + len(RANKING_MARKER) :].lstrip()
    try:
        rankings, _end = json.JSONDecoder().raw_decode(json_source)
    except json.JSONDecodeError as exc:
        raise RankingSyncError(
            f"{ranking_file}: embedded Best Posts ranking is invalid JSON"
        ) from exc
    if not isinstance(rankings, list) or not rankings:
        raise RankingSyncError(f"{ranking_file}: Best Posts ranking is empty")
    cleaned: list[dict[str, object]] = []
    for index, item in enumerate(rankings, start=1):
        if not isinstance(item, dict) or not item.get("url") or not item.get("title"):
            raise RankingSyncError(
                f"{ranking_file}: ranking entry {index} is missing a URL or title"
            )
        cleaned.append(item)
    return cleaned


def initial_review_date(ranking_file: Path) -> str:
    source = ranking_file.read_text(encoding="utf-8")
    match = INITIAL_REVIEW_DATE_PATTERN.search(source)
    if not match:
        raise RankingSyncError(
            f"{ranking_file}: could not find the initial Best Posts review date"
        )
    return match.group(1)


def canonical_url(raw_url: object) -> str:
    value = str(raw_url or "").strip().strip("'\"")
    if not value:
        return ""
    parsed = urlparse(value)
    host = parsed.netloc.casefold()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/").casefold()
    return f"{host}{path}"


def normalised_title(raw_title: object) -> str:
    value = unicodedata.normalize("NFKD", str(raw_title or ""))
    value = value.replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def publication_date_for(post: LocalPost) -> str:
    explicit_date = str(post.metadata.get("date", "")).strip()
    match = re.match(r"(\d{4}-\d{2}-\d{2})", explicit_date)
    if match:
        return match.group(1)
    filename_match = re.match(r"(\d{4}-\d{2}-\d{2})-", post.path.name)
    return filename_match.group(1) if filename_match else ""


def post_source_urls(post: LocalPost) -> set[str]:
    return {
        canonical
        for key in ("curnow-url", "musak-url")
        if (canonical := canonical_url(post.metadata.get(key)))
    }


def match_ranked_posts(
    posts: list[LocalPost],
    rankings: list[dict[str, object]],
) -> list[RankedMatch]:
    posts_by_url: dict[str, LocalPost] = {}
    for post in posts:
        for url in post_source_urls(post):
            existing = posts_by_url.get(url)
            if existing and existing.path != post.path:
                raise RankingSyncError(
                    f"Two local posts use the same source URL: {existing.path} and {post.path}"
                )
            posts_by_url[url] = post

    posts_by_title_date: dict[tuple[str, str], list[LocalPost]] = {}
    for post in posts:
        key = (
            normalised_title(post.metadata.get("title")),
            publication_date_for(post),
        )
        posts_by_title_date.setdefault(key, []).append(post)

    matched: list[RankedMatch] = []
    matched_paths: set[Path] = set()
    for source_rank, ranking in enumerate(rankings, start=1):
        post = posts_by_url.get(canonical_url(ranking.get("url")))
        if post is None:
            fallback_key = (
                normalised_title(ranking.get("title")),
                str(ranking.get("published_date", ""))[:10],
            )
            fallback_matches = posts_by_title_date.get(fallback_key, [])
            if len(fallback_matches) == 1:
                post = fallback_matches[0]
        if post is None or post.path in matched_paths:
            continue
        matched.append(
            RankedMatch(
                source_rank=source_rank,
                post=post,
                ranking=ranking,
            )
        )
        matched_paths.add(post.path)
    return matched


def matching_incremental_review(
    post: LocalPost,
    review_records: list[dict[str, object]],
) -> dict[str, object] | None:
    source_urls = post_source_urls(post)
    title_date = (
        normalised_title(post.metadata.get("title")),
        publication_date_for(post),
    )
    matches: list[dict[str, object]] = []
    for record in review_records:
        record_url = canonical_url(record.get("url"))
        record_title_date = (
            normalised_title(record.get("title")),
            str(record.get("published_date", ""))[:10],
        )
        if (record_url and record_url in source_urls) or record_title_date == title_date:
            matches.append(record)
    if len(matches) > 1:
        raise RankingSyncError(
            f"{post.path}: multiple Musak Checker incremental reviews match this post"
        )
    return matches[0] if matches else None


def verify_newer_posts_assessed(
    posts: list[LocalPost],
    ranked_matches: list[RankedMatch],
    ranking_file: Path,
) -> None:
    reviewed_through = initial_review_date(ranking_file)
    ranked_paths = {match.post.path for match in ranked_matches}
    newer_unranked = [
        post
        for post in posts
        if publication_date_for(post) > reviewed_through
        and post.path not in ranked_paths
    ]
    if not newer_unranked:
        return

    incremental_file = ranking_file.parents[1] / "best_posts_incremental_reviews.json"
    if not incremental_file.is_file():
        raise RankingSyncError(
            "Newer unranked posts need an incremental Best Posts decision, but "
            f"{incremental_file} was not found"
        )
    try:
        state = json.loads(incremental_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RankingSyncError(
            f"{incremental_file}: could not read incremental Best Posts decisions"
        ) from exc
    raw_reviews = state.get("reviews") if isinstance(state, dict) else None
    if not isinstance(raw_reviews, dict):
        raise RankingSyncError(
            f"{incremental_file}: incremental Best Posts reviews are not an object"
        )
    review_records = [
        record
        for record in raw_reviews.values()
        if isinstance(record, dict)
    ]

    for post in newer_unranked:
        review = matching_incremental_review(post, review_records)
        if review is None:
            raise RankingSyncError(
                f"{post.path}: this post is newer than the initial review and has "
                "not yet received a Musak Checker Best Posts decision"
            )
        status = str(review.get("status", ""))
        decision = str(review.get("decision", ""))
        if status == "skipped_weeknotes":
            continue
        if status != "reviewed":
            raise RankingSyncError(
                f"{post.path}: its Musak Checker Best Posts review is not complete "
                f"(status: {status or 'unknown'})"
            )
        if decision == "include":
            raise RankingSyncError(
                f"{post.path}: Musak Checker includes this post, but the ranked "
                "Best Posts page has not been rebuilt yet"
            )
        if decision != "exclude":
            raise RankingSyncError(
                f"{post.path}: its Musak Checker Best Posts decision is not recognised"
            )


def is_radio_post(post: LocalPost, repo_root: Path) -> bool:
    relative_parts = post.path.relative_to(repo_root.resolve()).parts
    if relative_parts and relative_parts[0].casefold() == "radio":
        return True
    categories = str(post.metadata.get("categories", ""))
    category_tokens = re.findall(r"[A-Za-z0-9-]+", categories.casefold())
    return "radio" in category_tokens


def truncate_at_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{shortened}…"


def description_for(match: RankedMatch) -> str:
    existing = str(match.post.metadata.get("best_description", "")).strip()
    if existing:
        return existing
    note = re.sub(r"\s+", " ", str(match.ranking.get("note", ""))).strip()
    if not note:
        return "A recommended post from the Musak Checker Best Posts ranking."
    sentence_match = re.match(r"(.+?[.!?])(?:\s|$)", note)
    sentence = sentence_match.group(1) if sentence_match else note
    return truncate_at_word(sentence, DESCRIPTION_LIMIT)


def rendered_front_matter(
    post: LocalPost,
    *,
    star: bool,
    next_best: bool,
    best_rank: int | None,
    best_description: str | None,
) -> str:
    lines, closing_index = front_matter_parts(post.text, post.path)
    managed_pattern = re.compile(
        rf"^(?:{'|'.join(re.escape(field) for field in MANAGED_FIELDS)}):"
    )
    kept_front_matter = [
        line
        for line in lines[1:closing_index]
        if not managed_pattern.match(line)
    ]
    managed_lines = [f"star: {'true' if star else 'false'}\n"]
    if next_best:
        managed_lines.append("next_best: true\n")
    if best_rank is not None and best_description is not None:
        managed_lines.append(f"best_rank: {best_rank}\n")
        managed_lines.append(
            f"best_description: {json.dumps(best_description, ensure_ascii=False)}\n"
        )
    return "".join(
        [
            lines[0],
            *kept_front_matter,
            *managed_lines,
            lines[closing_index],
            *lines[closing_index + 1 :],
        ]
    )


def atomic_write(path: Path, text: str) -> None:
    original_mode = stat.S_IMODE(path.stat().st_mode)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temporary_path = Path(handle.name)
    try:
        temporary_path.chmod(original_mode)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def sync_best_posts(
    repo_root: Path = REPO_ROOT,
    *,
    ranking_file: Path | None = None,
    dry_run: bool = False,
) -> RankingSyncResult:
    repo_root = repo_root.resolve()
    source_file = (
        ranking_file.expanduser().resolve()
        if ranking_file
        else default_ranking_file(repo_root).resolve()
    )
    posts = local_posts(repo_root)
    rankings = load_rankings(source_file)
    ranked_matches = match_ranked_posts(posts, rankings)
    verify_newer_posts_assessed(posts, ranked_matches, source_file)

    general_matches = [
        match for match in ranked_matches if not is_radio_post(match.post, repo_root)
    ]
    radio_matches = [
        match for match in ranked_matches if is_radio_post(match.post, repo_root)
    ]
    required_general = SELECTED_POST_COUNT + NEXT_BEST_POST_COUNT
    if len(general_matches) < required_general:
        raise RankingSyncError(
            "The Musak Checker ranking matches only "
            f"{len(general_matches)} local non-radio finalists; {required_general} "
            "are required for the selected and next-best lists."
        )
    if len(radio_matches) < RADIO_POST_COUNT:
        raise RankingSyncError(
            "The Musak Checker ranking matches only "
            f"{len(radio_matches)} local radio finalists; {RADIO_POST_COUNT} are required."
        )

    selected = general_matches[:SELECTED_POST_COUNT]
    selected_radio = radio_matches[:RADIO_POST_COUNT]
    next_best = general_matches[
        SELECTED_POST_COUNT : SELECTED_POST_COUNT + NEXT_BEST_POST_COUNT
    ]

    selected_paths = {match.post.path for match in selected}
    radio_paths = {match.post.path for match in selected_radio}
    next_best_paths = {match.post.path for match in next_best}
    ranked_twenty_paths = selected_paths | radio_paths | next_best_paths
    ranked_twenty = [
        match for match in ranked_matches if match.post.path in ranked_twenty_paths
    ]
    rank_by_path = {
        match.post.path: rank
        for rank, match in enumerate(ranked_twenty, start=1)
    }
    match_by_path = {match.post.path: match for match in ranked_twenty}

    changed: list[tuple[Path, str]] = []
    for post in posts:
        in_ranked_twenty = post.path in ranked_twenty_paths
        updated_text = rendered_front_matter(
            post,
            star=post.path in selected_paths or post.path in radio_paths,
            next_best=post.path in next_best_paths,
            best_rank=rank_by_path.get(post.path),
            best_description=(
                description_for(match_by_path[post.path])
                if in_ranked_twenty
                else None
            ),
        )
        if updated_text != post.text:
            changed.append((post.path, updated_text))

    if not dry_run:
        for path, updated_text in changed:
            atomic_write(path, updated_text)

    return RankingSyncResult(
        changed_paths=tuple(path for path, _text in changed),
        selected_paths=tuple(match.post.path for match in selected),
        radio_paths=tuple(match.post.path for match in selected_radio),
        next_best_paths=tuple(match.post.path for match in next_best),
        matched_finalists=len(ranked_matches),
    )


def main() -> int:
    args = parse_args()
    try:
        result = sync_best_posts(
            REPO_ROOT,
            ranking_file=args.ranking_file,
            dry_run=args.dry_run or args.check,
        )
    except RankingSyncError as exc:
        print(f"Best Posts ranking sync failed: {exc}", file=sys.stderr)
        return 2

    action = "would update" if args.dry_run or args.check else "updated"
    print(
        "Best Posts ranking: "
        f"{SELECTED_POST_COUNT} selected, {RADIO_POST_COUNT} radio, "
        f"{NEXT_BEST_POST_COUNT} next best; "
        f"{len(result.changed_paths)} file(s) {action}."
    )
    for path in result.changed_paths:
        print(f"  {path.relative_to(REPO_ROOT)}")

    if args.check and result.changed_paths:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
