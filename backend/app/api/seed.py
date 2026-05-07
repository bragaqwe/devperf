"""
POST /seed/demo  — создаёт 3 синтетических разработчика с реалистичными данными.
Идемпотентно: повторный вызов пересоздаёт данные с нуля.
"""
import random
import hashlib
from datetime import datetime, timezone, timedelta, date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.db.models import (
    Developer, Team,
    GitHubCommit, GitHubPullRequest, GitHubReview,
    JiraIssue, ActivityEvent, ActivityType,
    DailyMetric, PerformanceScore, PRGigaChatAssessment,
)

seed_router = APIRouter()

# ── Константы ──────────────────────────────────────────────────────────────────

REPO = "diplomatest/backend"
JIRA_PROJECT = "DEMO"

_COMMIT_MSGS = [
    "feat: add user authentication middleware",
    "fix: resolve race condition in session handler",
    "refactor: extract payment service into separate module",
    "feat: implement rate limiting for API endpoints",
    "fix: correct timezone handling in reports",
    "chore: update dependencies to latest versions",
    "feat: add caching layer for database queries",
    "fix: handle edge case in data validation",
    "refactor: simplify error handling in controllers",
    "feat: implement webhook for Slack notifications",
    "fix: memory leak in background job processor",
    "test: add integration tests for auth flow",
    "feat: add pagination to list endpoints",
    "fix: incorrect calculation in billing module",
    "refactor: move business logic out of controllers",
    "feat: implement soft delete for user records",
    "fix: SQL injection vulnerability in search",
    "chore: configure CI/CD pipeline for staging",
    "feat: add export to CSV functionality",
    "fix: broken links in email templates",
    "feat: implement two-factor authentication",
    "refactor: replace raw SQL with ORM queries",
    "fix: handle null values in report generator",
    "feat: add Redis session storage",
    "fix: correct date filtering in analytics",
]

_PR_TITLES = [
    "Add OAuth2 integration with Google",
    "Refactor notification system",
    "Fix critical bug in payment processing",
    "Implement real-time dashboard updates",
    "Migrate legacy API to REST v2",
    "Add comprehensive test coverage for auth module",
    "Performance optimization for search queries",
    "Implement role-based access control",
    "Add support for multi-currency payments",
    "Fix intermittent failures in background jobs",
    "Implement audit logging",
    "Add API rate limiting",
    "Refactor database connection pooling",
    "Fix session expiry handling",
    "Implement data export feature",
]

_REVIEW_BODIES = [
    "LGTM, nice clean implementation",
    "Looks good overall. One minor suggestion: consider extracting this into a helper function for reusability.",
    "This logic handles the happy path well. What happens when the external service is unavailable?",
    "Good refactor. The naming is much clearer now.",
    "Please add a unit test for the edge case where input is empty.",
    "I'd recommend adding error handling here — if the DB is down, the user will see a 500.",
    "Great work! The performance improvement is noticeable in the benchmarks.",
    "Minor: this could be simplified with a list comprehension.",
    "Approved. Make sure to squash before merge.",
    "Left a couple of comments inline, nothing blocking.",
]

_JIRA_SUMMARIES = [
    "Implement OAuth2 login flow",
    "Fix payment gateway timeout issues",
    "Add user activity audit log",
    "Migrate reports to new data model",
    "Performance testing for API endpoints",
    "Set up monitoring and alerting",
    "Refactor legacy authentication module",
    "Add support for webhook notifications",
    "Fix broken CSV export in analytics",
    "Implement data retention policy",
    "Upgrade database to latest version",
    "Add multi-language support",
    "Fix race condition in job scheduler",
    "Implement team permissions model",
    "Add API documentation with OpenAPI",
]

# ── Профили разработчиков ──────────────────────────────────────────────────────

DEMO_DEVS = [
    {
        "display_name": "Алексей Смирнов",
        "github_login": "demo_alexey_s",
        "jira_account_id": "demo_jira_alexey_001",
        "email": "alexey.smirnov@demo.internal",
        # Сильный разраб, высокий delivery, небольшой burnout из-за переработок
        "profile": {
            "commits_per_week": (8, 15),
            "prs_per_week": (2, 4),
            "issues_per_week": (3, 6),
            "story_points": (5, 13),
            "lines_per_commit": (30, 200),
            "after_hours_ratio": 0.35,
            "weekend_ratio": 0.18,
            "review_body_len": (80, 250),
            "rework_prob": 0.10,
            "trend": "stable_high",  # стабильно высокий
        },
    },
    {
        "display_name": "Мария Козлова",
        "github_login": "demo_maria_k",
        "jira_account_id": "demo_jira_maria_002",
        "email": "maria.kozlova@demo.internal",
        # Хороший mid, падение velocity на последних неделях (возможно выгорание)
        "profile": {
            "commits_per_week": (4, 9),
            "prs_per_week": (1, 3),
            "issues_per_week": (2, 4),
            "story_points": (3, 8),
            "lines_per_commit": (20, 120),
            "after_hours_ratio": 0.10,
            "weekend_ratio": 0.05,
            "review_body_len": (120, 350),
            "rework_prob": 0.05,
            "trend": "declining",  # снижение в последние 3 недели
        },
    },
    {
        "display_name": "Дмитрий Волков",
        "github_login": "demo_dmitry_v",
        "jira_account_id": "demo_jira_dmitry_003",
        "email": "dmitry.volkov@demo.internal",
        # Junior с ростом, много rework, но прогрессирует
        "profile": {
            "commits_per_week": (3, 7),
            "prs_per_week": (1, 2),
            "issues_per_week": (2, 3),
            "story_points": (2, 5),
            "lines_per_commit": (10, 80),
            "after_hours_ratio": 0.15,
            "weekend_ratio": 0.08,
            "review_body_len": (20, 100),
            "rework_prob": 0.30,
            "trend": "growing",  # рост от недели к недели
        },
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _rng(seed_str: str) -> random.Random:
    """Детерминированный rng по строковому сиду."""
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return random.Random(h)


def _monday(dt: datetime) -> datetime:
    return (dt - timedelta(days=dt.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
    )


def _work_ts(rng: random.Random, day: date, after_hours_ratio: float, weekend_ratio: float) -> datetime | None:
    """Возвращает timestamp активности для дня, или None (нет активности)."""
    weekday = day.weekday()
    if weekday >= 5:  # выходной
        if rng.random() > weekend_ratio:
            return None
        hour = rng.randint(10, 16)
    else:
        if rng.random() < after_hours_ratio:
            hour = rng.choice([7, 8, 20, 21, 22])
        else:
            hour = rng.randint(9, 18)
    minute = rng.randint(0, 59)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)


def _week_multiplier(week_idx: int, total: int, trend: str) -> float:
    """Множитель активности в зависимости от тренда."""
    progress = week_idx / max(total - 1, 1)
    if trend == "stable_high":
        return 1.0 + 0.05 * (0.5 - abs(progress - 0.5))
    if trend == "declining":
        if progress < 0.6:
            return 1.0
        return max(0.45, 1.0 - (progress - 0.6) * 2.0)
    if trend == "growing":
        return 0.5 + progress * 0.8
    return 1.0


# ── Основная функция ───────────────────────────────────────────────────────────

async def _seed_developer(db: AsyncSession, dev_cfg: dict, team_id: int, week_starts: list[datetime]):
    rng = _rng(dev_cfg["github_login"])
    profile = dev_cfg["profile"]
    trend = profile["trend"]
    total_weeks = len(week_starts)

    # Создаём разработчика
    dev = Developer(
        display_name    = dev_cfg["display_name"],
        github_login    = dev_cfg["github_login"],
        jira_account_id = dev_cfg["jira_account_id"],
        email           = dev_cfg["email"],
        team_id         = team_id,
    )
    db.add(dev)
    await db.flush()

    # Используем хэш логина как базу счётчиков — гарантирует уникальность между разработчиками
    _base = abs(hash(dev_cfg["github_login"])) % 90_000
    pr_counter = 10_000 + _base
    commit_counter = 100_000 + _base * 10
    jira_counter = 1_000 + _base
    gh_id_base = 50_000_000 + _base * 100
    dev_prefix = dev_cfg["github_login"].replace("demo_", "")

    for w_idx, week in enumerate(week_starts):
        mult = _week_multiplier(w_idx, total_weeks, trend)
        week_end = week + timedelta(days=7)

        # ── Коммиты ────────────────────────────────────────────────────────────
        n_commits = max(0, int(rng.randint(*profile["commits_per_week"]) * mult))
        week_commits = []
        for _ in range(n_commits):
            day_offset = rng.randint(0, 6)
            ts = _work_ts(rng, (week + timedelta(days=day_offset)).date(),
                          profile["after_hours_ratio"], profile["weekend_ratio"])
            if ts is None:
                ts = week + timedelta(days=day_offset, hours=10)
            additions = int(rng.randint(*profile["lines_per_commit"]) * mult)
            deletions = int(additions * rng.uniform(0.2, 0.7))
            msg = rng.choice(_COMMIT_MSGS)
            sha = hashlib.sha1(f"{dev_cfg['github_login']}-{commit_counter}".encode()).hexdigest()
            c = GitHubCommit(
                sha=sha, repo_full_name=REPO,
                author_login=dev_cfg["github_login"],
                author_email=dev_cfg["email"],
                message=msg,
                html_url=f"https://github.com/{REPO}/commit/{sha}",
                committed_at=ts,
                additions=additions, deletions=deletions,
            )
            db.add(c)
            week_commits.append((ts, additions, deletions, msg))
            commit_counter += 1

        # ── Pull Requests ───────────────────────────────────────────────────────
        n_prs = max(0, int(rng.randint(*profile["prs_per_week"]) * mult))
        week_prs = []
        for _ in range(n_prs):
            pr_counter += 1
            gh_id_base += rng.randint(1, 50)
            day_offset = rng.randint(0, 5)
            created = week + timedelta(days=day_offset, hours=rng.randint(9, 17))
            additions = int(rng.randint(20, 400) * mult)
            deletions = int(additions * rng.uniform(0.1, 0.5))
            changed_files = rng.randint(1, min(20, additions // 15 + 1))
            review_comments = rng.randint(0, 6)
            title = rng.choice(_PR_TITLES)
            is_merged = rng.random() < 0.80
            merged_at = created + timedelta(hours=rng.randint(2, 48)) if is_merged else None
            is_rework = rng.random() < profile["rework_prob"]

            pr = GitHubPullRequest(
                gh_id=gh_id_base, repo_full_name=REPO, number=pr_counter,
                title=title,
                state="merged" if is_merged else "open",
                author_login=dev_cfg["github_login"],
                html_url=f"https://github.com/{REPO}/pull/{pr_counter}",
                created_at=created, merged_at=merged_at,
                additions=additions, deletions=deletions,
                changed_files=changed_files, review_comments=review_comments,
                commits_count=rng.randint(1, 5),
            )
            db.add(pr)
            await db.flush()
            week_prs.append(pr)

            # Ревью на этот PR
            reviewer = rng.choice(["team_reviewer_1", "team_reviewer_2", "team_lead"])
            review_ts = created + timedelta(hours=rng.randint(1, 24))
            review_state = "CHANGES_REQUESTED" if is_rework else (
                "APPROVED" if rng.random() < 0.75 else "COMMENTED"
            )
            body_len = rng.randint(*profile["review_body_len"])
            review_body = rng.choice(_REVIEW_BODIES)
            if len(review_body) < body_len:
                review_body += " " + " ".join(rng.choices(_REVIEW_BODIES, k=2))
            db.add(GitHubReview(
                gh_id=gh_id_base + 1000, pr_id=pr.id,
                reviewer_login=reviewer, state=review_state,
                html_url=f"https://github.com/{REPO}/pull/{pr_counter}#pullrequestreview-{gh_id_base}",
                submitted_at=review_ts, body=review_body[:body_len],
            ))

            # GigaChat оценка PR (реалистичные, is_stub=0)
            q_base = 85 if not is_rework else 55
            q_score = round(max(20, min(100, q_base + rng.uniform(-12, 12))), 1)
            c_raw = additions / 50 * 25 + changed_files * 3
            c_score = round(min(100, c_raw + rng.uniform(-10, 10)), 1)
            q_label = "высокое" if q_score >= 75 else ("среднее" if q_score >= 45 else "низкое")
            c_label = "высокая" if c_score >= 70 else ("средняя" if c_score >= 35 else "низкая")
            q_reasons = ["Хорошее описание изменений", "Наличие тестов"] if q_score >= 75 else \
                        ["Недостаточное описание", "Рекомендуется добавить тесты"]
            c_reasons = [f"Изменено {changed_files} файлов", f"+{additions} строк кода"]
            db.add(PRGigaChatAssessment(
                pr_id=pr.id,
                quality_score=q_score, complexity_score=c_score,
                quality_label=q_label, complexity_label=c_label,
                quality_reasons=q_reasons, complexity_reasons=c_reasons,
                is_stub=0,
            ))

        # ── Jira Issues ─────────────────────────────────────────────────────────
        n_issues = max(0, int(rng.randint(*profile["issues_per_week"]) * mult))
        week_story_points = 0.0
        for _ in range(n_issues):
            jira_counter += 1
            sp = rng.choice([1, 2, 3, 5, 8]) if rng.random() < 0.7 else None
            if sp:
                week_story_points += sp
            created_j = week + timedelta(days=rng.randint(0, 4), hours=rng.randint(9, 12))
            resolved_j = created_j + timedelta(hours=rng.randint(4, int(96 / max(mult, 0.3))))
            if resolved_j >= week_end:
                resolved_j = week_end - timedelta(hours=1)
            key = f"{JIRA_PROJECT}-{dev_prefix}-{jira_counter}"
            db.add(JiraIssue(
                jira_id=f"demo_{dev_prefix}_{jira_counter}",
                key=key, project_key=JIRA_PROJECT,
                issue_type=rng.choice(["Story", "Bug", "Task"]),
                summary=rng.choice(_JIRA_SUMMARIES),
                status="Done",
                assignee_account_id=dev_cfg["jira_account_id"],
                priority=rng.choice(["High", "Medium", "Low"]),
                story_points=sp,
                html_url=f"https://jira.demo.internal/browse/{JIRA_PROJECT}-{jira_counter}",
                created_at=created_j, resolved_at=resolved_j,
                reopen_count=1 if rng.random() < 0.08 else 0,
            ))

        # ── DailyMetric за каждый день недели ──────────────────────────────────
        for day_offset in range(7):
            day = (week + timedelta(days=day_offset)).date()
            day_dt = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)

            day_commits  = sum(1 for (ts, *_) in week_commits if ts.date() == day)
            day_adds     = sum(a for (ts, a, _, _) in week_commits if ts.date() == day)
            day_dels     = sum(d for (ts, _, d, _) in week_commits if ts.date() == day)
            day_prs_open = sum(1 for pr in week_prs if pr.created_at.date() == day)
            day_prs_merg = sum(1 for pr in week_prs if pr.merged_at and pr.merged_at.date() == day)

            if day_commits == 0 and day_prs_open == 0:
                continue

            churn = round(rng.uniform(0.9, 1.8) * (1 + 0.3 * (1 - mult)), 2)
            cycle_h = round(rng.uniform(6, 48) / max(mult, 0.3), 1)

            db.add(DailyMetric(
                developer_id=dev.id, date=day_dt,
                commits_count=day_commits,
                prs_opened=day_prs_open, prs_merged=day_prs_merg,
                reviews_given=rng.randint(0, 2),
                issues_resolved=rng.randint(0, 2),
                story_points_delivered=round(week_story_points / max(n_issues, 1), 1),
                lines_added=day_adds, lines_removed=day_dels,
                code_churn=churn,
                avg_issue_cycle_time_hours=cycle_h,
                review_comments_given=rng.randint(0, 4),
                review_comments_received=rng.randint(0, 3),
            ))

        # ── ActivityEvents за неделю ────────────────────────────────────────────
        for ts, additions, deletions, msg in week_commits:
            sha_short = hashlib.sha1(f"{ts}-{msg}".encode()).hexdigest()[:7]
            db.add(ActivityEvent(
                developer_id=dev.id, activity_type=ActivityType.COMMIT,
                occurred_at=ts, lines_added=additions, lines_removed=deletions,
                source_type="github_commit",
                source_url=f"https://github.com/{REPO}/commit/{sha_short}",
                repo=REPO, title=msg[:120],
                description=f"+{additions}/{deletions} строк",
            ))
        for pr in week_prs:
            db.add(ActivityEvent(
                developer_id=dev.id, activity_type=ActivityType.PR_OPENED,
                occurred_at=pr.created_at,
                lines_added=pr.additions, lines_removed=pr.deletions,
                source_type="github_pr",
                source_url=pr.html_url, repo=REPO,
                title=f"PR #{pr.number}: {pr.title}",
            ))
            if pr.merged_at:
                db.add(ActivityEvent(
                    developer_id=dev.id, activity_type=ActivityType.PR_MERGED,
                    occurred_at=pr.merged_at,
                    source_type="github_pr", source_url=pr.html_url,
                    repo=REPO, title=f"PR #{pr.number} влит",
                ))

        # ── PerformanceScore за неделю ──────────────────────────────────────────
        gc_quality = None
        if week_prs:
            gc_scores = [
                q_score  # значение из последнего PR в цикле — используем среднее
            ]
            gc_quality = round(sum(
                (85 if rng.random() > profile["rework_prob"] else 55) + rng.uniform(-10, 10)
                for _ in week_prs
            ) / len(week_prs), 1)

        delivery  = round(max(10, min(100, 50 + 25 * mult + rng.uniform(-8, 8))), 1)
        code_h    = round(max(10, min(100, 90 - profile["rework_prob"] * 150 + rng.uniform(-5, 5))), 1)
        quality   = round(code_h * 0.5 + (gc_quality or code_h) * 0.5, 1) if gc_quality else code_h
        collab    = round(max(10, min(100, 55 + 15 * mult + rng.uniform(-10, 10))), 1)
        consist   = round(max(10, min(100, 60 + 10 * mult + rng.uniform(-10, 10))), 1)
        overall   = round(delivery * 0.3 + quality * 0.25 + collab * 0.25 + consist * 0.2, 1)

        burnout_score = round(min(1.0, profile["after_hours_ratio"] * 0.6 +
                                  profile["weekend_ratio"] * 0.4 +
                                  (0.3 if mult < 0.6 else 0.0) +
                                  rng.uniform(0, 0.1)), 3)
        burnout_level = "high" if burnout_score > 0.6 else ("medium" if burnout_score > 0.35 else "low")

        db.add(PerformanceScore(
            developer_id=dev.id, week_start=week,
            delivery_score=delivery, quality_score=quality,
            collaboration_score=collab, consistency_score=consist,
            velocity_trend=round((mult - 1.0) * 0.5, 3),
            overall_score=overall,
            avg_daily_active_hours=round(rng.uniform(6, 10) * mult, 1),
            weekend_activity_ratio=round(profile["weekend_ratio"] + rng.uniform(-0.03, 0.03), 3),
            after_hours_ratio=round(profile["after_hours_ratio"] + rng.uniform(-0.05, 0.05), 3),
            burnout_risk_score=burnout_score,
            burnout_risk_level=burnout_level,
        ))

    await db.flush()
    return dev


# ── Endpoint ───────────────────────────────────────────────────────────────────

@seed_router.post("/seed/demo", summary="Создать синтетических разработчиков для демо")
async def seed_demo(db: AsyncSession = Depends(get_db)):
    logins = [d["github_login"] for d in DEMO_DEVS]

    # Удаляем старые данные demo-разработчиков
    existing = (await db.execute(
        select(Developer).where(Developer.github_login.in_(logins))
    )).scalars().all()

    for dev in existing:
        await db.execute(delete(PerformanceScore).where(PerformanceScore.developer_id == dev.id))
        await db.execute(delete(DailyMetric).where(DailyMetric.developer_id == dev.id))
        await db.execute(delete(ActivityEvent).where(ActivityEvent.developer_id == dev.id))
        prs = (await db.execute(
            select(GitHubPullRequest).where(GitHubPullRequest.author_login == dev.github_login)
        )).scalars().all()
        for pr in prs:
            await db.execute(delete(PRGigaChatAssessment).where(PRGigaChatAssessment.pr_id == pr.id))
        await db.execute(delete(GitHubPullRequest).where(
            GitHubPullRequest.author_login == dev.github_login))
        await db.execute(delete(GitHubCommit).where(
            GitHubCommit.author_login == dev.github_login))
        await db.execute(delete(JiraIssue).where(
            JiraIssue.assignee_account_id == dev.jira_account_id))
        await db.execute(delete(Developer).where(Developer.id == dev.id))
    await db.flush()

    # Берём первую команду
    team = (await db.execute(select(Team).limit(1))).scalar_one_or_none()
    if not team:
        return {"error": "Сначала создайте хотя бы одну команду"}

    # 12 недель назад до текущей
    now = datetime.now(tz=timezone.utc)
    current_monday = now - timedelta(days=now.weekday())
    current_monday = current_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    week_starts = [current_monday - timedelta(weeks=w) for w in range(11, -1, -1)]

    created = []
    for dev_cfg in DEMO_DEVS:
        dev = await _seed_developer(db, dev_cfg, team.id, week_starts)
        created.append({"id": dev.id, "name": dev.display_name})

    await db.commit()
    return {
        "created": created,
        "weeks": len(week_starts),
        "message": f"Создано {len(created)} разработчика с данными за {len(week_starts)} недель",
    }
