"""
Seed data v4 — совместим с новыми моделями:
  - JiraIssue без html_url
  - PerformanceScore с 7 новыми метриками (momentum, responsiveness, etc.)
  - GradeHistory — история грейдов
  - VacationPeriod — отпуска
  - Developer.grade — текущий грейд
"""
import random
from datetime import datetime, timedelta, timezone

import numpy as np

from app.db.models import (
    Department, Team, Developer, Grade,
    GitHubCommit, GitHubPullRequest, GitHubReview,
    JiraIssue, JiraTransition,
    DailyMetric, PerformanceScore,
    GradeHistory, VacationPeriod,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Фикстуры ─────────────────────────────────────────────────────────────────

_DEPARTMENTS = [
    {"id": 1, "name": "Разработка",  "description": "Продуктовая разработка",     "head_name": "Михаил Иванов"},
    {"id": 2, "name": "Платформа",   "description": "Платформа и инфраструктура", "head_name": "Анна Петрова"},
]

_TEAMS = [
    {"id": 1, "name": "Core Platform", "jira_project_key": "CORE", "github_org": "company-org", "department_id": 2},
    {"id": 2, "name": "Product Web",   "jira_project_key": "WEB",  "github_org": "company-org", "department_id": 1},
]

_DEVELOPERS = [
    {"id": 1, "display_name": "Alice Chen",    "github_login": "alice_dev",   "jira_account_id": "alice-jira-id",   "email": "alice@company.io",   "team_id": 1, "grade": Grade.SENIOR},
    {"id": 2, "display_name": "Bob Müller",    "github_login": "bob_codes",   "jira_account_id": "bob-jira-id",     "email": "bob@company.io",     "team_id": 1, "grade": Grade.MIDDLE},
    {"id": 3, "display_name": "Charlie Singh", "github_login": "charlie_eng", "jira_account_id": "charlie-jira-id", "email": "charlie@company.io", "team_id": 1, "grade": Grade.SENIOR},
    {"id": 4, "display_name": "Diana Torres",  "github_login": "diana_hacks", "jira_account_id": "diana-jira-id",   "email": "diana@company.io",   "team_id": 2, "grade": Grade.MIDDLE},
    {"id": 5, "display_name": "Evan Park",     "github_login": "evan_build",  "jira_account_id": "evan-jira-id",    "email": "evan@company.io",    "team_id": 2, "grade": Grade.JUNIOR},
]

# Профили: определяют характер генерируемых данных
# attrition=True → метрики будут падать → сработают attrition alerts
_PROFILES = {
    1: {"base_sp": 6,  "base_prs": 3, "burnout": False, "trend": "improving",  "attrition": False},
    2: {"base_sp": 4,  "base_prs": 2, "burnout": False, "trend": "stable",     "attrition": False},
    3: {"base_sp": 8,  "base_prs": 5, "burnout": True,  "trend": "declining",  "attrition": True},
    4: {"base_sp": 3,  "base_prs": 2, "burnout": False, "trend": "improving",  "attrition": False},
    5: {"base_sp": 2,  "base_prs": 1, "burnout": False, "trend": "stable",     "attrition": False},
}

_REPOS = {
    1: ["company-org/core-api",  "company-org/infra-tools"],
    2: ["company-org/core-api",  "company-org/data-pipeline"],
    3: ["company-org/core-api",  "company-org/infra-tools", "company-org/data-pipeline"],
    4: ["company-org/web-app",   "company-org/design-system"],
    5: ["company-org/web-app",   "company-org/landing"],
}
_JIRA_PROJ = {1: "CORE", 2: "CORE", 3: "CORE", 4: "WEB", 5: "WEB"}

_COMMIT_MSGS = [
    "fix: resolve NPE in auth middleware",
    "feat: add pagination to user list endpoint",
    "refactor: extract service layer from controller",
    "chore: update dependencies",
    "fix: correct date parsing in scheduler",
    "feat: implement caching layer for API responses",
    "test: add unit tests for payment processor",
    "docs: update README with setup instructions",
    "fix: handle edge case in CSV export",
    "feat: add rate limiting to public endpoints",
    "refactor: simplify database connection pool logic",
    "fix: resolve memory leak in websocket handler",
    "perf: optimize slow SQL queries in dashboard",
    "fix: sanitize user input in search endpoint",
    "feat: integrate Sentry error tracking",
    "refactor: migrate to async/await pattern",
]

_PR_TITLES = [
    "Add user authentication flow",
    "Implement dashboard analytics widget",
    "Fix memory leak in background jobs",
    "Refactor API response serialization",
    "Add CSV export feature",
    "Optimize database query performance",
    "Integrate third-party payment gateway",
    "Update dependency versions",
    "Add comprehensive test coverage",
    "Implement real-time notifications",
    "Fix timezone bug in scheduler",
    "Add rate limiting middleware",
    "Implement caching layer",
    "Refactor legacy authentication code",
]

_REVIEW_BODIES = [
    "LGTM! Great work on the error handling.",
    "Could you add a test for the edge case where the user is null?",
    "This looks good, but I'd suggest extracting this into a separate method.",
    "Nice improvement! The new approach is much cleaner.",
    "I think we need to handle the case where the API returns 429. Otherwise approved.",
    "Approved, but please fix the typo in the comment.",
    None,
    "The logic looks correct. One minor: consider using a named constant.",
    "Good catch on the NPE! Approved.",
    "This might have a performance issue at scale — can we add a benchmark?",
]

_JIRA_SUMMARIES = {
    "Story": [
        "As a user I want to export reports to PDF",
        "Implement SSO login integration",
        "Add multi-language support to dashboard",
        "Create API for mobile application",
        "Build notification system for alerts",
    ],
    "Task": [
        "Update CI/CD pipeline configuration",
        "Migrate database to PostgreSQL 16",
        "Review and update API documentation",
        "Set up monitoring dashboards in Grafana",
        "Configure auto-scaling for production",
    ],
    "Bug": [
        "Login fails when email contains plus sign",
        "Dashboard chart shows incorrect data on weekends",
        "Export button not visible on mobile screens",
        "Slow query causing timeout on report page",
        "Date picker resets when switching tabs",
    ],
    "Sub-task": [
        "Write unit tests for auth module",
        "Add input validation to registration form",
        "Update Swagger documentation",
        "Code review for feature branch",
        "Deploy hotfix to staging environment",
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(base_dt: datetime, h_min: int = 9, h_max: int = 18) -> datetime:
    return base_dt.replace(
        hour=random.randint(h_min, h_max - 1),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
        tzinfo=timezone.utc,
    )

def _gh_commit_url(repo, sha):    return f"https://github.com/{repo}/commit/{sha}"
def _gh_pr_url(repo, num):        return f"https://github.com/{repo}/pull/{num}"
def _gh_review_url(repo, num, r): return f"https://github.com/{repo}/pull/{num}#pullrequestreview-{r}"


# ── Main seed ─────────────────────────────────────────────────────────────────

async def run_seed(db: AsyncSession, num_weeks: int = 12):
    # ── Departments / Teams / Developers ─────────────────────────────────────
    for d in _DEPARTMENTS:
        if not await db.get(Department, d["id"]):
            db.add(Department(**d))
    await db.flush()

    for t in _TEAMS:
        if not await db.get(Team, t["id"]):
            db.add(Team(**t))
    await db.flush()

    for dev_data in _DEVELOPERS:
        existing = await db.get(Developer, dev_data["id"])
        if not existing:
            db.add(Developer(**dev_data))
        else:
            # Обновляем грейд если изменился
            existing.grade = dev_data["grade"]
    await db.flush()

    dev_ids   = [d["id"]              for d in _DEVELOPERS]
    gh_logins = [d["github_login"]    for d in _DEVELOPERS]
    jira_ids  = [d["jira_account_id"] for d in _DEVELOPERS]

    # ── Очистка старых данных (порядок важен из-за FK) ────────────────────────
    old_issue_ids = (await db.execute(
        select(JiraIssue.id).where(JiraIssue.assignee_account_id.in_(jira_ids))
    )).scalars().all()
    if old_issue_ids:
        await db.execute(delete(JiraTransition).where(JiraTransition.issue_id.in_(old_issue_ids)))
    await db.execute(delete(JiraIssue).where(JiraIssue.assignee_account_id.in_(jira_ids)))

    old_pr_ids = (await db.execute(
        select(GitHubPullRequest.id).where(GitHubPullRequest.author_login.in_(gh_logins))
    )).scalars().all()
    if old_pr_ids:
        await db.execute(delete(GitHubReview).where(GitHubReview.pr_id.in_(old_pr_ids)))
    await db.execute(delete(GitHubReview).where(GitHubReview.reviewer_login.in_(gh_logins)))
    await db.execute(delete(GitHubPullRequest).where(GitHubPullRequest.author_login.in_(gh_logins)))
    await db.execute(delete(GitHubCommit).where(GitHubCommit.author_login.in_(gh_logins)))
    await db.execute(delete(DailyMetric).where(DailyMetric.developer_id.in_(dev_ids)))
    await db.execute(delete(PerformanceScore).where(PerformanceScore.developer_id.in_(dev_ids)))
    await db.execute(delete(GradeHistory).where(GradeHistory.developer_id.in_(dev_ids)))
    await db.execute(delete(VacationPeriod).where(VacationPeriod.developer_id.in_(dev_ids)))
    await db.flush()

    # ── Глобальные счётчики PK ────────────────────────────────────────────────
    ctr = {"commit": 1, "pr": 1, "review": 1, "jira": 1, "trans": 1}

    # ── Grade History ─────────────────────────────────────────────────────────
    grade_histories = [
        # Alice: middle → senior (повышение 6 недель назад)
        {"developer_id": 1, "grade": Grade.MIDDLE, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=20), "changed_by": "Михаил Иванов", "note": "Начальный грейд"},
        {"developer_id": 1, "grade": Grade.SENIOR, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=6),  "changed_by": "Михаил Иванов", "note": "Стабильный рост, взял на себя архитектурные задачи"},
        # Bob: junior → middle (3 месяца назад)
        {"developer_id": 2, "grade": Grade.JUNIOR, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=30), "changed_by": "Михаил Иванов", "note": "Начальный грейд"},
        {"developer_id": 2, "grade": Grade.MIDDLE, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=12), "changed_by": "Михаил Иванов", "note": "Хорошо справляется с самостоятельными задачами"},
        # Charlie: middle → senior (давно)
        {"developer_id": 3, "grade": Grade.MIDDLE, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=40), "changed_by": "Анна Петрова",  "note": "Начальный грейд"},
        {"developer_id": 3, "grade": Grade.SENIOR, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=16), "changed_by": "Анна Петрова",  "note": "Технический лидер нескольких фич"},
        # Diana: junior → middle (недавно)
        {"developer_id": 4, "grade": Grade.JUNIOR, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=24), "changed_by": "Михаил Иванов", "note": "Начальный грейд"},
        {"developer_id": 4, "grade": Grade.MIDDLE, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=4),  "changed_by": "Михаил Иванов", "note": "Отличный прогресс"},
        # Evan: только junior
        {"developer_id": 5, "grade": Grade.JUNIOR, "changed_at": datetime.now(tz=timezone.utc) - timedelta(weeks=16), "changed_by": "Михаил Иванов", "note": "Начальный грейд"},
    ]
    for gh in grade_histories:
        db.add(GradeHistory(**gh))
    await db.flush()

    # ── Vacation Periods ──────────────────────────────────────────────────────
    now = datetime.now(tz=timezone.utc)
    vacations = [
        # Alice: отпуск 2 месяца назад
        {"developer_id": 1, "started_at": now - timedelta(weeks=9), "ended_at": now - timedelta(weeks=7), "source": "manual", "note": "Плановый отпуск"},
        # Bob: отпуск 4 месяца назад
        {"developer_id": 2, "started_at": now - timedelta(weeks=18), "ended_at": now - timedelta(weeks=16), "source": "manual", "note": "Отпуск"},
        # Charlie: очень давно — сигнал для recovery score
        {"developer_id": 3, "started_at": now - timedelta(weeks=32), "ended_at": now - timedelta(weeks=30), "source": "manual", "note": "Последний отпуск"},
        # Diana: недавно вернулась
        {"developer_id": 4, "started_at": now - timedelta(weeks=3), "ended_at": now - timedelta(weeks=1), "source": "manual", "note": "Отпуск"},
    ]
    for v in vacations:
        db.add(VacationPeriod(**v))
    await db.flush()

    # ── Основной цикл: GitHub + Jira + DailyMetric + PerformanceScore ─────────
    daily_metrics      = []
    performance_scores = []

    for dev_data in _DEVELOPERS:
        dev_id  = dev_data["id"]
        login   = dev_data["github_login"]
        jira_id = dev_data["jira_account_id"]
        profile = _PROFILES[dev_id]
        repos   = _REPOS[dev_id]
        proj    = _JIRA_PROJ[dev_id]
        trend_k = {"improving": 1.04, "stable": 1.0, "declining": 0.96}[profile["trend"]]

        created_prs = []  # (pr_id, pr_number, repo) — для привязки ревью

        for week_offset in range(num_weeks, 0, -1):
            week_mult  = trend_k ** (num_weeks - week_offset)
            # Для attrition-профиля дополнительно роняем последние 4 недели
            if profile["attrition"] and week_offset <= 4:
                attrition_mult = 0.6 - (4 - week_offset) * 0.08
                week_mult *= attrition_mult

            week_start = (
                datetime.now(tz=timezone.utc) - timedelta(weeks=week_offset)
            ).replace(hour=0, minute=0, second=0, microsecond=0)

            week_daily      = []
            week_added      = 0
            week_removed    = 0
            week_commits_n  = 0
            week_prs_merged = 0
            week_reviews_n  = 0
            week_jira_n     = 0

            for day_off in range(7):
                day_dt     = week_start + timedelta(days=day_off)
                is_weekend = day_dt.weekday() >= 5

                if is_weekend:
                    if profile["burnout"] and random.random() < 0.3:
                        n_commits   = random.randint(0, 2)
                        n_prs       = random.randint(0, 1)
                        sp_day      = random.uniform(0, 2) * week_mult
                        n_reviews   = random.randint(0, 1)
                        n_jira_done = 0
                    else:
                        n_commits = n_prs = n_reviews = n_jira_done = 0
                        sp_day    = 0.0
                else:
                    n_commits   = random.randint(0, 5)
                    n_prs       = max(0, int(np.random.normal(profile["base_prs"] / 5, 0.5)))
                    sp_day      = max(0.0, np.random.normal(profile["base_sp"] / 5, 1.0) * week_mult)
                    n_reviews   = random.randint(0, 3)
                    n_jira_done = random.randint(0, 2)

                    # Attrition: снижаем engagement (меньше ревью, короче комменты)
                    if profile["attrition"] and week_offset <= 4:
                        n_reviews   = max(0, n_reviews - 2)
                        n_jira_done = max(0, n_jira_done - 1)

                day_added   = 0
                day_removed = 0
                day_merged  = 0

                # ── Commits ──────────────────────────────────────────────────
                for _ in range(n_commits):
                    cid  = ctr["commit"]; ctr["commit"] += 1
                    sha  = f"{cid:040x}"
                    repo = random.choice(repos)
                    add  = random.randint(5, 300)
                    rem  = random.randint(0, max(1, add // 3))
                    day_added   += add
                    day_removed += rem
                    db.add(GitHubCommit(
                        id=cid, sha=sha, repo_full_name=repo,
                        author_login=login,
                        author_email=dev_data["email"],
                        message=random.choice(_COMMIT_MSGS),
                        html_url=_gh_commit_url(repo, sha),
                        committed_at=_ts(day_dt),
                        additions=add, deletions=rem,
                        jira_issue_key=(
                            f"{proj}-{random.randint(1, 99)}"
                            if random.random() > 0.4 else None
                        ),
                    ))

                # ── Pull Requests ─────────────────────────────────────────────
                for _ in range(n_prs):
                    pid    = ctr["pr"]; ctr["pr"] += 1
                    repo   = random.choice(repos)
                    add    = random.randint(20, 600)
                    rem    = random.randint(0, max(1, add // 3))
                    opened = _ts(day_dt)
                    merged = None
                    if random.random() < 0.65:
                        delay  = timedelta(hours=random.randint(1, 48))
                        merged = opened + delay
                        if merged > datetime.now(tz=timezone.utc):
                            merged = None
                    if merged:
                        day_merged += 1
                    db.add(GitHubPullRequest(
                        id=pid, gh_id=pid * 1000,
                        repo_full_name=repo, number=pid,
                        title=random.choice(_PR_TITLES),
                        state="merged" if merged else "open",
                        author_login=login,
                        html_url=_gh_pr_url(repo, pid),
                        created_at=opened,
                        merged_at=merged,
                        closed_at=merged,
                        additions=add, deletions=rem,
                        changed_files=random.randint(1, 20),
                        review_comments=random.randint(0, 10),
                        jira_issue_key=(
                            f"{proj}-{random.randint(1, 99)}"
                            if random.random() > 0.3 else None
                        ),
                    ))
                    created_prs.append((pid, pid, repo))

                # ── Reviews ───────────────────────────────────────────────────
                if n_reviews > 0 and created_prs:
                    for _ in range(n_reviews):
                        pr_id_ref, pr_num_ref, repo_ref = random.choice(created_prs)
                        rid   = ctr["review"]; ctr["review"] += 1
                        state = random.choice(["APPROVED", "APPROVED", "CHANGES_REQUESTED", "COMMENTED"])
                        db.add(GitHubReview(
                            id=rid, gh_id=rid * 100,
                            pr_id=pr_id_ref,
                            reviewer_login=login,
                            state=state,
                            html_url=_gh_review_url(repo_ref, pr_num_ref, rid),
                            submitted_at=_ts(day_dt),
                            body=random.choice(_REVIEW_BODIES),
                        ))

                # ── Jira issues ───────────────────────────────────────────────
                for _ in range(n_jira_done):
                    iid      = ctr["jira"]; ctr["jira"] += 1
                    ikey     = f"{proj}-{iid}"
                    itype    = random.choice(list(_JIRA_SUMMARIES))
                    summary  = random.choice(_JIRA_SUMMARIES[itype])
                    sp_pts   = random.choice([1, 2, 3, 5, 8, None])
                    resolved = _ts(day_dt)
                    created  = resolved - timedelta(hours=random.randint(24, 240))
                    db.add(JiraIssue(
                        id=iid, jira_id=str(iid), key=ikey,
                        project_key=proj,
                        issue_type=itype,
                        summary=summary,
                        status="Done",
                        assignee_account_id=jira_id,
                        priority=random.choice(["High", "Medium", "Low", "Critical"]),
                        story_points=sp_pts,
                        created_at=created,
                        updated_at=resolved,
                        resolved_at=resolved,
                        # reopen_count=0,
                    ))
                    await db.flush()

                    # Переходы: To Do → In Progress → In Review → Done
                    t1_at = created  + timedelta(hours=random.randint(1, 12))
                    t2_at = t1_at    + timedelta(hours=random.randint(4, 48))
                    if t2_at > resolved: t2_at = resolved - timedelta(minutes=10)

                    for t_from, t_to, t_at in [
                        ("To Do",       "In Progress", t1_at),
                        ("In Progress", "In Review",   t2_at),
                        ("In Review",   "Done",        resolved),
                    ]:
                        tid = ctr["trans"]; ctr["trans"] += 1
                        db.add(JiraTransition(
                            id=tid, issue_id=iid,
                            from_status=t_from, to_status=t_to,
                            author_account_id=jira_id,
                            transitioned_at=t_at,
                        ))

                week_added      += day_added
                week_removed    += day_removed
                week_commits_n  += n_commits
                week_prs_merged += day_merged
                week_reviews_n  += n_reviews
                week_jira_n     += n_jira_done

                week_daily.append({
                    "developer_id":              dev_id,
                    "date":                      day_dt,
                    "commits_count":             n_commits,
                    "prs_opened":                n_prs,
                    "prs_merged":                day_merged,
                    "reviews_given":             n_reviews,
                    "issues_resolved":           n_jira_done,
                    "story_points_delivered":    round(sp_day, 1),
                    "lines_added":               day_added,
                    "lines_removed":             day_removed,
                    "code_churn":                round(random.uniform(1.0, 2.5), 2),
                    "pr_review_coverage":        round(random.uniform(0.5, 1.0), 2),
                    "reopen_rate":               round(random.uniform(0.0, 0.2), 2),
                    "avg_pr_review_time_hours":  round(random.uniform(2, 48), 1),
                    "avg_issue_cycle_time_hours":round(random.uniform(4, 72), 1),
                    "review_comments_given":     random.randint(0, 8),
                    "review_comments_received":  random.randint(0, 5),
                })

            await db.flush()
            daily_metrics.extend(week_daily)

            # ── PerformanceScore с новыми 7 метриками ─────────────────────────
            sp_wk      = sum(dm["story_points_delivered"] for dm in week_daily)
            prm_wk     = sum(dm["prs_merged"]             for dm in week_daily)
            rev_wk     = sum(dm["reviews_given"]          for dm in week_daily)
            act_days   = sum(1 for dm in week_daily if dm["commits_count"] + dm["prs_opened"] > 0)

            # Личный baseline (упрощённый для seed)
            base_throughput = profile["base_sp"] * 0.6 + profile["base_prs"] * 0.4
            curr_throughput = sp_wk * 0.6 + prm_wk * 0.4
            momentum = round(
                float(np.clip((curr_throughput - base_throughput) / max(base_throughput, 1), -1.0, 1.0)),
                3,
            )

            # Responsiveness: быстрее для хороших профилей
            avg_rt = random.uniform(4, 12) if not profile["attrition"] or week_offset > 4 else random.uniform(24, 60)
            resp_score = round(max(0.0, 100.0 - (avg_rt - 2) * (100 / 46)), 2)

            # Task velocity
            avg_ct = random.uniform(8, 40) if not profile["attrition"] or week_offset > 4 else random.uniform(50, 90)
            tv_score = round(max(0.0, 100.0 - (avg_ct - 8) * (100 / 88)), 2)

            # Engagement depth
            # Attrition профиль: engagement падает в последние недели
            if profile["attrition"] and week_offset <= 4:
                eng_score = round(random.uniform(15, 35), 2)
                avg_comment = round(random.uniform(20, 60), 1)
            else:
                eng_score = round(random.uniform(55, 85) * week_mult, 2)
                avg_comment = round(random.uniform(80, 250), 1)

            # Code health
            avg_churn = random.uniform(1.1, 2.0)
            rework    = random.uniform(0.0, 0.2)
            ch_score  = round(max(0.0, 100.0 - (avg_churn - 1.0) * (100 / 1.5)) * 0.4 + (1 - rework) * 100 * 0.6, 2)

            # Rhythm
            if profile["burnout"]:
                variance    = round(random.uniform(3, 6), 2)
                rhythm_score = round(max(0.0, 100.0 - (variance / 4.0) * 100), 2)
            else:
                variance    = round(random.uniform(0.5, 2.5), 2)
                rhythm_score = round(max(0.0, 100.0 - (variance / 4.0) * 100), 2)

            # Recovery: смотрим на отпуска из seed данных
            dev_vacs = [v for v in vacations if v["developer_id"] == dev_id]
            if dev_vacs:
                last_end     = max(v["ended_at"] for v in dev_vacs)
                days_since_v = (datetime.now(tz=timezone.utc) - last_end).days
            else:
                days_since_v = None

            if days_since_v is None:
                rec_score = 50.0
            elif days_since_v <= 14:
                rec_score = 90.0
            elif days_since_v <= 60:
                rec_score = 70.0
            elif days_since_v <= 120:
                rec_score = 50.0
            elif days_since_v <= 180:
                rec_score = 30.0
            else:
                rec_score = 10.0

            # Burnout
            if profile["burnout"]:
                after_h = round(random.uniform(0.25, 0.55), 3)
                wkend_r = round(random.uniform(0.15, 0.40), 3)
                b_score = round(min(after_h * 0.35 + wkend_r * 0.25 + random.uniform(0.1, 0.3), 1.0), 3)
                b_level = "high" if b_score >= 0.65 else "medium"
                avg_hrs = round(random.uniform(10, 14), 2)
            else:
                after_h = round(random.uniform(0.0, 0.15), 3)
                wkend_r = round(random.uniform(0.0, 0.08), 3)
                b_score = round(min(after_h * 0.35 + wkend_r * 0.25, 1.0), 3)
                b_level = "low"
                avg_hrs = round(random.uniform(6, 9), 2)

            # Attrition risk
            if profile["attrition"] and week_offset <= 4:
                weeks_declining = 4 - week_offset + 1
                attrition_score = round(min(0.25 * weeks_declining, 1.0), 3)
                attrition_level = "high" if attrition_score >= 0.6 else "medium"
            else:
                attrition_score = round(random.uniform(0.0, 0.15), 3)
                attrition_level = "low"

            performance_scores.append({
                "developer_id":             dev_id,
                "week_start":               week_start,
                # 7 новых метрик
                "momentum":                 momentum,
                "avg_response_time_hours":  round(avg_rt, 2),
                "responsiveness_score":     resp_score,
                "task_velocity_score":      tv_score,
                "avg_comment_length":       avg_comment,
                "avg_task_complexity":      round(random.uniform(2, 8), 2),
                "engagement_depth_score":   eng_score,
                "code_churn_ratio":         round(avg_churn, 3),
                "pr_rework_rate":           round(rework,    3),
                "code_health_score":        ch_score,
                "activity_variance":        variance,
                "rhythm_score":             rhythm_score,
                "days_since_last_vacation": days_since_v,
                "post_vacation_momentum":   None,
                "recovery_score":           round(rec_score, 2),
                # Burnout
                "avg_daily_active_hours":   avg_hrs,
                "weekend_activity_ratio":   wkend_r,
                "after_hours_ratio":        after_h,
                "burnout_risk_score":       b_score,
                "burnout_risk_level":       b_level,
                # Attrition
                "attrition_risk_score":     attrition_score,
                "attrition_risk_level":     attrition_level,
            })

    for dm in daily_metrics:
        db.add(DailyMetric(**dm))
    await db.flush()

    for ps in performance_scores:
        db.add(PerformanceScore(**ps))

    await db.commit()
    print(f"Seed v4 done: {len(daily_metrics)} daily metrics, {len(performance_scores)} performance scores")