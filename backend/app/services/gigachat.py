"""
GigaChat service — оценка качества и сложности PR через LLM.
Документация: https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-token
"""
import json
import logging
import math
import re
import time
import uuid
import httpx

logger = logging.getLogger(__name__)

_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_API_URL   = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
_SCOPE     = "GIGACHAT_API_PERS"


from dataclasses import dataclass, field


@dataclass
class PRAssessment:
    quality_score:      float
    complexity_score:   float
    quality_label:      str
    complexity_label:   str
    quality_reasons:    list[str]
    complexity_reasons: list[str]
    ai_summary:         str | None = None
    is_stub:            bool = True


@dataclass
class OneOnOneTopic:
    topic:    str   # короткое название темы
    advice:   str   # совет менеджеру — что обсудить и зачем
    category: str   # "мотивация" / "нагрузка" / "блокеры" / "карьера"
    urgency:  int   # 1 = срочно, 2 = плановое


class GigaChatService:
    def __init__(self, auth_key: str | None = None):
        self.auth_key   = auth_key
        self.enabled    = bool(auth_key)
        self._token: str | None = None
        self._token_expires: float = 0.0

    # ── Public interface ───────────────────────────────────────────────────────

    async def assess_pr(
        self,
        title: str,
        body: str | None,
        additions: int,
        deletions: int,
        changed_files: int,
        review_comments: int,
        commits_count: int,
        diff: str | None = None,
    ) -> PRAssessment:
        if self.enabled:
            try:
                return await self._api_assess_pr(
                    title, body, additions, deletions,
                    changed_files, review_comments, commits_count, diff,
                )
            except Exception as e:
                logger.warning("GigaChat API error, falling back to stub: %s", e)
        return self._stub_assess_pr(
            additions, deletions, changed_files, review_comments, commits_count,
        )

    async def generate_one_on_one_topics(
        self,
        developer_name: str,
        burnout_risk_score: float,
        burnout_risk_level: str,
        velocity_trend: float,
        overall_score: float,
        delivery_score: float,
        quality_score: float,
        collaboration_score: float,
        consistency_score: float,
        after_hours_ratio: float,
        weekend_activity_ratio: float,
    ) -> list[OneOnOneTopic]:
        if self.enabled:
            try:
                return await self._api_one_on_one(
                    developer_name, burnout_risk_score, burnout_risk_level,
                    velocity_trend, overall_score, delivery_score, quality_score,
                    collaboration_score, consistency_score,
                    after_hours_ratio, weekend_activity_ratio,
                )
            except Exception as e:
                logger.warning("GigaChat API error, falling back to stub: %s", e)
        return self._stub_one_on_one(
            burnout_risk_score, burnout_risk_level, velocity_trend,
            overall_score, after_hours_ratio, weekend_activity_ratio,
        )

    # ── OAuth token ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_json(raw: str) -> dict | list:
        """Извлекает JSON из ответа, устойчив к markdown-обёртке и обрезке."""
        raw = raw.strip()
        # Убираем ```json ... ``` или ``` ... ```
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```\s*$', '', raw)
        raw = raw.strip()
        # Пробуем напрямую
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Ищем первый полный JSON-объект или массив через regex
        for pattern in (r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', r'\[.*?\]'):
            m = re.search(pattern, raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        raise ValueError(f"Cannot extract JSON from: {raw[:200]!r}")

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.post(
                _OAUTH_URL,
                headers={
                    "Authorization": f"Basic {self.auth_key}",
                    "RqUID": str(uuid.uuid4()),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"scope": _SCOPE},
            )
            resp.raise_for_status()
            data = resp.json()

        self._token         = data["access_token"]
        self._token_expires = data.get("expires_at", 0) / 1000  # ms → s
        return self._token

    async def _chat(self, messages: list[dict], max_tokens: int = 800) -> str:
        token = await self._get_token()
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.post(
                _API_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "GigaChat",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    # ── Real API implementations ───────────────────────────────────────────────

    async def _api_assess_pr(
        self,
        title: str,
        body: str | None,
        additions: int,
        deletions: int,
        changed_files: int,
        review_comments: int,
        commits_count: int,
        diff: str | None = None,
    ) -> PRAssessment:
        diff_section = f"\nDiff изменений:\n```diff\n{diff}\n```" if diff else ""

        prompt = f"""Проанализируй Pull Request. Верни ТОЛЬКО JSON, без пояснений.

PR: {title}
+{additions}/-{deletions} строк, {changed_files} файлов, {review_comments} комментариев, {commits_count} коммитов{diff_section}

JSON (строго, без markdown):
{{
  "quality_score": <0-100>,
  "complexity_score": <0-100>,
  "quality_label": "<высокое|среднее|низкое>",
  "complexity_label": "<высокая|средняя|низкая>",
  "quality_reasons": ["<причина, макс 10 слов>"],
  "complexity_reasons": ["<причина, макс 10 слов>"],
  "ai_summary": "<одно предложение: что изменено и зачем>"
}}"""

        raw = await self._chat([{"role": "user", "content": prompt}], max_tokens=700)
        data = self._extract_json(raw)

        return PRAssessment(
            quality_score      = float(data.get("quality_score") or 70),
            complexity_score   = float(data.get("complexity_score") or 50),
            quality_label      = data.get("quality_label") or "среднее",
            complexity_label   = data.get("complexity_label") or "средняя",
            quality_reasons    = data.get("quality_reasons") or [],
            complexity_reasons = data.get("complexity_reasons") or [],
            ai_summary         = data.get("ai_summary") or None,
            is_stub            = False,
        )

    async def _api_one_on_one(
        self,
        developer_name: str,
        burnout_risk_score: float,
        burnout_risk_level: str,
        velocity_trend: float,
        overall_score: float,
        delivery_score: float,
        quality_score: float,
        collaboration_score: float,
        consistency_score: float,
        after_hours_ratio: float,
        weekend_activity_ratio: float,
    ) -> list[OneOnOneTopic]:
        risk_map   = {"low": "низкий", "medium": "средний", "high": "высокий"}
        risk_ru    = risk_map.get(burnout_risk_level, burnout_risk_level)
        trend_str  = f"+{velocity_trend:.1%}" if velocity_trend >= 0 else f"{velocity_trend:.1%}"

        prompt = f"""Ты опытный инженерный менеджер. Подготовь темы для встречи 1:1 — не вопросы, а конкретные советы что обсудить и зачем.

Разработчик: {developer_name}

Метрики за последнюю неделю (0–100, выше = лучше):
- Общий score: {overall_score:.0f}/100
- Поставка: {delivery_score:.0f}/100 — скорость закрытия Jira-задач vs личный baseline
- Качество: {quality_score:.0f}/100 — code health + AI-оценка PR (CHANGES_REQUESTED, churn кода)
- Коллаборация: {collaboration_score:.0f}/100 — содержательность ревью-комментариев + скорость получения ревью
- Стабильность: {consistency_score:.0f}/100 — равномерность рабочего дня (низкий = хаотичный график)
- Тренд velocity: {trend_str} — изменение throughput vs baseline последних 4 недель
- Риск выгорания: {risk_ru} ({burnout_risk_score:.0%})
- Активность вне рабочих часов (после 19:00 / до 9:00): {after_hours_ratio:.0%}
- Активность по выходным: {weekend_activity_ratio:.0%}

Сгенерируй 3-5 тем для обсуждения. Каждая тема — это совет менеджеру: что обсудить, на что обратить внимание и почему это важно именно сейчас. Фокусируйся только на аномалиях — не упоминай метрики которые в норме.

Верни строго JSON без markdown:
[
  {{
    "topic": "<короткое название темы, 3-6 слов>",
    "advice": "<совет менеджеру: что конкретно обсудить, какой сигнал это даёт, что нужно выяснить — 2-3 предложения>",
    "category": "<мотивация|нагрузка|блокеры|карьера>",
    "urgency": <1 срочно|2 плановое>
  }}
]"""

        raw = await self._chat([{"role": "user", "content": prompt}], max_tokens=900)
        items = self._extract_json(raw)

        topics = [
            OneOnOneTopic(
                topic    = item.get("topic", ""),
                advice   = item.get("advice", ""),
                category = item.get("category", "мотивация"),
                urgency  = int(item.get("urgency", 2)),
            )
            for item in items
        ]
        return sorted(topics, key=lambda t: t.urgency)

    # ── Stub implementations ───────────────────────────────────────────────────

    def _stub_assess_pr(
        self,
        additions: int,
        deletions: int,
        changed_files: int,
        review_comments: int,
        commits_count: int,
    ) -> PRAssessment:
        total_lines = additions + deletions

        raw_complexity = math.log1p(total_lines) * 10 + changed_files * 2
        complexity = min(100.0, raw_complexity)

        complexity_reasons = []
        if total_lines > 500:
            complexity_reasons.append(f"Большой объём изменений: {total_lines} строк")
        if changed_files > 20:
            complexity_reasons.append(f"Много файлов: {changed_files}")
        if commits_count > 10:
            complexity_reasons.append(f"Много коммитов: {commits_count}")
        if not complexity_reasons:
            complexity_reasons.append("Стандартный размер PR")

        quality = 70.0
        if review_comments >= 3:
            quality += 15
        elif review_comments == 0 and total_lines > 200:
            quality -= 20
        if total_lines > 1000:
            quality -= 15
        if changed_files > 30:
            quality -= 10
        quality = max(10.0, min(100.0, quality))

        quality_reasons = []
        if review_comments >= 3:
            quality_reasons.append(f"Активное ревью: {review_comments} комментариев")
        elif review_comments == 0:
            quality_reasons.append("Ревью без комментариев")
        if total_lines > 1000:
            quality_reasons.append("PR слишком большой — рекомендуется разбить")
        if not quality_reasons:
            quality_reasons.append("Стандартный PR")

        def _q_label(v):
            if v >= 75: return "высокое"
            if v >= 45: return "среднее"
            return "низкое"

        def _c_label(v):
            if v >= 70: return "высокая"
            if v >= 35: return "средняя"
            return "низкая"

        return PRAssessment(
            quality_score     = round(quality,     1),
            complexity_score  = round(complexity,  1),
            quality_label     = _q_label(quality),
            complexity_label  = _c_label(complexity),
            quality_reasons   = quality_reasons,
            complexity_reasons= complexity_reasons,
            is_stub           = True,
        )

    def _stub_one_on_one(
        self,
        burnout_risk_score: float,
        burnout_risk_level: str,
        velocity_trend: float,
        overall_score: float,
        after_hours_ratio: float,
        weekend_activity_ratio: float,
    ) -> list[OneOnOneTopic]:
        topics: list[OneOnOneTopic] = []

        if burnout_risk_level in ("high", "medium"):
            topics.append(OneOnOneTopic(
                topic="Риск выгорания",
                advice="Метрики фиксируют высокую нагрузку. Обсудите текущий объём задач и ощущение от темпа работы. Выясните, есть ли внешнее давление или задачи которые можно делегировать.",
                category="нагрузка", urgency=1,
            ))
        if after_hours_ratio > 0.3:
            topics.append(OneOnOneTopic(
                topic="Активность в нерабочее время",
                advice=f"{after_hours_ratio:.0%} активности приходится на время после 19:00 или до 9:00. Выясните причину: личные предпочтения, давление дедлайнов или проблемы с фокусом в течение дня. Если это системно — стоит пересмотреть нагрузку.",
                category="нагрузка", urgency=1,
            ))
        if weekend_activity_ratio > 0.2:
            topics.append(OneOnOneTopic(
                topic="Работа по выходным",
                advice=f"Зафиксирована активность в {weekend_activity_ratio:.0%} выходных дней. Уточните, это осознанный выбор или ощущение что без этого не успеть. Регулярная работа по выходным — ранний признак выгорания.",
                category="нагрузка", urgency=1,
            ))
        if velocity_trend < -0.05:
            topics.append(OneOnOneTopic(
                topic="Снижение скорости",
                advice="Throughput снизился относительно личного baseline. Обсудите что изменилось: новые сложные задачи, технический долг, блокеры от смежных команд или личные обстоятельства.",
                category="блокеры", urgency=1,
            ))
        if overall_score < 50:
            topics.append(OneOnOneTopic(
                topic="Общее снижение эффективности",
                advice="Несколько метрик одновременно ниже нормы. Это сигнал для открытого разговора — не для оценки, а для понимания что происходит и чем можно помочь.",
                category="блокеры", urgency=1,
            ))
        if velocity_trend > 0.1:
            topics.append(OneOnOneTopic(
                topic="Высокая динамика — закрепить успех",
                advice="Хороший момент чтобы зафиксировать что именно работает. Обсудите что изменилось в последнее время и как сохранить этот темп без перегрузки.",
                category="мотивация", urgency=2,
            ))
        topics.append(OneOnOneTopic(
            topic="Карьерный вектор",
            advice="Плановая тема для каждой 1:1: какие направления интересны, чего не хватает в текущих задачах, есть ли навыки которые хочется развить в ближайший квартал.",
            category="карьера", urgency=2,
        ))
        return sorted(topics, key=lambda t: t.urgency)


def get_gigachat() -> GigaChatService:
    from app.core.config import settings
    return GigaChatService(auth_key=settings.GIGACHAT_AUTH_KEY)
