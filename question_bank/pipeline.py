"""Scraping pipeline: fetch → extract → deduplicate → persist.

Entry point:  run_pipeline()

Can be run directly:
    python -m question_bank.pipeline
    python -m question_bank.pipeline --sources github hackernews
    python -m question_bank.pipeline --sources reddit stackexchange --reddit-limit 5
    python -m question_bank.pipeline --sources github --reddit-limit 5

Valid source names: reddit, stackexchange, github, hackernews

The pipeline is intentionally stateless — it is safe to run multiple times.
The UNIQUE constraint on (source, source_id) in scraped_questions prevents
double-inserts, and the dedup layer prevents near-duplicate prompts from being
stored even under different source IDs.
"""
from __future__ import annotations

import argparse
import json

from db.connection import get_cursor
from db.models import init_db
from question_bank.extractor import ExtractedQuestion, deduplicate, extract_questions
from question_bank.scraper import (
    RawPost,
    fetch_github,
    fetch_hackernews,
    fetch_reddit,
    fetch_stackexchange,
)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load_existing_prompts() -> list[str]:
    """All prompts in the bank files plus pending candidates (for dedup)."""
    from db import repo
    try:
        return repo.existing_prompts()
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] Could not load existing prompts (continuing): {exc}")
        from question_bank import store
        return [q["prompt"] for q in store.load_all()]


def _load_existing_source_ids() -> set[str]:
    """Return (source, source_id) pairs already in the DB to skip re-extraction."""
    ids: set[str] = set()
    try:
        with get_cursor() as cur:
            cur.execute("SELECT source, source_id FROM scraped_questions")
            for row in cur.fetchall():
                ids.add(f"{row['source']}:{row['source_id']}")
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] Could not load existing source IDs (continuing): {exc}")
    return ids


def _save_questions(questions: list[ExtractedQuestion]) -> int:
    """Upsert a list of ExtractedQuestion dicts into scraped_questions.

    Returns:
        Number of rows actually inserted (skips conflicts silently).
    """
    if not questions:
        return 0
    inserted = 0
    try:
        with get_cursor(commit=True) as cur:
            for q in questions:
                cur.execute(
                    """
                    INSERT INTO scraped_questions
                        (source, source_id, domain, topic, difficulty, tags,
                         prompt, expected_answer_notes, approved, raw_text)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, source_id) DO NOTHING
                    """,
                    (
                        q["source"],
                        q["source_id"],
                        q["domain"],
                        q["topic"],
                        q["difficulty"],
                        json.dumps(q["tags"]),
                        q["prompt"],
                        q["expected_answer_notes"],
                        q["approved"],
                        q["raw_text"],
                    ),
                )
                if cur.rowcount:
                    inserted += 1
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] DB save failed: {exc}")
    return inserted


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

_ALL_SOURCES = ["reddit", "stackexchange", "github", "hackernews"]


def run_pipeline(
    sources: list[str] | None = None,
    reddit_limit: int = 10,
) -> dict[str, int]:
    """Run the full scrape → extract → dedup → store pipeline.

    Args:
        sources:      Which sources to fetch. None / empty = all sources.
                      Valid values: "reddit", "stackexchange", "github", "hackernews"
        reddit_limit: Posts per (subreddit, search_term) for the Reddit fetcher.

    Returns:
        Summary dict: {"fetched": N, "extracted": N, "unique": N, "saved": N}
    """
    init_db()
    sources = sources or _ALL_SOURCES

    # 1. Fetch raw posts.
    raw_posts: list[RawPost] = []
    if "reddit" in sources:
        raw_posts.extend(fetch_reddit(limit_per_term=reddit_limit))
    if "stackexchange" in sources:
        raw_posts.extend(fetch_stackexchange())
    if "github" in sources:
        raw_posts.extend(fetch_github())
    if "hackernews" in sources:
        raw_posts.extend(fetch_hackernews())

    fetched = len(raw_posts)
    print(f"[pipeline] Fetched {fetched} raw posts total.")

    if not raw_posts:
        return {"fetched": 0, "extracted": 0, "unique": 0, "saved": 0}

    # Skip posts whose source_id we already have in the DB (avoid re-LLM-calling).
    existing_ids = _load_existing_source_ids()
    new_posts = [p for p in raw_posts
                 if f"{p['source']}:{p['source_id']}" not in existing_ids]
    print(f"[pipeline] {len(new_posts)} posts not yet in DB → extracting questions.")

    # 2. Extract questions via Claude.
    all_extracted: list[ExtractedQuestion] = []
    for i, post in enumerate(new_posts, 1):
        extracted = extract_questions(post)
        all_extracted.extend(extracted)
        if i % 10 == 0:
            print(f"[pipeline]   ... processed {i}/{len(new_posts)} posts "
                  f"({len(all_extracted)} questions so far)")

    extracted_count = len(all_extracted)
    print(f"[pipeline] Extracted {extracted_count} candidate questions.")

    # 3. Deduplicate against existing bank.
    existing_prompts = _load_existing_prompts()
    unique = deduplicate(all_extracted, existing_prompts)
    print(f"[pipeline] {len(unique)} questions survived dedup "
          f"({extracted_count - len(unique)} duplicates dropped).")

    # 4. Persist to DB.
    saved = _save_questions(unique)
    print(f"[pipeline] Saved {saved} new questions to scraped_questions table.")

    summary = {
        "fetched": fetched,
        "extracted": extracted_count,
        "unique": len(unique),
        "saved": saved,
    }
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape forum posts and extract interview questions into the DB."
    )
    parser.add_argument(
        "--sources", nargs="+",
        choices=_ALL_SOURCES,
        default=_ALL_SOURCES,
        help="Which sources to scrape (default: all).",
    )
    parser.add_argument(
        "--reddit-limit", type=int, default=10,
        help="Max posts per (subreddit, search_term) for Reddit (default: 10).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    summary = run_pipeline(sources=args.sources, reddit_limit=args.reddit_limit)
    print("\n--- Pipeline summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
