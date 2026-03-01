"""
Jira data collector — REST API v3. VERSION 4.
/rest/api/3/search (GET) — отключён в этом Jira Cloud instance (410).
Используем ТОЛЬКО POST /rest/api/3/search/jql без expand=changelog.
Changelog тянем отдельно через GET /rest/api/3/issue/{key}/changelog.
"""
import uuid
import logging
from datetime import datetime
from typing import Any
from base64 import b64encode

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.core.config import settings

logger = logging.getLogger(__name__)

FIELDS = [
    "summary", "status", "assignee", "reporter", "priority",
    "issuetype", "created", "updated", "resolutiondate",
    "labels", "duedate",
    "customfield_10016",
    "customfield_10028",
]


def _is_retryable(exc: BaseException) -> bool:
    """Retry только на временные ошибки — НЕ на 400/410."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError))


class JiraCollector:
    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        self.base_url = (base_url or settings.JIRA_BASE_URL or "").rstrip("/")
        email = email or settings.JIRA_EMAIL or ""
        token = api_token or settings.JIRA_API_TOKEN or ""
        creds = b64encode(f"{email}:{token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        print(self.headers)

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=2, max=30),
        stop=stop_after_attempt(4),
    )
    async def _post(self, client: httpx.AsyncClient, url: str, body: dict) -> Any:
        resp = await client.post(url, json=body, headers=self.headers)
        if not resp.is_success:
            logger.error(f"Jira POST {url} → {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=2, max=30),
        stop=stop_after_attempt(4),
    )
    async def _get(self, client: httpx.AsyncClient, url: str, params: dict = None) -> Any:
        resp = await client.get(url, params=params, headers=self.headers)
        if not resp.is_success:
            logger.error(f"Jira GET {url} → {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
        return resp.json()

    async def collect_issues(
        self,
        project_key: str,
        updated_after: datetime | None = None,
        max_results: int = 5000,
    ) -> list[dict]:
        jql = f"project = {project_key} ORDER BY updated DESC"
        if updated_after:
            ts = updated_after.strftime("%Y-%m-%d %H:%M")
            jql = f"project = {project_key} AND updated >= '{ts}' ORDER BY updated DESC"

        start_at = 0
        page_size = 50
        all_raw = []

        async with httpx.AsyncClient(timeout=60) as client:
            # ШАГ 1 — POST /search/jql БЕЗ expand
            while start_at < max_results:
                body = {
                    "jql": jql,
                    # "startAt": start_at,
                    "maxResults": page_size,
                    "fields": FIELDS,
                    
                    # НЕТ "expand" — именно это вызывало 400
                }
                data = await self._post(
                    client,
                    f"{self.base_url}/rest/api/3/search/jql",
                    body=body
                )

                print("RESULT", data)
                


                issues = data.get("issues", [])
                if not issues:
                    break

                all_raw.extend(issues)
                start_at += len(issues)
                total = data.get("total", 0)
                logger.info(f"  Jira: fetched {start_at}/{total}")
                if start_at >= total:
                    break

            # ШАГ 2 — Changelog для каждого issue отдельно
            result = []
            for i, raw in enumerate(all_raw):
                entries = await self._fetch_changelog(client, raw["key"])
                raw["_changelog_entries"] = entries
                result.append(self._parse_issue(raw))
                if (i + 1) % 10 == 0:
                    logger.info(f"  Changelog: {i + 1}/{len(all_raw)}")

        logger.info(f"  Jira done: {len(result)} issues")
        return result

    async def _fetch_changelog(self, client: httpx.AsyncClient, issue_key: str) -> list:
        entries = []
        start_at = 0
        while True:
            try:
                data = await self._get(
                    client,
                    f"{self.base_url}/rest/api/3/issue/{issue_key}/changelog",
                    params={"startAt": start_at, "maxResults": 100},
                )
                page = data.get("values", [])
                entries.extend(page)
                start_at += len(page)
                if start_at >= data.get("total", 0) or not page:
                    break
            except httpx.HTTPStatusError as e:
                logger.warning(f"  Changelog {issue_key}: {e.response.status_code}")
                break
        return entries
    from datetime import datetime

    def _parse_jira_datetime(self, dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        try:
            # Jira возвращает формат вида: "2026-02-26T14:23:00.000+0000"
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            try:
                # Иногда может быть без миллисекунд
                return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                return None

    def _parse_issue(self, raw: dict) -> dict:
        fields = raw.get("fields", {})
        changelog_entries = raw.get("_changelog_entries", [])

        transitions = self._parse_transitions(raw["id"], changelog_entries)
        reopen_count = sum(
            1 for t in transitions
            if t["to_status"].lower() in ("open", "reopened", "to do", "backlog")
            and t.get("from_status", "").lower() in ("done", "closed", "resolved")
        )

        assignee = fields.get("assignee") or {}
        story_points = fields.get("customfield_10016") or fields.get("customfield_10028")
        if isinstance(story_points, (int, float)):
            story_points = float(story_points)
        else:
            story_points = None

        return {
    # "id": str(uuid.uuid4()),
    "jira_id": raw["id"],
    "key": raw["key"],
    "project_key": raw["key"].split("-")[0],
    "issue_type": (fields.get("issuetype") or {}).get("name", "Unknown"),
    "summary": fields.get("summary", ""),
    "status": (fields.get("status") or {}).get("name", "Unknown"),
    "assignee_account_id": assignee.get("accountId"),
    "reporter_account_id": (fields.get("reporter") or {}).get("accountId"),
    "priority": (fields.get("priority") or {}).get("name"),
    "story_points": story_points,
    "created_at": self._parse_jira_datetime(fields.get("created")),
    "updated_at": self._parse_jira_datetime(fields.get("updated")),
    "resolved_at": self._parse_jira_datetime(fields.get("resolutiondate")),
    "due_date": self._parse_jira_datetime(fields.get("duedate")),
    "reopen_count": reopen_count,
    "labels": fields.get("labels", []),
    "raw_data": raw,
    "transitions": transitions,
}

    def _parse_transitions(self, issue_id: str, entries: list) -> list[dict]:
        transitions = []
        for history in entries:
            for item in history.get("items", []):
                if item.get("field") == "status":
                    transitions.append({
                        # "id": str(uuid.uuid4()),
                        "issue_id": issue_id,
                        "from_status": item.get("fromString"),
                        "to_status": item.get("toString", ""),
                        "author_account_id": (history.get("author") or {}).get("accountId"),
                        "transitioned_at": datetime.strptime(history.get("created"),   "%Y-%m-%dT%H:%M:%S.%f%z"),
                    })
        return transitions
    

    async def get_project_members(self, project_key: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                data = await self._get(
                    client,
                    f"{self.base_url}/rest/api/3/user/assignable/search",
                    params={"project": project_key, "maxResults": 200},
                )
                return [
                    {
                        "account_id": u.get("accountId"),
                        "display_name": u.get("displayName", ""),
                        "email": u.get("emailAddress"),
                    }
                    for u in data if u.get("accountId")
                ]
            except Exception as e:
                logger.warning(f"Members fetch failed: {e}")
                return []
