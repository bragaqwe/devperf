"""
Jira data collector — REST API v3. VERSION 5.
/rest/api/3/search (GET) — отключён в этом Jira Cloud instance (410).
Используем ТОЛЬКО POST /rest/api/3/search/jql без expand=changelog.
Changelog тянем отдельно через GET /rest/api/3/issue/{key}/changelog.
Пагинация: сначала пробуем nextPageToken (cursor-based), затем startAt (offset).
"""
import logging
from datetime import datetime
from typing import Any
from base64 import b64encode

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.core.config import settings

logger = logging.getLogger(__name__)

# Только гарантированно существующие стандартные поля.
# Кастомные поля (story points) запрашиваем отдельно через field-lookup,
# чтобы не получать 400 "Invalid request payload" если поля нет в проекте.
FIELDS_STANDARD = [
    "summary", "status", "assignee", "reporter", "priority",
    "issuetype", "created", "updated", "resolutiondate",
]
# Кандидаты на story points — пробуем все известные варианты
STORY_POINTS_FIELDS = [
    "customfield_10016",  # Jira Software (классический)
    "customfield_10028",  # Jira Next-gen / newer cloud
    "customfield_10034",  # некоторые инстансы
    "story_points",       # некоторые конфигурации
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
        logger.debug("JiraCollector initialized for %s", self.base_url)

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

        page_size  = 50
        fetched    = 0
        all_raw    = []
        next_page_token: str | None = None

        async with httpx.AsyncClient(timeout=60) as client:
            # Определяем доступные story points поля один раз
            sp_field = await self._detect_story_points_field(client)
            fields_to_fetch = list(FIELDS_STANDARD)
            if sp_field:
                fields_to_fetch.append(sp_field)

            # ШАГ 1 — POST /search/jql
            # ВАЖНО: POST /search/jql (новый Cloud API) НЕ поддерживает startAt.
            # Отправка startAt вызывает 400 "Invalid request payload".
            # Пагинация только через nextPageToken из ответа.
            while fetched < max_results:
                body: dict = {
                    "jql":        jql,
                    "maxResults": page_size,
                    "fields":     fields_to_fetch,
                    # startAt — НЕ отправляем (400 на Cloud API)
                    # expand  — НЕ отправляем (400)
                }
                if next_page_token:
                    body["nextPageToken"] = next_page_token

                data = await self._post(
                    client,
                    f"{self.base_url}/rest/api/3/search/jql",
                    body=body,
                )

                issues = data.get("issues", [])
                if not issues:
                    break

                all_raw.extend(issues)
                fetched += len(issues)

                total     = data.get("total")          # offset API
                is_last   = data.get("isLast", False)  # cursor API
                next_page_token = data.get("nextPageToken")  # cursor API

                logger.info("  Jira: fetched %d%s", fetched,
                            f"/{total}" if total is not None else "")

                if is_last or not next_page_token and (
                    (total is not None and fetched >= total)
                    or len(issues) < page_size
                ):
                    break

            # ШАГ 2 — Changelog для каждого issue отдельно
            result = []
            for i, raw in enumerate(all_raw):
                entries = await self._fetch_changelog(client, raw["key"])
                raw["_changelog_entries"] = entries
                result.append(self._parse_issue(raw))
                if (i + 1) % 10 == 0:
                    logger.info("  Changelog: %d/%d", i + 1, len(all_raw))

        logger.info("  Jira done: %d issues", len(result))
        return result

    async def _detect_story_points_field(self, client: httpx.AsyncClient) -> str | None:
        """Определяет какой custom field используется для story points в этом инстансе."""
        try:
            fields = await self._get(client, f"{self.base_url}/rest/api/3/field")
            for f in fields:
                name = (f.get("name") or "").lower()
                if "story" in name and "point" in name:
                    logger.info("  Story points field: %s (%s)", f["id"], f["name"])
                    return f["id"]
        except Exception as e:
            logger.warning("  Cannot detect story points field: %s", e)
        # Fallback — попробуем классический вариант
        return "customfield_10016"

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
                logger.warning("  Changelog %s: %s", issue_key, e.response.status_code)
                break
        return entries

    def _parse_jira_datetime(self, dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        try:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            try:
                return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                return None

    def _parse_issue(self, raw: dict) -> dict:
        fields = raw.get("fields", {})
        changelog_entries = raw.get("_changelog_entries", [])

        transitions = self._parse_transitions(raw["id"], changelog_entries)

        assignee = fields.get("assignee") or {}
        # Ищем story points в любом из известных кастомных полей
        story_points = None
        for sp_key in STORY_POINTS_FIELDS:
            val = fields.get(sp_key)
            if val is not None and isinstance(val, (int, float)):
                story_points = float(val)
                break

        return {
            "jira_id":             raw["id"],
            "key":                 raw["key"],
            "project_key":         raw["key"].split("-")[0],
            "issue_type":          (fields.get("issuetype") or {}).get("name", "Unknown"),
            "summary":             fields.get("summary", ""),
            "status":              (fields.get("status") or {}).get("name", "Unknown"),
            "assignee_account_id": assignee.get("accountId"),
            "reporter_account_id": (fields.get("reporter") or {}).get("accountId"),
            "priority":            (fields.get("priority") or {}).get("name"),
            "story_points":        story_points,
            "created_at":          self._parse_jira_datetime(fields.get("created")),
            "updated_at":          self._parse_jira_datetime(fields.get("updated")),
            "resolved_at":         self._parse_jira_datetime(fields.get("resolutiondate")),
            "raw_data":            raw,
            "transitions":         transitions,
        }

    def _parse_transitions(self, issue_id: str, entries: list) -> list[dict]:
        transitions = []
        for history in entries:
            for item in history.get("items", []):
                if item.get("field") == "status":
                    try:
                        transitioned_at = datetime.strptime(
                            history.get("created"), "%Y-%m-%dT%H:%M:%S.%f%z"
                        )
                    except (ValueError, TypeError):
                        continue
                    transitions.append({
                        "issue_id":           issue_id,
                        "from_status":        item.get("fromString"),
                        "to_status":          item.get("toString", ""),
                        "author_account_id":  (history.get("author") or {}).get("accountId"),
                        "transitioned_at":    transitioned_at,
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
                        "account_id":   u.get("accountId"),
                        "display_name": u.get("displayName", ""),
                        "email":        u.get("emailAddress"),
                    }
                    for u in data if u.get("accountId")
                ]
            except Exception as e:
                logger.warning("Members fetch failed: %s", e)
                return []

    async def test_connection(self, project_key: str = "CORE") -> dict:
        """Диагностика подключения к Jira: проверяем аутентификацию и доступ к проекту."""
        result: dict = {
            "base_url":    self.base_url,
            "auth_ok":     False,
            "project_ok":  False,
            "issue_count": None,
            "error":       None,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Проверяем себя (текущий пользователь)
            try:
                me = await self._get(client, f"{self.base_url}/rest/api/3/myself")
                result["auth_ok"]    = True
                result["account_id"] = me.get("accountId")
                result["email"]      = me.get("emailAddress")
            except Exception as e:
                result["error"] = f"Auth failed: {e}"
                return result

            # 2. Проверяем доступ к проекту
            try:
                proj = await self._get(
                    client,
                    f"{self.base_url}/rest/api/3/project/{project_key}",
                )
                result["project_ok"]   = True
                result["project_name"] = proj.get("name")
            except httpx.HTTPStatusError as e:
                result["error"] = f"Project {project_key} not accessible: {e.response.status_code}"
                return result

            # 3. Сколько задач в проекте
            try:
                body = {
                    "jql":        f"project = {project_key}",
                    "maxResults": 1,
                    "fields":     ["summary"],
                }
                data = await self._post(
                    client,
                    f"{self.base_url}/rest/api/3/search/jql",
                    body=body,
                )
                result["issue_count"] = data.get("total")
            except Exception as e:
                result["error"] = f"Search failed: {e}"

        return result
