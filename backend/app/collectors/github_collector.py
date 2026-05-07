"""
GitHub data collector — PRs, commits, reviews, PR-comments, issues, issue-comments.
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

GITHUB_API        = "https://api.github.com"
PER_PAGE          = 100
DETAIL_CONCURRENCY = 5


class GitHubRateLimitError(Exception):
    pass


class GitHubCollector:
    def __init__(self, token: str | None = None):
        self.token = token or settings.GITHUB_TOKEN
        self.headers = {
            "Accept":               "application/vnd.github+json",
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

    # ── Pull Requests ─────────────────────────────────────────────────────────

    async def collect_pull_requests(
        self, repo_full_name: str, since: datetime | None = None
    ) -> list[dict]:
        """PRs с детальной статистикой (additions/deletions/changed_files)."""
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
                        detail = pr_basic

                jira_key = link_pr_to_jira(
                    pr_title    = detail.get("title", ""),
                    pr_body     = detail.get("body"),
                    branch_name = detail.get("head", {}).get("ref"),
                )
                return {
                    "gh_id":           detail["id"],
                    "repo_full_name":  repo_full_name,
                    "number":          detail["number"],
                    "title":           detail["title"],
                    "state":           detail["state"],
                    "author_login":    (detail.get("user") or {}).get("login"),
                    "html_url":        detail.get("html_url", ""),
                    "created_at":      _parse_gh_dt(detail.get("created_at", "")),
                    "merged_at":       _parse_gh_dt(detail.get("merged_at"))  if detail.get("merged_at")  else None,
                    "closed_at":       _parse_gh_dt(detail.get("closed_at"))  if detail.get("closed_at")  else None,
                    "additions":       detail.get("additions", 0)       or 0,
                    "deletions":       detail.get("deletions", 0)       or 0,
                    "changed_files":   detail.get("changed_files", 0)   or 0,
                    "review_comments": detail.get("review_comments", 0) or 0,
                    "commits_count":   detail.get("commits", 0)         or 0,
                    "jira_issue_key":  jira_key,
                }

            results = await asyncio.gather(*[_enrich_pr(pr) for pr in basic_prs])

        logger.info("GitHub %s: collected %d PRs", repo_full_name, len(results))
        return list(results)

    # ── Commits ───────────────────────────────────────────────────────────────

    async def collect_commits(
        self, repo_full_name: str, since: datetime | None = None
    ) -> list[dict]:
        """Коммиты с детальной статистикой (additions/deletions)."""
        basic_commits: list[dict] = []

        async with httpx.AsyncClient(timeout=30) as client:
            url    = f"{GITHUB_API}/repos/{repo_full_name}/commits"
            params = {}
            if since:
                params["since"] = since.isoformat()

            async for commit in self._paginate(client, url, params):
                basic_commits.append(commit)

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
                    "sha":            sha,
                    "repo_full_name": repo_full_name,
                    "author_login":   author.get("login"),
                    "author_email":   c_author.get("email"),
                    "message":        message,
                    "html_url":       detail.get("html_url", ""),
                    "committed_at":   _parse_gh_dt(c_author.get("date", "")),
                    "additions":      stats.get("additions", 0) or 0,
                    "deletions":      stats.get("deletions", 0) or 0,
                    "jira_issue_key": link_commit_to_jira(message),
                }

            results = await asyncio.gather(*[_enrich_commit(c) for c in basic_commits])

        logger.info("GitHub %s: collected %d commits", repo_full_name, len(results))
        return list(results)

    # ── Reviews ───────────────────────────────────────────────────────────────

    async def collect_reviews(
        self, repo_full_name: str, pr_number: int, pr_db_id: int
    ) -> list[dict]:
        """Ревью для конкретного PR."""
        url     = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
        results = []
        async with httpx.AsyncClient(timeout=30) as client:
            async for review in self._paginate(client, url):
                results.append({
                    "gh_id":          review["id"],
                    "pr_id":          pr_db_id,
                    "reviewer_login": (review.get("user") or {}).get("login"),
                    "state":          review["state"],
                    "html_url":       review.get("html_url", ""),
                    "submitted_at":   _parse_gh_dt(review.get("submitted_at", "")),
                    "body":           review.get("body"),
                })
        return results

    # ── Issues ────────────────────────────────────────────────────────────────

    async def collect_issues(
        self, repo_full_name: str, since: datetime | None = None
    ) -> list[dict]:
        """
        Все issues репозитория (включая закрытые).
        Pull requests в GitHub тоже являются issues — фильтруем их по наличию pull_request.
        """
        url    = f"{GITHUB_API}/repos/{repo_full_name}/issues"
        params: dict = {"state": "all", "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since.isoformat()

        results = []
        async with httpx.AsyncClient(timeout=30) as client:
            async for item in self._paginate(client, url, params):
                if "pull_request" in item:
                    continue  # Это PR, не issue
                assignee = item.get("assignee") or {}
                results.append({
                    "gh_id":           item["id"],
                    "repo_full_name":  repo_full_name,
                    "number":          item["number"],
                    "title":           item.get("title", ""),
                    "state":           item.get("state", "open"),
                    "author_login":    (item.get("user") or {}).get("login"),
                    "assignee_login":  assignee.get("login"),
                    "html_url":        item.get("html_url", ""),
                    "created_at":      _parse_gh_dt(item.get("created_at", "")),
                    "updated_at":      _parse_gh_dt(item.get("updated_at", "")),
                    "closed_at":       _parse_gh_dt(item.get("closed_at")) if item.get("closed_at") else None,
                    "labels":          [l["name"] for l in (item.get("labels") or [])],
                    "comments_count":  item.get("comments", 0),
                })

        logger.info("GitHub %s: collected %d issues", repo_full_name, len(results))
        return results

    # ── Issue comments ────────────────────────────────────────────────────────

    async def collect_issue_comments(
        self, repo_full_name: str, since: datetime | None = None
    ) -> list[dict]:
        """Все комментарии к issues (не PR-ревью)."""
        url    = f"{GITHUB_API}/repos/{repo_full_name}/issues/comments"
        params: dict = {"sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since.isoformat()

        results = []
        async with httpx.AsyncClient(timeout=30) as client:
            async for item in self._paginate(client, url, params):
                results.append({
                    "gh_id":          item["id"],
                    "repo_full_name": repo_full_name,
                    "author_login":   (item.get("user") or {}).get("login"),
                    "html_url":       item.get("html_url", ""),
                    "created_at":     _parse_gh_dt(item.get("created_at", "")),
                    "updated_at":     _parse_gh_dt(item.get("updated_at", "")),
                    "body":           (item.get("body") or "")[:500],
                    "issue_number":   _extract_issue_number(item.get("issue_url", "")),
                })

        logger.info("GitHub %s: collected %d issue comments", repo_full_name, len(results))
        return results

    # ── Org repos ─────────────────────────────────────────────────────────────

    async def get_repos_for_org(self, org: str) -> list[str]:
        """Список репозиториев организации."""
        url   = f"{GITHUB_API}/orgs/{org}/repos"
        repos = []
        async with httpx.AsyncClient(timeout=30) as client:
            async for repo in self._paginate(client, url, {"type": "all"}):
                repos.append(repo["full_name"])
        return repos

    async def get_pr_diff(self, repo: str, pr_number: int, max_chars: int = 4000) -> str | None:
        """Возвращает unified diff PR, обрезанный до max_chars."""
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return None
                diff = resp.text
                if len(diff) > max_chars:
                    diff = diff[:max_chars] + "\n... (diff обрезан)"
                return diff
        except Exception:
            return None

    async def get_repos_for_user(self, username: str) -> list[str]:
        """Список публичных и приватных репозиториев пользователя."""
        url   = f"{GITHUB_API}/users/{username}/repos"
        repos = []
        async with httpx.AsyncClient(timeout=30) as client:
            async for repo in self._paginate(client, url, {"type": "all", "sort": "updated"}):
                repos.append(repo["full_name"])
        return repos


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_gh_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _extract_issue_number(issue_url: str) -> int | None:
    """Извлекает номер issue из URL вида .../issues/123."""
    if not issue_url:
        return None
    parts = issue_url.rstrip("/").split("/")
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return None
