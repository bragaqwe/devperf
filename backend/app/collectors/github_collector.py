"""
GitHub data collector — pulls PRs, commits, reviews via REST API.

Изменения:
  - PR list: после сбора делаем детальный GET /pulls/{number} для additions/deletions
  - Commits list: после сбора делаем детальный GET /commits/{sha} для stats
  - html_url добавлен во все объекты
  - id убран (Integer PK генерирует PostgreSQL)
  - Батчевые детальные запросы с concurrency-limit чтобы не бить rate limit
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.services.linker import link_pr_to_jira, link_commit_to_jira

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
PER_PAGE   = 100
# Максимум параллельных детальных запросов (осторожно с rate limit)
DETAIL_CONCURRENCY = 5


class GitHubRateLimitError(Exception):
    pass


class GitHubCollector:
    def __init__(self, token: str | None = None):
        self.token = token or settings.GITHUB_TOKEN
        self.headers = {
            "Accept":              "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    @retry(
        retry=retry_if_exception_type(GitHubRateLimitError),
        wait=wait_exponential(multiplier=2, min=10, max=120),
        stop=stop_after_attempt(5),
    )
    async def _get(self, client: httpx.AsyncClient, url: str, params: dict = None) -> Any:
        resp = await client.get(url, params=params, headers=self.headers, timeout=30)
        if resp.status_code in (403, 429):
            reset = resp.headers.get("X-RateLimit-Reset")
            logger.warning("GitHub rate limit hit. Reset at %s", reset)
            raise GitHubRateLimitError("Rate limited")
        resp.raise_for_status()
        return resp.json()

    async def _paginate(
        self, client: httpx.AsyncClient, url: str, params: dict = None
    ) -> AsyncGenerator[dict, None]:
        params = dict(params or {})
        params["per_page"] = PER_PAGE
        page = 1
        while True:
            params["page"] = page
            data = await self._get(client, url, params)
            if not data:
                break
            for item in data:
                yield item
            if len(data) < PER_PAGE:
                break
            page += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Pull Requests
    # ─────────────────────────────────────────────────────────────────────────

    async def collect_pull_requests(
        self, repo_full_name: str, since: datetime | None = None
    ) -> list[dict]:
        """
        Собирает все PR репозитория.
        Для каждого PR делает детальный запрос чтобы получить
        additions, deletions, changed_files (их нет в list endpoint).
        """
        basic_prs: list[dict] = []

        async with httpx.AsyncClient(timeout=30) as client:
            url    = f"{GITHUB_API}/repos/{repo_full_name}/pulls"
            params = {"state": "all", "sort": "updated", "direction": "desc"}

            async for pr in self._paginate(client, url, params):
                if since:
                    updated = _parse_gh_dt(pr.get("updated_at", ""))
                    if updated and updated < since:
                        break
                basic_prs.append(pr)

            # Детальные данные (additions/deletions) — батчами по DETAIL_CONCURRENCY
            results: list[dict] = []
            sem = asyncio.Semaphore(DETAIL_CONCURRENCY)

            async def _enrich_pr(pr_basic: dict) -> dict:
                async with sem:
                    try:
                        detail = await self._get(
                            client,
                            f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_basic['number']}",
                        )
                    except Exception as e:
                        logger.warning("Cannot fetch PR detail %s#%s: %s",
                                       repo_full_name, pr_basic["number"], e)
                        detail = pr_basic  # fallback — без статистики

                jira_key = link_pr_to_jira(
                    pr_title  = detail.get("title", ""),
                    pr_body   = detail.get("body"),
                    branch_name = detail.get("head", {}).get("ref"),
                )
                return {
                    # id не указываем — autoincrement в PostgreSQL
                    "gh_id":          detail["id"],
                    "repo_full_name": repo_full_name,
                    "number":         detail["number"],
                    "title":          detail["title"],
                    "state":          detail["state"],
                    "author_login":   (detail.get("user") or {}).get("login"),
                    "html_url":       detail.get("html_url", ""),
                    "created_at":     _parse_gh_dt(detail.get("created_at", "")),
                    "merged_at":      _parse_gh_dt(detail.get("merged_at")) if detail.get("merged_at") else None,
                    "closed_at":      _parse_gh_dt(detail.get("closed_at"))  if detail.get("closed_at")  else None,
                    "additions":      detail.get("additions", 0) or 0,
                    "deletions":      detail.get("deletions", 0) or 0,
                    "changed_files":  detail.get("changed_files", 0) or 0,
                    "review_comments":detail.get("review_comments", 0) or 0,
                    "commits_count":  detail.get("commits", 0) or 0,
                    "jira_issue_key": jira_key,
                }

            tasks = [_enrich_pr(pr) for pr in basic_prs]
            results = await asyncio.gather(*tasks)

        logger.info("GitHub %s: collected %d PRs (with stats)", repo_full_name, len(results))
        return list(results)

    # ─────────────────────────────────────────────────────────────────────────
    # Commits
    # ─────────────────────────────────────────────────────────────────────────

    async def collect_commits(
        self, repo_full_name: str, since: datetime | None = None
    ) -> list[dict]:
        """
        Собирает коммиты репозитория.
        Для каждого коммита делает детальный запрос чтобы получить
        stats.additions / stats.deletions (их нет в list endpoint).
        """
        basic_commits: list[dict] = []

        async with httpx.AsyncClient(timeout=30) as client:
            url    = f"{GITHUB_API}/repos/{repo_full_name}/commits"
            params = {}
            if since:
                params["since"] = since.isoformat()

            async for commit in self._paginate(client, url, params):
                basic_commits.append(commit)

            # Детальные данные — батчами
            sem = asyncio.Semaphore(DETAIL_CONCURRENCY)

            async def _enrich_commit(c_basic: dict) -> dict:
                sha = c_basic["sha"]
                async with sem:
                    try:
                        detail = await self._get(
                            client,
                            f"{GITHUB_API}/repos/{repo_full_name}/commits/{sha}",
                        )
                    except Exception as e:
                        logger.warning("Cannot fetch commit detail %s@%s: %s",
                                       repo_full_name, sha[:8], e)
                        detail = c_basic

                c_obj    = detail.get("commit", {})
                author   = detail.get("author") or {}
                c_author = c_obj.get("author") or {}
                stats    = detail.get("stats", {}) or {}
                message  = c_obj.get("message", "")

                return {
                    # id не указываем — autoincrement
                    "sha":           sha,
                    "repo_full_name": repo_full_name,
                    "author_login":  author.get("login"),
                    "author_email":  c_author.get("email"),
                    "message":       message,
                    "html_url":      detail.get("html_url", ""),
                    "committed_at":  _parse_gh_dt(c_author.get("date", "")),
                    "additions":     stats.get("additions", 0) or 0,
                    "deletions":     stats.get("deletions", 0) or 0,
                    "jira_issue_key": link_commit_to_jira(message),
                }

            tasks   = [_enrich_commit(c) for c in basic_commits]
            results = await asyncio.gather(*tasks)

        logger.info("GitHub %s: collected %d commits (with stats)", repo_full_name, len(results))
        return list(results)

    # ─────────────────────────────────────────────────────────────────────────
    # Reviews
    # ─────────────────────────────────────────────────────────────────────────

    async def collect_reviews(
        self, repo_full_name: str, pr_number: int, pr_db_id: int
    ) -> list[dict]:
        """Собирает ревью для конкретного PR."""
        url     = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
        results = []

        async with httpx.AsyncClient(timeout=30) as client:
            async for review in self._paginate(client, url):
                results.append({
                    # id не указываем — autoincrement
                    "gh_id":           review["id"],
                    "pr_id":           pr_db_id,
                    "reviewer_login":  (review.get("user") or {}).get("login"),
                    "state":           review["state"],
                    "html_url":        review.get("html_url", ""),
                    "submitted_at":    _parse_gh_dt(review.get("submitted_at", "")),
                    "body":            review.get("body"),
                })
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Org repos
    # ─────────────────────────────────────────────────────────────────────────

    async def get_repos_for_org(self, org: str) -> list[str]:
        """Список репозиториев организации."""
        url   = f"{GITHUB_API}/orgs/{org}/repos"
        repos = []
        async with httpx.AsyncClient(timeout=30) as client:
            async for repo in self._paginate(client, url, {"type": "all"}):
                repos.append(repo["full_name"])
        return repos


# ─────────────────────────────────────────────────────────────────────────────

def _parse_gh_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
