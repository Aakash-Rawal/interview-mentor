"""Raw-text fetchers: Reddit, Stack Exchange, GitHub, and Hacker News.

Each fetcher returns a list of RawPost dicts:
    {
        "source":    str,   # "reddit" | "stackexchange" | "github" | "hackernews"
        "source_id": str,   # unique ID within that source
        "raw_text":  str,   # title + body + top comments / file content concatenated
        "url":       str,   # permalink for reference
    }

The caller (extractor.py) is responsible for turning these into structured
questions; this file only fetches and normalises the raw text.
"""
from __future__ import annotations

import time
from typing import TypedDict

import config


class RawPost(TypedDict):
    source: str
    source_id: str
    raw_text: str
    url: str


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

def _get_reddit():
    """Return a read-only praw.Reddit instance. Raises if credentials missing."""
    try:
        import praw  # lazy import — optional dependency
    except ImportError as exc:
        raise ImportError(
            "praw is not installed. Run: pip install praw"
        ) from exc

    if not config.REDDIT_CLIENT_ID or not config.REDDIT_CLIENT_SECRET:
        raise RuntimeError(
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set in .env "
            "before running the Reddit scraper."
        )
    return praw.Reddit(
        client_id=config.REDDIT_CLIENT_ID,
        client_secret=config.REDDIT_CLIENT_SECRET,
        user_agent=config.REDDIT_USER_AGENT,
        check_for_async=False,
    )


def _post_to_raw(submission, reddit_client) -> RawPost:
    """Convert a praw Submission into a RawPost."""
    submission.comments.replace_more(limit=0)
    # Collect body + top-level comments (best signal; deep threads add noise).
    parts = [submission.title]
    if submission.selftext:
        parts.append(submission.selftext)
    for comment in list(submission.comments)[:20]:
        if hasattr(comment, "body") and len(comment.body) > 30:
            parts.append(comment.body)
    return RawPost(
        source="reddit",
        source_id=submission.id,
        raw_text="\n\n---\n\n".join(parts),
        url=f"https://reddit.com{submission.permalink}",
    )


def fetch_reddit(limit_per_term: int = 10) -> list[RawPost]:
    """Fetch posts from configured subreddits matching interview-question search terms.

    Args:
        limit_per_term: Max posts per (subreddit, search_term) pair.

    Returns:
        Deduplicated list of RawPost dicts.
    """
    reddit = _get_reddit()
    seen: set[str] = set()
    posts: list[RawPost] = []

    for subreddit_name in config.REDDIT_SUBREDDITS:
        subreddit = reddit.subreddit(subreddit_name)
        for term in config.REDDIT_SEARCH_TERMS:
            try:
                results = subreddit.search(term, sort="relevance", limit=limit_per_term)
                for submission in results:
                    if submission.id in seen:
                        continue
                    seen.add(submission.id)
                    posts.append(_post_to_raw(submission, reddit))
                    time.sleep(0.5)  # be polite to Reddit's API
            except Exception as exc:  # noqa: BLE001
                print(f"[scraper] Reddit {subreddit_name!r}/{term!r} failed: {exc}")

    print(f"[scraper] Reddit: fetched {len(posts)} unique posts.")
    return posts


# ---------------------------------------------------------------------------
# Stack Exchange
# ---------------------------------------------------------------------------

def fetch_stackexchange(page_size: int = 50) -> list[RawPost]:
    """Fetch high-scored questions from Stack Exchange sites via the public API.

    Uses the /questions endpoint with tag filters. No auth needed for read-only
    access; results are gzip-compressed automatically by the API.

    Args:
        page_size: Questions per API request per (site, tag) pair (max 100).

    Returns:
        Deduplicated list of RawPost dicts.
    """
    try:
        import httpx  # lazy import — optional dependency
    except ImportError as exc:
        raise ImportError(
            "httpx is not installed. Run: pip install httpx"
        ) from exc

    seen: set[str] = set()
    posts: list[RawPost] = []

    with httpx.Client(timeout=15) as client:
        for source in config.STACKEXCHANGE_SOURCES:
            site = source["site"]
            for tag in source["tags"]:
                uid = f"{site}:{tag}"
                if uid in seen:
                    continue
                seen.add(uid)
                try:
                    posts.extend(_fetch_se_tag(client, site, tag, page_size))
                    time.sleep(0.2)  # SE API: ~30 req/s unauthenticated
                except Exception as exc:  # noqa: BLE001
                    print(f"[scraper] StackExchange {site!r}/{tag!r} failed: {exc}")

    print(f"[scraper] StackExchange: fetched {len(posts)} unique posts.")
    return posts


def _fetch_se_tag(client, site: str, tag: str, page_size: int) -> list[RawPost]:
    """Fetch one page of tagged questions + their accepted/top answers."""
    params = {
        "order": "desc",
        "sort": "votes",
        "tagged": tag,
        "site": site,
        "pagesize": min(page_size, 100),
        "filter": "withbody",  # include question body in response
        "min": config.STACKEXCHANGE_MIN_SCORE,
    }
    resp = client.get("https://api.stackexchange.com/2.3/questions", params=params)
    resp.raise_for_status()
    data = resp.json()

    posts: list[RawPost] = []
    question_ids = [str(item["question_id"]) for item in data.get("items", [])]
    if not question_ids:
        return posts

    # Fetch answers in a single batch call to minimise API quota usage.
    answers_by_qid = _fetch_se_answers(client, site, question_ids)

    for item in data.get("items", []):
        qid = str(item["question_id"])
        parts = [item.get("title", ""), item.get("body", "")]
        for ans_body in answers_by_qid.get(qid, [])[:3]:
            parts.append(ans_body)
        posts.append(RawPost(
            source="stackexchange",
            source_id=f"{site}:{qid}",
            raw_text="\n\n---\n\n".join(p for p in parts if p),
            url=item.get("link", ""),
        ))

    return posts


def _fetch_se_answers(client, site: str, question_ids: list[str]) -> dict[str, list[str]]:
    """Return {question_id: [answer_body, ...]} for the given IDs (batch call)."""
    ids_str = ";".join(question_ids)
    params = {
        "order": "desc",
        "sort": "votes",
        "site": site,
        "filter": "withbody",
        "pagesize": 5,
    }
    try:
        resp = client.get(
            f"https://api.stackexchange.com/2.3/questions/{ids_str}/answers",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        return {}

    result: dict[str, list[str]] = {}
    for ans in data.get("items", []):
        qid = str(ans.get("question_id", ""))
        result.setdefault(qid, []).append(ans.get("body", ""))
    return result


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

def _get_github():
    """Return an authenticated (or anonymous) PyGithub Github instance."""
    try:
        from github import Github, Auth  # lazy import — optional dependency
    except ImportError as exc:
        raise ImportError(
            "PyGithub is not installed. Run: pip install PyGithub"
        ) from exc

    if config.GITHUB_TOKEN:
        return Github(auth=Auth.Token(config.GITHUB_TOKEN))
    # Unauthenticated still works; rate-limited to 60 req/hr.
    print("[scraper] GitHub: no GITHUB_TOKEN set — using unauthenticated (60 req/hr).")
    return Github()


def fetch_github() -> list[RawPost]:
    """Read markdown/text files from curated interview-prep repos on GitHub.

    For each repo in GITHUB_REPOS, we walk the file tree and collect all
    files matching GITHUB_FILE_EXTENSIONS that are under GITHUB_MAX_FILE_BYTES.
    Each file becomes one RawPost so the extractor can chunk it independently.

    Returns:
        Deduplicated list of RawPost dicts (one per file).
    """
    gh = _get_github()
    seen: set[str] = set()
    posts: list[RawPost] = []

    for repo_name in config.GITHUB_REPOS:
        try:
            repo = gh.get_repo(repo_name)
            posts.extend(_read_repo_files(repo, seen))
            time.sleep(0.5)  # stay well within rate limits
        except Exception as exc:  # noqa: BLE001
            print(f"[scraper] GitHub repo {repo_name!r} failed: {exc}")

    print(f"[scraper] GitHub: fetched {len(posts)} files across "
          f"{len(config.GITHUB_REPOS)} repos.")
    return posts


def _read_repo_files(repo, seen: set[str]) -> list[RawPost]:
    """Walk a repo's default branch and return one RawPost per eligible file."""
    posts: list[RawPost] = []
    try:
        contents = repo.get_contents("")
    except Exception as exc:  # noqa: BLE001
        print(f"[scraper] GitHub: could not read {repo.full_name}: {exc}")
        return posts

    # BFS over the directory tree.
    queue = list(contents)
    while queue:
        item = queue.pop(0)
        if item.type == "dir":
            try:
                queue.extend(repo.get_contents(item.path))
            except Exception:  # noqa: BLE001
                pass
            continue

        ext = "." + item.name.rsplit(".", 1)[-1].lower() if "." in item.name else ""
        if ext not in config.GITHUB_FILE_EXTENSIONS:
            continue
        if item.size > config.GITHUB_MAX_FILE_BYTES:
            continue

        source_id = f"{repo.full_name}:{item.path}"
        if source_id in seen:
            continue
        seen.add(source_id)

        try:
            text = item.decoded_content.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue

        posts.append(RawPost(
            source="github",
            source_id=source_id,
            raw_text=f"# {repo.full_name} — {item.path}\n\n{text}",
            url=item.html_url,
        ))
        time.sleep(0.1)  # gentle pacing within the repo walk

    return posts


# ---------------------------------------------------------------------------
# Hacker News
# ---------------------------------------------------------------------------

def fetch_hackernews() -> list[RawPost]:
    """Search HN via the Algolia API and return threads as RawPost dicts.

    Uses the Algolia HN search endpoint — no auth required, generous rate limits.
    Fetches the top-level post plus its top comments for each hit.

    Returns:
        Deduplicated list of RawPost dicts.
    """
    try:
        import httpx  # already required for SE; lazy-import for clarity
    except ImportError as exc:
        raise ImportError(
            "httpx is not installed. Run: pip install httpx"
        ) from exc

    seen: set[str] = set()
    posts: list[RawPost] = []

    with httpx.Client(timeout=15) as client:
        for term in config.HN_SEARCH_TERMS:
            try:
                hits = _search_hn(client, term)
                for hit in hits:
                    story_id = str(hit.get("objectID", ""))
                    if not story_id or story_id in seen:
                        continue
                    if hit.get("points", 0) < config.HN_MIN_POINTS:
                        continue
                    seen.add(story_id)
                    post = _hn_hit_to_raw(client, hit, story_id)
                    if post:
                        posts.append(post)
                    time.sleep(0.1)
            except Exception as exc:  # noqa: BLE001
                print(f"[scraper] HackerNews term {term!r} failed: {exc}")

    print(f"[scraper] HackerNews: fetched {len(posts)} unique threads.")
    return posts


def _search_hn(client, term: str) -> list[dict]:
    """Run one Algolia HN search and return the list of hit dicts."""
    resp = client.get(
        "https://hn.algolia.com/api/v1/search",
        params={
            "query": term,
            "tags": "story",          # only top-level stories, not comments
            "hitsPerPage": config.HN_MAX_RESULTS_PER_TERM,
        },
    )
    resp.raise_for_status()
    return resp.json().get("hits", [])


def _hn_hit_to_raw(client, hit: dict, story_id: str) -> RawPost | None:
    """Fetch a story's comment tree from the Firebase API and build a RawPost."""
    try:
        resp = client.get(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        )
        resp.raise_for_status()
        item = resp.json()
    except Exception:  # noqa: BLE001
        return None

    if not item:
        return None

    parts = []
    if item.get("title"):
        parts.append(item["title"])
    if item.get("text"):
        parts.append(item["text"])

    # Fetch top-level comments (kids) — one API call each, limit to 30.
    for kid_id in (item.get("kids") or [])[:30]:
        try:
            kid_resp = client.get(
                f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
            )
            kid_resp.raise_for_status()
            kid = kid_resp.json()
            if kid and kid.get("text") and len(kid["text"]) > 30:
                parts.append(kid["text"])
            time.sleep(0.05)
        except Exception:  # noqa: BLE001
            continue

    if not parts:
        return None

    return RawPost(
        source="hackernews",
        source_id=story_id,
        raw_text="\n\n---\n\n".join(parts),
        url=f"https://news.ycombinator.com/item?id={story_id}",
    )
