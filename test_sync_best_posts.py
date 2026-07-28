#!/usr/bin/env python3

from __future__ import annotations

import json
import runpy
import stat
import tempfile
import unittest
from pathlib import Path

from sync_best_posts import (
    RankingSyncError,
    canonical_url,
    load_rankings,
    local_posts,
    match_ranked_posts,
    parse_front_matter,
    sync_best_posts,
    verify_newer_posts_assessed,
)

PUBLISH_LOCAL = runpy.run_path(
    str(Path(__file__).resolve().parent / "publish-local.py")
)


class BestPostsSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temporary_directory.name) / "curns.github.io"
        self.repo_root.mkdir()
        self.ranking_file = (
            Path(self.temporary_directory.name)
            / "MusakChecker"
            / "calendar"
            / "best_posts.html"
        )
        self.ranking_file.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_post(
        self,
        *,
        index: int,
        section: str,
        title: str,
        url: str,
        extra_front_matter: list[str] | None = None,
        published_on: str | None = None,
    ) -> Path:
        post_dir = self.repo_root / section / "_posts"
        post_dir.mkdir(parents=True, exist_ok=True)
        post_date = published_on or f"2026-01-{index:02d}"
        path = post_dir / f"{post_date}-Post-{index}.md"
        extra = extra_front_matter or []
        front_matter = [
            "---",
            f'title: "{title}"',
            "layout: post",
            f"categories: {section}",
            f'curnow-url: "{url}"',
            "longform: true",
            "star: true",
            *extra,
            "---",
            "",
            f"Body for {title}.",
            "",
        ]
        path.write_text("\n".join(front_matter), encoding="utf-8")
        return path

    def write_ranking(self, rankings: list[dict[str, object]]) -> None:
        self.ranking_file.write_text(
            "<div>Initial reviews 2026-07-28</div>\n"
            "<script>\n"
            f"const POSTS = {json.dumps(rankings)};\n"
            'const PAGE_COUNTS = {"all": 1};\n'
            "</script>\n",
            encoding="utf-8",
        )

    def test_sync_selects_ten_general_three_radio_and_seven_next_best(self) -> None:
        rankings: list[dict[str, object]] = []
        general_paths: list[Path] = []
        radio_paths: list[Path] = []

        source_order: list[tuple[str, int]] = [
            ("general", 1),
            ("radio", 1),
            ("general", 2),
            ("general", 3),
            ("radio", 2),
            ("general", 4),
            ("general", 5),
            ("general", 6),
            ("general", 7),
            ("radio", 3),
            ("general", 8),
            ("general", 9),
            ("general", 10),
            ("general", 11),
            ("radio", 4),
            ("general", 12),
            ("general", 13),
            ("general", 14),
            ("general", 15),
            ("general", 16),
            ("general", 17),
            ("general", 18),
        ]

        for source_rank, (kind, kind_index) in enumerate(source_order, start=1):
            section = "radio" if kind == "radio" else "everyday"
            title = f"{kind.title()} post {kind_index}"
            url = f"https://www.curnow.org/2026/01/{kind}-post-{kind_index}/"
            extras = (
                [
                    "next_best: true",
                    "best_rank: 99",
                    'best_description: "Keep this description."',
                ]
                if source_rank == 1
                else []
            )
            path = self.create_post(
                index=source_rank,
                section=section,
                title=title,
                url=url,
                extra_front_matter=extras,
            )
            if kind == "radio":
                radio_paths.append(path.resolve())
            else:
                general_paths.append(path.resolve())
            rankings.append(
                {
                    "title": title,
                    "url": url,
                    "published_date": f"2026-01-{source_rank:02d}",
                    "combined": 10 - source_rank / 100,
                    "categories": ["Radio" if kind == "radio" else "Other"],
                    "note": f"{title} has a useful first sentence. A second sentence is not needed.",
                }
            )

        self.write_ranking(rankings)
        original_mode = stat.S_IMODE(general_paths[0].stat().st_mode)
        result = sync_best_posts(
            self.repo_root,
            ranking_file=self.ranking_file,
        )

        self.assertEqual(10, len(result.selected_paths))
        self.assertEqual(3, len(result.radio_paths))
        self.assertEqual(7, len(result.next_best_paths))
        self.assertEqual(22, result.matched_finalists)

        selected_general = set(general_paths[:10])
        selected_radio = set(radio_paths[:3])
        next_best = set(general_paths[10:17])
        ranked_twenty = selected_general | selected_radio | next_best
        observed_ranks: list[int] = []

        for path in general_paths + radio_paths:
            metadata = parse_front_matter(path.read_text(encoding="utf-8"), path)
            self.assertEqual(
                path in selected_general or path in selected_radio,
                metadata["star"],
            )
            self.assertEqual(path in next_best, metadata.get("next_best") is True)
            if path in ranked_twenty:
                observed_ranks.append(int(metadata["best_rank"]))
                self.assertTrue(metadata.get("best_description"))
            else:
                self.assertNotIn("best_rank", metadata)
                self.assertNotIn("best_description", metadata)

        self.assertEqual(list(range(1, 21)), sorted(observed_ranks))
        self.assertEqual(
            original_mode,
            stat.S_IMODE(general_paths[0].stat().st_mode),
        )
        first_metadata = parse_front_matter(
            general_paths[0].read_text(encoding="utf-8"),
            general_paths[0],
        )
        self.assertEqual("Keep this description.", first_metadata["best_description"])
        self.assertEqual("selected post", result.tier_for(general_paths[0]))
        self.assertEqual("selected radio post", result.tier_for(radio_paths[0]))
        self.assertEqual("next-best post", result.tier_for(general_paths[10]))
        self.assertEqual(
            "not selected in the current top twenty",
            result.tier_for(general_paths[17]),
        )

        second_result = sync_best_posts(
            self.repo_root,
            ranking_file=self.ranking_file,
        )
        self.assertEqual((), second_result.changed_paths)

    def test_title_and_date_provide_a_unique_fallback_match(self) -> None:
        path = self.create_post(
            index=1,
            section="everyday",
            title="A fallback title",
            url="https://www.curnow.org/2026/01/a-local-slug/",
        )
        rankings = [
            {
                "title": "A fallback title",
                "url": "https://www.musak.org/2026/01/a-different-slug/",
                "published_date": "2026-01-01",
                "categories": ["Other"],
                "note": "A fallback note.",
            }
        ]
        self.write_ranking(rankings)

        matches = match_ranked_posts(
            local_posts(self.repo_root),
            load_rankings(self.ranking_file),
        )
        self.assertEqual(1, len(matches))
        self.assertEqual(path.resolve(), matches[0].post.path)

    def test_missing_ranking_file_fails_without_changing_posts(self) -> None:
        path = self.create_post(
            index=1,
            section="everyday",
            title="Unchanged",
            url="https://www.curnow.org/2026/01/unchanged/",
        )
        original = path.read_text(encoding="utf-8")

        with self.assertRaisesRegex(RankingSyncError, "was not found"):
            sync_best_posts(
                self.repo_root,
                ranking_file=self.ranking_file,
            )

        self.assertEqual(original, path.read_text(encoding="utf-8"))

    def test_newer_unranked_post_requires_an_incremental_decision(self) -> None:
        path = self.create_post(
            index=1,
            section="everyday",
            title="A future post",
            url="https://www.curnow.org/2026/08/a-future-post/",
            published_on="2026-08-01",
        )
        self.write_ranking(
            [
                {
                    "title": "An unrelated finalist",
                    "url": "https://www.curnow.org/2026/01/unrelated/",
                    "published_date": "2026-01-01",
                    "categories": ["Other"],
                    "note": "An unrelated note.",
                }
            ]
        )
        posts = local_posts(self.repo_root)
        matches = match_ranked_posts(posts, load_rankings(self.ranking_file))
        incremental_file = (
            self.ranking_file.parents[1] / "best_posts_incremental_reviews.json"
        )
        incremental_file.write_text(
            json.dumps({"reviews": {}}),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(RankingSyncError, "not yet received"):
            verify_newer_posts_assessed(posts, matches, self.ranking_file)

        incremental_file.write_text(
            json.dumps(
                {
                    "reviews": {
                        "future": {
                            "status": "reviewed",
                            "decision": "exclude",
                            "title": "A future post",
                            "url": "https://www.curnow.org/2026/08/a-future-post/",
                            "published_date": "2026-08-01",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        verify_newer_posts_assessed(posts, matches, self.ranking_file)
        metadata = parse_front_matter(path.read_text(encoding="utf-8"), path)
        self.assertEqual("A future post", metadata["title"])

    def test_canonical_url_ignores_www_query_fragment_and_trailing_slash(self) -> None:
        self.assertEqual(
            "curnow.org/2026/01/example",
            canonical_url("https://www.CURNOW.org/2026/01/Example/?ref=1#top"),
        )

    def test_quick_publish_comparison_ignores_only_managed_ranking_fields(self) -> None:
        before = (
            "---\n"
            'title: "Example"\n'
            "star: false\n"
            "---\n"
            "Original body.\n"
        )
        ranking_only = (
            "---\n"
            'title: "Example"\n'
            "star: true\n"
            "next_best: true\n"
            "best_rank: 12\n"
            'best_description: "Example description."\n'
            "---\n"
            "Original body.\n"
        )
        body_change = ranking_only.replace("Original body.", "Changed body.")
        strip_ranking = PUBLISH_LOCAL["without_ranking_front_matter"]

        self.assertEqual(strip_ranking(before), strip_ranking(ranking_only))
        self.assertNotEqual(strip_ranking(before), strip_ranking(body_change))


if __name__ == "__main__":
    unittest.main()
