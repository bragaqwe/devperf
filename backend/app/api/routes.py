import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from datetime import datetime, timezone, timedelta, date
from typing import Optional

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.db.models import (
    Department, Developer, Team, DailyMetric, PerformanceScore,
    GitHubCommit, GitHubPullRequest, GitHubReview, GitHubComment,
    JiraIssue, JiraTransition, ActivityEvent, ActivityType,
)
from app.models.schemas import (
    DepartmentOut, DeveloperOut, TeamOut,
    DailyMetricOut, PerformanceScoreOut,
    TrendPoint, BurnoutAlert, SyncResponse,
    DayActivityReport, TimelineEvent,
    TeamReport, MemberSnapshot, TeamWeeklyPoint,
)

router = APIRouter()

# ── colour palette for timeline badges ────────────────────────────────────────
_TYPE_META = {
    "commit":          {"label": "Коммит",            "color": "#3b82f6"},
    "pr_opened":       {"label": "PR открыт",         "color": "#10b981"},
    "pr_merged":       {"label": "PR влит",           "color": "#8b5cf6"},
    "pr_closed":       {"label": "PR закрыт",         "color": "#64748b"},
    "pr_review":       {"label": "Ревью",             "color": "#f59e0b"},
    "pr_comment":      {"label": "Комментарий PR",    "color": "#f59e0b"},
    "issue_resolved":  {"label": "Задача закрыта",    "color": "#10b981"},
    "issue_created":   {"label": "Задача создана",    "color": "#06b6d4"},
    "issue_updated":   {"label": "Задача обновлена",  "color": "#64748b"},
    "issue_reopened":  {"label": "Задача переоткрыта","color": "#ef4444"},
    "jira_transition": {"label": "Смена статуса",     "color": "#06b6d4"},
    "release":         {"label": "Релиз",             "color": "#a855f7"},
}


def _event_meta(activity_type: str) -> tuple[str, str]:
    m = _TYPE_META.get(activity_type, {"label": activity_type, "color": "#64748b"})
    return m["label"], m["color"]


# ══════════════════════════════════════════════════════════════════════════════
# DEPARTMENTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Department).order_by(Department.name))).scalars().all()


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    name:        str           = Body(...),
    description: Optional[str] = Body(None),
    head_name:   Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    dep = Department(name=name, description=description, head_name=head_name)
    db.add(dep); await db.commit(); await db.refresh(dep)
    return dep


@router.put("/departments/{dep_id}", response_model=DepartmentOut)
async def update_department(
    dep_id:      int,
    name:        Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    head_name:   Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    dep = await db.get(Department, dep_id)
    if not dep: raise HTTPException(404, "Department not found")
    if name        is not None: dep.name        = name
    if description is not None: dep.description = description
    if head_name   is not None: dep.head_name   = head_name
    await db.commit(); await db.refresh(dep)
    return dep


@router.delete("/departments/{dep_id}", status_code=204)
async def delete_department(dep_id: int, db: AsyncSession = Depends(get_db)):
    dep = await db.get(Department, dep_id)
    if not dep: raise HTTPException(404, "Department not found")
    await db.delete(dep); await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# TEAMS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/teams", response_model=list[TeamOut])
async def list_teams(
    department_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Team)
    if department_id is not None:
        q = q.where(Team.department_id == department_id)
    return (await db.execute(q.order_by(Team.name))).scalars().all()


@router.post("/teams", response_model=TeamOut, status_code=201)
async def create_team(
    name:             str           = Body(...),
    jira_project_key: Optional[str] = Body(None),
    github_org:       Optional[str] = Body(None),
    department_id:    Optional[int] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    if department_id and not await db.get(Department, department_id):
        raise HTTPException(404, "Department not found")
    team = Team(name=name, jira_project_key=jira_project_key,
                github_org=github_org, department_id=department_id)
    db.add(team); await db.commit(); await db.refresh(team)
    return team


@router.put("/teams/{team_id}", response_model=TeamOut)
async def update_team(
    team_id:          int,
    name:             Optional[str] = Body(None),
    jira_project_key: Optional[str] = Body(None),
    github_org:       Optional[str] = Body(None),
    department_id:    Optional[int] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team: raise HTTPException(404, "Team not found")
    if name             is not None: team.name             = name
    if jira_project_key is not None: team.jira_project_key = jira_project_key
    if github_org       is not None: team.github_org       = github_org
    if department_id    is not None:
        if department_id and not await db.get(Department, department_id):
            raise HTTPException(404, "Department not found")
        team.department_id = department_id
    await db.commit(); await db.refresh(team)
    return team


@router.delete("/teams/{team_id}", status_code=204)
async def delete_team(team_id: int, db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, team_id)
    if not team: raise HTTPException(404, "Team not found")
    await db.delete(team); await db.commit()


# ── Team report ────────────────────────────────────────────────────────────────

@router.get("/teams/{team_id}/report", response_model=TeamReport)
async def get_team_report(
    team_id:     int,
    period_days: int = Query(default=30, ge=7, le=180),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team: raise HTTPException(404, "Team not found")

    since = datetime.now(tz=timezone.utc) - timedelta(days=period_days)
    devs  = (await db.execute(select(Developer).where(Developer.team_id == team_id))).scalars().all()

    members: list[MemberSnapshot] = []
    all_scores: list[float] = []
    burnout_names: list[str] = []
    total_commits = total_prs = 0
    total_sp = 0.0

    for dev in devs:
        latest = await _get_latest_score(db, dev.id)
        if not latest:
            continue
        week_ago = datetime.now(tz=timezone.utc) - timedelta(days=7)
        dm_rows  = (await db.execute(
            select(DailyMetric).where(DailyMetric.developer_id == dev.id, DailyMetric.date >= week_ago)
        )).scalars().all()
        commits_lw = sum(r.commits_count          for r in dm_rows)
        prs_lw     = sum(r.prs_merged             for r in dm_rows)
        sp_lw      = sum(r.story_points_delivered for r in dm_rows)
        total_commits += commits_lw; total_prs += prs_lw; total_sp += sp_lw
        all_scores.append(latest.overall_score)
        if latest.burnout_risk_level in ("medium", "high"):
            burnout_names.append(dev.display_name)
        members.append(MemberSnapshot(
            developer=DeveloperOut.model_validate(dev),
            overall_score=latest.overall_score,
            delivery_score=latest.delivery_score,
            quality_score=latest.quality_score,
            collaboration_score=latest.collaboration_score,
            consistency_score=latest.consistency_score,
            burnout_risk_level=latest.burnout_risk_level,
            burnout_risk_score=latest.burnout_risk_score,
            velocity_trend=latest.velocity_trend,
            commits_last_week=commits_lw,
            prs_last_week=prs_lw,
            sp_last_week=sp_lw,
        ))

    members.sort(key=lambda m: m.overall_score, reverse=True)
    avg   = sum(all_scores) / len(all_scores) if all_scores else 0.0
    top   = members[0].developer.display_name if members else None
    worst = max(burnout_names, key=lambda n: next(
        (m.burnout_risk_score for m in members if m.developer.display_name == n), 0
    )) if burnout_names else None

    return TeamReport(
        team=TeamOut.model_validate(team),
        period_days=period_days,
        members=members,
        avg_overall_score=round(avg, 2),
        top_performer=top,
        most_at_risk=worst,
        total_commits=total_commits,
        total_prs_merged=total_prs,
        total_sp=round(total_sp, 1),
        burnout_alerts=burnout_names,
        weekly_trend=await _team_weekly_trend(db, [d.id for d in devs], since),
    )


# ══════════════════════════════════════════════════════════════════════════════
# DEVELOPERS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/developers", response_model=list[DeveloperOut])
async def list_developers(
    team_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Developer)
    if team_id: q = q.where(Developer.team_id == team_id)
    return (await db.execute(q)).scalars().all()


@router.get("/developers/{developer_id}", response_model=DeveloperOut)
async def get_developer(developer_id: int, db: AsyncSession = Depends(get_db)):
    dev = await db.get(Developer, developer_id)
    if not dev: raise HTTPException(404, "Developer not found")
    return dev


@router.post("/developers", response_model=DeveloperOut, status_code=201)
async def create_developer(
    display_name:    str           = Body(...),
    team_id:         int           = Body(...),
    github_login:    Optional[str] = Body(None),
    jira_account_id: Optional[str] = Body(None),
    email:           Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(Team, team_id):
        raise HTTPException(404, f"Team not found")
    if github_login and (await db.execute(
        select(Developer).where(Developer.github_login == github_login)
    )).scalar_one_or_none():
        raise HTTPException(409, f"GitHub login already registered")

    dev = Developer(display_name=display_name, team_id=team_id,
                    github_login=github_login or None,
                    jira_account_id=jira_account_id or None,
                    email=email or None)
    db.add(dev); await db.commit(); await db.refresh(dev)
    return dev


@router.put("/developers/{developer_id}", response_model=DeveloperOut)
async def update_developer(
    developer_id:    int,
    display_name:    Optional[str] = Body(None),
    github_login:    Optional[str] = Body(None),
    jira_account_id: Optional[str] = Body(None),
    email:           Optional[str] = Body(None),
    team_id:         Optional[int] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    dev = await db.get(Developer, developer_id)
    if not dev: raise HTTPException(404, "Developer not found")
    if display_name    is not None: dev.display_name    = display_name
    if github_login    is not None: dev.github_login    = github_login    or None
    if jira_account_id is not None: dev.jira_account_id = jira_account_id or None
    if email           is not None: dev.email           = email           or None
    if team_id         is not None:
        if not await db.get(Team, team_id): raise HTTPException(404, "Team not found")
        dev.team_id = team_id
    await db.commit(); await db.refresh(dev)
    return dev


@router.delete("/developers/{developer_id}", status_code=204)
async def delete_developer(developer_id: int, db: AsyncSession = Depends(get_db)):
    dev = await db.get(Developer, developer_id)
    if not dev: raise HTTPException(404, "Developer not found")
    await db.delete(dev); await db.commit()


# ── Sync ──────────────────────────────────────────────────────────────────────

@router.post("/developers/{developer_id}/sync", response_model=SyncResponse)
async def sync_developer(
    developer_id: int,
    days_back:    int        = Query(default=30, ge=1, le=365),
    github_repos: list[str] = Body(default=[]),
    db: AsyncSession = Depends(get_db),
):
    dev = await db.get(Developer, developer_id)
    if not dev: raise HTTPException(404, "Developer not found")

    from app.core.config import settings
    messages = []
    since = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    if dev.github_login and settings.GITHUB_TOKEN:
        from app.collectors.github_collector import GitHubCollector
        gh    = GitHubCollector()
        repos = list(github_repos) or []
        if not repos and dev.team_id:
            team = await db.get(Team, dev.team_id)
            if team and team.github_org:
                try:
                    repos = (await gh.get_repos_for_org(team.github_org))[:10]
                except Exception as e:
                    messages.append(f"Org repos: {e}")
        pr_count = commit_count = review_count = 0
        for repo in repos:
            try:
                all_prs = await gh.collect_pull_requests(repo, since=since)
                for pr_data in [p for p in all_prs if p.get("author_login") == dev.github_login]:
                    rd = pr_data.pop("raw_data", None)
                    ex = (await db.execute(select(GitHubPullRequest).where(
                        GitHubPullRequest.repo_full_name == repo,
                        GitHubPullRequest.number == pr_data["number"],
                    ))).scalar_one_or_none()
                    if not ex:
                        db.add(GitHubPullRequest(**pr_data, raw_data=rd))
                    else:
                        for k, v in pr_data.items():
                            if k != "id": setattr(ex, k, v)
                    pr_count += 1
                await db.flush()
                for pr in all_prs:
                    pr_res = (await db.execute(select(GitHubPullRequest).where(
                        GitHubPullRequest.repo_full_name == repo,
                        GitHubPullRequest.number == pr["number"],
                    ))).scalar_one_or_none()
                    if pr_res:
                        reviews = await gh.collect_reviews(repo, pr["number"], pr_res.id)
                        for rv in [r for r in reviews if r.get("reviewer_login") == dev.github_login]:
                            if not (await db.execute(
                                select(GitHubReview).where(GitHubReview.gh_id == rv["gh_id"])
                            )).scalar_one_or_none():
                                db.add(GitHubReview(**rv)); review_count += 1
                commits = await gh.collect_commits(repo, since=since)
                for c in [x for x in commits if x.get("author_login") == dev.github_login]:
                    if not (await db.execute(
                        select(GitHubCommit).where(GitHubCommit.sha == c["sha"])
                    )).scalar_one_or_none():
                        db.add(GitHubCommit(**c)); commit_count += 1
            except Exception as e:
                messages.append(f"GitHub {repo}: {e}")
        await db.flush()
        messages.append(f"GitHub: {pr_count} PRs, {commit_count} коммитов, {review_count} ревью")
    else:
        messages.append("GitHub: пропущено")

    if dev.jira_account_id and settings.JIRA_BASE_URL:
        from app.collectors.jira_collector import JiraCollector
        team = await db.get(Team, dev.team_id) if dev.team_id else None
        pk   = team.jira_project_key if team else None
        if pk:
            jira = JiraCollector()
            try:
                issues_raw = await jira.collect_issues(pk, updated_after=since)
                ic = tc = 0
                for raw in [i for i in issues_raw if i.get("assignee_account_id") == dev.jira_account_id]:
                    transitions = raw.pop("transitions", [])
                    raw.pop("raw_data", None)
                    raw.pop("id", None)   # Integer PK генерирует БД, не передаём

                    # Пересчитываем reopen_count на основе полученных переходов
                    raw["reopen_count"] = sum(
                        1 for t in transitions
                        if (t.get("to_status") or "").lower() in ("open", "reopened", "to do", "backlog")
                        and (t.get("from_status") or "").lower() in ("done", "closed", "resolved")
                    )

                    ex = (await db.execute(
                        select(JiraIssue).where(JiraIssue.jira_id == raw["jira_id"])
                    )).scalar_one_or_none()

                    if not ex:
                        io = JiraIssue(**raw)
                        db.add(io)
                    else:
                        for k, v in raw.items():
                            setattr(ex, k, v)
                        io = ex
                    await db.flush()   # нужен io.id для FK

                    for t in transitions:
                        # убираем лишние ключи, которых нет в модели
                        t.pop("id", None)
                        t["issue_id"] = io.id
                        # дедупликация по (issue_id, transitioned_at, to_status)
                        exists = (await db.execute(
                            select(JiraTransition).where(
                                JiraTransition.issue_id     == io.id,
                                JiraTransition.to_status    == t["to_status"],
                                JiraTransition.transitioned_at == t["transitioned_at"],
                            )
                        )).scalar_one_or_none()
                        if not exists:
                            db.add(JiraTransition(**t))
                            tc += 1
                    ic += 1

                await db.flush()
                messages.append(f"Jira: {ic} задач, {tc} переходов")
            except Exception as e:
                logger.exception("Jira sync error")
                messages.append(f"Jira ошибка: {e}")
        else:
            messages.append("Jira: нет project key")
    else:
        messages.append("Jira: пропущено")

    await _rebuild_developer_metrics(db, dev, since)
    messages.append("Метрики пересчитаны")
    await db.commit()
    return SyncResponse(status="ok", message=" | ".join(messages),
                        synced_at=datetime.now(tz=timezone.utc))


# ── Scores & metrics ──────────────────────────────────────────────────────────

@router.get("/developers/{developer_id}/scores", response_model=list[PerformanceScoreOut])
async def get_developer_scores(
    developer_id: int,
    weeks: int = Query(default=12, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(tz=timezone.utc) - timedelta(weeks=weeks)
    return (await db.execute(
        select(PerformanceScore)
        .where(PerformanceScore.developer_id == developer_id,
               PerformanceScore.week_start >= since)
        .order_by(PerformanceScore.week_start)
    )).scalars().all()


@router.get("/developers/{developer_id}/daily-metrics", response_model=list[DailyMetricOut])
async def get_daily_metrics(
    developer_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    return (await db.execute(
        select(DailyMetric)
        .where(DailyMetric.developer_id == developer_id, DailyMetric.date >= since)
        .order_by(DailyMetric.date)
    )).scalars().all()


# ── Day drill-down (timeline) ─────────────────────────────────────────────────

@router.get("/developers/{developer_id}/day/{day}", response_model=DayActivityReport)
async def get_day_activity(
    developer_id: int,
    day:          str,        # YYYY-MM-DD
    db: AsyncSession = Depends(get_db),
):
    """Full timeline for one developer on one calendar day, sorted by time."""
    dev = await db.get(Developer, developer_id)
    if not dev: raise HTTPException(404, "Developer not found")
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(400, "day must be YYYY-MM-DD")

    day_start = datetime(d.year, d.month, d.day,  0,  0,  0, tzinfo=timezone.utc)
    day_end   = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)

    events: list[TimelineEvent] = []

    # ── Commits ────────────────────────────────────────────────────────────────
    if dev.github_login:
        for c in (await db.execute(
            select(GitHubCommit)
            .where(GitHubCommit.author_login == dev.github_login,
                   GitHubCommit.committed_at.between(day_start, day_end))
            .order_by(GitHubCommit.committed_at)
        )).scalars().all():
            label, color = _event_meta("commit")
            events.append(TimelineEvent(
                id=c.id, occurred_at=c.committed_at,
                activity_type="commit",
                title=c.message.split("\n")[0][:120],
                description=f"+{c.additions} / -{c.deletions} строк · {c.repo_full_name}",
                source_type="github_commit",
                source_url=c.html_url or _gh_commit_url(c.repo_full_name, c.sha),
                repo=c.repo_full_name,
                jira_issue_key=c.jira_issue_key,
                lines_added=c.additions or 0,
                lines_removed=c.deletions or 0,
                badge_label=label, badge_color=color,
            ))

        # ── PRs opened / merged / closed today ────────────────────────────────
        for pr in (await db.execute(
            select(GitHubPullRequest)
            .where(GitHubPullRequest.author_login == dev.github_login,
                   GitHubPullRequest.created_at.between(day_start, day_end))
            .order_by(GitHubPullRequest.created_at)
        )).scalars().all():
            label, color = _event_meta("pr_opened")
            events.append(TimelineEvent(
                id=pr.id * 10,        # avoid id collision
                occurred_at=pr.created_at,
                activity_type="pr_opened",
                title=f"PR #{pr.number}: {pr.title[:100]}",
                description=f"{pr.repo_full_name} · +{pr.additions} / -{pr.deletions}",
                source_type="github_pr",
                source_url=pr.html_url or _gh_pr_url(pr.repo_full_name, pr.number),
                repo=pr.repo_full_name,
                jira_issue_key=pr.jira_issue_key,
                lines_added=pr.additions or 0,
                lines_removed=pr.deletions or 0,
                badge_label=label, badge_color=color,
            ))

        for pr in (await db.execute(
            select(GitHubPullRequest)
            .where(GitHubPullRequest.author_login == dev.github_login,
                   GitHubPullRequest.merged_at.isnot(None),
                   GitHubPullRequest.merged_at.between(day_start, day_end))
            .order_by(GitHubPullRequest.merged_at)
        )).scalars().all():
            label, color = _event_meta("pr_merged")
            events.append(TimelineEvent(
                id=pr.id * 10 + 1,
                occurred_at=pr.merged_at,
                activity_type="pr_merged",
                title=f"PR #{pr.number} влит: {pr.title[:100]}",
                description=pr.repo_full_name,
                source_type="github_pr",
                source_url=pr.html_url or _gh_pr_url(pr.repo_full_name, pr.number),
                repo=pr.repo_full_name,
                jira_issue_key=pr.jira_issue_key,
                badge_label=label, badge_color=color,
            ))

        for pr in (await db.execute(
            select(GitHubPullRequest)
            .where(GitHubPullRequest.author_login == dev.github_login,
                   GitHubPullRequest.state == "closed",
                   GitHubPullRequest.merged_at.is_(None),
                   GitHubPullRequest.closed_at.isnot(None),
                   GitHubPullRequest.closed_at.between(day_start, day_end))
            .order_by(GitHubPullRequest.closed_at)
        )).scalars().all():
            label, color = _event_meta("pr_closed")
            events.append(TimelineEvent(
                id=pr.id * 10 + 2,
                occurred_at=pr.closed_at,
                activity_type="pr_closed",
                title=f"PR #{pr.number} закрыт: {pr.title[:100]}",
                description=pr.repo_full_name,
                source_type="github_pr",
                source_url=pr.html_url or _gh_pr_url(pr.repo_full_name, pr.number),
                repo=pr.repo_full_name,
                badge_label=label, badge_color=color,
            ))

        # ── Reviews ────────────────────────────────────────────────────────────
        for rv in (await db.execute(
            select(GitHubReview, GitHubPullRequest)
            .join(GitHubPullRequest, GitHubReview.pr_id == GitHubPullRequest.id, isouter=True)
            .where(GitHubReview.reviewer_login == dev.github_login,
                   GitHubReview.submitted_at.between(day_start, day_end))
            .order_by(GitHubReview.submitted_at)
        )).all():
            review, pr = rv
            review_state_label = {
                "APPROVED": "одобрено",
                "CHANGES_REQUESTED": "запрошены правки",
                "COMMENTED": "оставил комментарий",
            }.get(review.state, review.state)
            label, color = _event_meta("pr_review")
            events.append(TimelineEvent(
                id=review.id * 100,
                occurred_at=review.submitted_at,
                activity_type="pr_review",
                title=f"Ревью: {review_state_label}" + (f" → PR #{pr.number}" if pr else ""),
                description=(review.body or "")[:200] or None,
                source_type="github_review",
                source_url=review.html_url or (pr.html_url if pr else None),
                repo=pr.repo_full_name if pr else None,
                badge_label=label, badge_color=color,
            ))

        # ── PR comments ────────────────────────────────────────────────────────
        for cm in (await db.execute(
            select(GitHubComment, GitHubPullRequest)
            .join(GitHubPullRequest, GitHubComment.pr_id == GitHubPullRequest.id, isouter=True)
            .where(GitHubComment.author_login == dev.github_login,
                   GitHubComment.created_at.between(day_start, day_end))
            .order_by(GitHubComment.created_at)
        )).all():
            comment, pr = cm
            label, color = _event_meta("pr_comment")
            events.append(TimelineEvent(
                id=comment.id * 1000,
                occurred_at=comment.created_at,
                activity_type="pr_comment",
                title="Комментарий в PR" + (f" #{pr.number}" if pr else ""),
                description=(comment.body or "")[:200] or None,
                source_type="github_comment",
                source_url=comment.html_url,
                repo=pr.repo_full_name if pr else None,
                badge_label=label, badge_color=color,
            ))

    # ── Jira transitions ───────────────────────────────────────────────────────
    if dev.jira_account_id:
        for t, issue in (await db.execute(
            select(JiraTransition, JiraIssue)
            .join(JiraIssue, JiraTransition.issue_id == JiraIssue.id)
            .where(JiraIssue.assignee_account_id == dev.jira_account_id,
                   JiraTransition.transitioned_at.between(day_start, day_end))
            .order_by(JiraTransition.transitioned_at)
        )).all():
            fr  = t.from_status or "—"
            to  = t.to_status
            label, color = _event_meta("jira_transition")
            is_resolved  = to.lower() in ("done", "closed", "resolved", "завершено")
            if is_resolved:
                label, color = _event_meta("issue_resolved")
            events.append(TimelineEvent(
                id=t.id * 10000,
                occurred_at=t.transitioned_at,
                activity_type="issue_resolved" if is_resolved else "jira_transition",
                title=f"{issue.key}: {issue.summary[:80]}",
                description=f"{fr} → {to}" + (f" · {issue.story_points} SP" if issue.story_points else ""),
                source_type="jira_issue",
                source_url=issue.html_url or _jira_url(issue.key),
                jira_issue_key=issue.key,
                badge_label=label, badge_color=color,
            ))

        # Jira issues resolved today (no transition record)
        for issue in (await db.execute(
            select(JiraIssue)
            .where(JiraIssue.assignee_account_id == dev.jira_account_id,
                   JiraIssue.resolved_at.isnot(None),
                   JiraIssue.resolved_at.between(day_start, day_end))
            .order_by(JiraIssue.resolved_at)
        )).scalars().all():
            # Avoid duplicating if transition already added
            already = any(e.jira_issue_key == issue.key and e.activity_type == "issue_resolved" for e in events)
            if not already:
                label, color = _event_meta("issue_resolved")
                events.append(TimelineEvent(
                    id=issue.id * 10000 + 1,
                    occurred_at=issue.resolved_at,
                    activity_type="issue_resolved",
                    title=f"{issue.key}: {issue.summary[:80]}",
                    description=f"Закрыта" + (f" · {issue.story_points} SP" if issue.story_points else ""),
                    source_type="jira_issue",
                    source_url=issue.html_url or _jira_url(issue.key),
                    jira_issue_key=issue.key,
                    badge_label=label, badge_color=color,
                ))

    # sort by time
    events.sort(key=lambda e: e.occurred_at)

    # compute aggregates
    commits_events  = [e for e in events if e.activity_type == "commit"]
    pr_open_events  = [e for e in events if e.activity_type == "pr_opened"]
    pr_merge_events = [e for e in events if e.activity_type == "pr_merged"]
    review_events   = [e for e in events if e.activity_type == "pr_review"]
    resolved_events = [e for e in events if e.activity_type == "issue_resolved"]

    # story points from jira resolved
    sp = 0.0
    if dev.jira_account_id:
        issues_today = (await db.execute(
            select(JiraIssue).where(
                JiraIssue.assignee_account_id == dev.jira_account_id,
                JiraIssue.resolved_at.between(day_start, day_end),
            )
        )).scalars().all()
        sp = sum(i.story_points or 0 for i in issues_today)

    return DayActivityReport(
        developer_id=developer_id,
        developer_name=dev.display_name,
        date=d,
        total_commits=len(commits_events),
        lines_added=sum(e.lines_added for e in commits_events),
        lines_removed=sum(e.lines_removed for e in commits_events),
        prs_opened=len(pr_open_events),
        prs_merged=len(pr_merge_events),
        reviews_given=len(review_events),
        issues_resolved=len(resolved_events),
        story_points=sp,
        jira_transitions=len([e for e in events if e.activity_type == "jira_transition"]),
        timeline=events,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD / BURNOUT
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/leaderboard", response_model=list[dict])
async def get_leaderboard(
    team_id:       Optional[int] = None,
    department_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Developer)
    if team_id: q = q.where(Developer.team_id == team_id)
    if department_id:
        team_ids = (await db.execute(
            select(Team.id).where(Team.department_id == department_id)
        )).scalars().all()
        q = q.where(Developer.team_id.in_(team_ids))
    devs  = (await db.execute(q)).scalars().all()
    board = []
    for dev in devs:
        latest = await _get_latest_score(db, dev.id)
        if latest:
            board.append({
                "developer_id": dev.id, "display_name": dev.display_name,
                "github_login": dev.github_login, "team_id": dev.team_id,
                "overall_score": latest.overall_score,
                "delivery_score": latest.delivery_score,
                "quality_score": latest.quality_score,
                "collaboration_score": latest.collaboration_score,
                "consistency_score": latest.consistency_score,
                "burnout_risk_level": latest.burnout_risk_level,
                "burnout_risk_score": latest.burnout_risk_score,
                "velocity_trend": latest.velocity_trend,
            })
    return sorted(board, key=lambda x: x["overall_score"], reverse=True)


@router.get("/burnout/alerts", response_model=list[BurnoutAlert])
async def get_burnout_alerts(
    team_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Developer)
    if team_id: q = q.where(Developer.team_id == team_id)
    devs   = (await db.execute(q)).scalars().all()
    alerts = []
    for dev in devs:
        latest = await _get_latest_score(db, dev.id)
        if latest and latest.burnout_risk_level in ("medium", "high"):
            alerts.append(BurnoutAlert(
                developer_id=dev.id, developer_name=dev.display_name,
                burnout_risk_score=latest.burnout_risk_score,
                burnout_risk_level=latest.burnout_risk_level,
                after_hours_ratio=latest.after_hours_ratio,
                weekend_activity_ratio=latest.weekend_activity_ratio,
                avg_daily_active_hours=latest.avg_daily_active_hours,
                week_start=latest.week_start,
            ))
    return sorted(alerts, key=lambda a: a.burnout_risk_score, reverse=True)


# ── Seed ─────────────────────────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse)
async def trigger_seed(db: AsyncSession = Depends(get_db)):
    from app.services.seed_data import run_seed
    await run_seed(db)
    return SyncResponse(status="ok", message="Демо-данные загружены",
                        synced_at=datetime.now(tz=timezone.utc))


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def _get_latest_score(db, developer_id) -> Optional[PerformanceScoreOut]:
    score = (await db.execute(
        select(PerformanceScore)
        .where(PerformanceScore.developer_id == developer_id)
        .order_by(PerformanceScore.week_start.desc()).limit(1)
    )).scalar_one_or_none()
    return PerformanceScoreOut.model_validate(score) if score else None


async def _team_weekly_trend(db, dev_ids, since):
    if not dev_ids:
        return []
    points = []
    week = since.replace(hour=0, minute=0, second=0, microsecond=0)
    now  = datetime.now(tz=timezone.utc)
    while week <= now:
        week_end = week + timedelta(days=7)
        scores = (await db.execute(
            select(PerformanceScore).where(
                PerformanceScore.developer_id.in_(dev_ids),
                PerformanceScore.week_start >= week,
                PerformanceScore.week_start <  week_end,
            )
        )).scalars().all()
        dms = (await db.execute(
            select(DailyMetric).where(
                DailyMetric.developer_id.in_(dev_ids),
                DailyMetric.date >= week, DailyMetric.date < week_end,
            )
        )).scalars().all()
        if scores or dms:
            points.append(TeamWeeklyPoint(
                week_start=week,
                avg_overall_score  = round(sum(s.overall_score      for s in scores) / max(len(scores),1), 2),
                avg_delivery_score = round(sum(s.delivery_score      for s in scores) / max(len(scores),1), 2),
                avg_quality_score  = round(sum(s.quality_score       for s in scores) / max(len(scores),1), 2),
                avg_collab_score   = round(sum(s.collaboration_score for s in scores) / max(len(scores),1), 2),
                total_commits    = sum(d.commits_count          for d in dms),
                total_prs_merged = sum(d.prs_merged             for d in dms),
                total_sp         = round(sum(d.story_points_delivered for d in dms), 1),
                active_members   = len({s.developer_id for s in scores}),
            ))
        week = week_end
    return points


async def _rebuild_developer_metrics(db, dev, since):
    from app.services.metrics_engine import compute_daily_metrics, compute_performance_score
    from collections import defaultdict

    await db.execute(delete(ActivityEvent).where(
        ActivityEvent.developer_id == dev.id, ActivityEvent.occurred_at >= since))
    await db.execute(delete(DailyMetric).where(
        DailyMetric.developer_id == dev.id, DailyMetric.date >= since))
    await db.execute(delete(PerformanceScore).where(
        PerformanceScore.developer_id == dev.id, PerformanceScore.week_start >= since))
    await db.flush()

    events = []

    if dev.github_login:
        for pr in (await db.execute(select(GitHubPullRequest).where(
            GitHubPullRequest.author_login == dev.github_login,
            GitHubPullRequest.created_at >= since,
        ))).scalars().all():
            url = pr.html_url or _gh_pr_url(pr.repo_full_name, pr.number)
            label, color = _event_meta("pr_opened")
            events.append(ActivityEvent(
                developer_id=dev.id, activity_type=ActivityType.PR_OPENED,
                occurred_at=_dt(pr.created_at),
                lines_added=pr.additions or 0, lines_removed=pr.deletions or 0,
                complexity_score=min((pr.additions or 0) / 100, 10.0),
                source_id=pr.id, source_type="github_pr", source_url=url,
                jira_issue_key=pr.jira_issue_key, repo=pr.repo_full_name,
                title=f"PR #{pr.number}: {pr.title[:100]}",
                description=f"+{pr.additions}/{pr.deletions} строк"))
            if pr.merged_at:
                label2, color2 = _event_meta("pr_merged")
                events.append(ActivityEvent(
                    developer_id=dev.id, activity_type=ActivityType.PR_MERGED,
                    occurred_at=_dt(pr.merged_at),
                    source_id=pr.id, source_type="github_pr", source_url=url,
                    jira_issue_key=pr.jira_issue_key, repo=pr.repo_full_name,
                    title=f"PR #{pr.number} влит: {pr.title[:100]}"))

        for c in (await db.execute(select(GitHubCommit).where(
            GitHubCommit.author_login == dev.github_login,
            GitHubCommit.committed_at >= since,
        ))).scalars().all():
            events.append(ActivityEvent(
                developer_id=dev.id, activity_type=ActivityType.COMMIT,
                occurred_at=_dt(c.committed_at),
                lines_added=c.additions or 0, lines_removed=c.deletions or 0,
                source_id=c.id, source_type="github_commit",
                source_url=c.html_url or _gh_commit_url(c.repo_full_name, c.sha),
                jira_issue_key=c.jira_issue_key, repo=c.repo_full_name,
                title=c.message.split("\n")[0][:120],
                description=f"+{c.additions}/{c.deletions} строк"))

        for rv in (await db.execute(select(GitHubReview).where(
            GitHubReview.reviewer_login == dev.github_login,
            GitHubReview.submitted_at >= since,
        ))).scalars().all():
            q = 1.0 if rv.state == "APPROVED" else (-0.5 if rv.state == "CHANGES_REQUESTED" else 0.2)
            events.append(ActivityEvent(
                developer_id=dev.id, activity_type=ActivityType.PR_REVIEW,
                occurred_at=_dt(rv.submitted_at),
                quality_signal=q, source_id=rv.id, source_type="github_review",
                source_url=rv.html_url))

    if dev.jira_account_id:
        for issue in (await db.execute(select(JiraIssue).where(
            JiraIssue.assignee_account_id == dev.jira_account_id,
            JiraIssue.resolved_at >= since,
        ))).scalars().all():
            events.append(ActivityEvent(
                developer_id=dev.id, activity_type=ActivityType.ISSUE_RESOLVED,
                occurred_at=_dt(issue.resolved_at),
                complexity_score=issue.story_points or 1.0,
                quality_signal=-0.5 if (issue.reopen_count or 0) > 0 else 1.0,
                source_id=issue.id, source_type="jira_issue",
                source_url=issue.html_url or _jira_url(issue.key),
                jira_issue_key=issue.key,
                title=f"{issue.key}: {issue.summary[:80]}",
                description=f"{issue.story_points or 0} SP"))

    for e in events:
        db.add(e)
    await db.flush()

    if not events:
        return

    by_date = defaultdict(list)
    for e in events:
        by_date[e.occurred_at.date()].append({
            "activity_type": e.activity_type.value,
            "lines_added": e.lines_added, "lines_removed": e.lines_removed,
            "quality_signal": e.quality_signal, "extra_data": {},
        })

    for day, day_evs in sorted(by_date.items()):
        db.add(DailyMetric(**compute_daily_metrics(
            developer_id=dev.id, target_date=day,
            activities=day_evs, jira_issues=[], pr_data=[])))
    await db.flush()

    all_ts = [e.occurred_at for e in events]
    now    = datetime.now(tz=timezone.utc)
    week   = since.replace(hour=0, minute=0, second=0, microsecond=0)
    while week <= now:
        week_end = week + timedelta(days=7)
        wm = [{c.name: getattr(r, c.name) for c in r.__table__.columns}
              for r in (await db.execute(select(DailyMetric).where(
                  DailyMetric.developer_id == dev.id,
                  DailyMetric.date >= week, DailyMetric.date < week_end,
              ))).scalars().all()]
        pm = [{c.name: getattr(r, c.name) for c in r.__table__.columns}
              for r in (await db.execute(select(DailyMetric).where(
                  DailyMetric.developer_id == dev.id,
                  DailyMetric.date >= week - timedelta(days=7), DailyMetric.date < week,
              ))).scalars().all()]
        wts = [t for t in all_ts if week <= t < week_end]
        if wm:
            db.add(PerformanceScore(**compute_performance_score(dev.id, week, wm, pm, wts)))
        week = week_end
    await db.flush()


def _dt(val) -> datetime:
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    if isinstance(val, str):
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    return datetime.now(tz=timezone.utc)


def _gh_commit_url(repo: str, sha: str) -> str:
    return f"https://github.com/{repo}/commit/{sha}"

def _gh_pr_url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/pull/{number}"

def _jira_url(key: str) -> Optional[str]:
    from app.core.config import settings
    if settings.JIRA_BASE_URL:
        return f"{settings.JIRA_BASE_URL}/browse/{key}"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# JIRA DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/jira/test")
async def jira_test(project_key: str = Query(default="CORE")):
    """
    Диагностический эндпоинт — проверяет связь с Jira и возвращает:
    - текущего пользователя (myself)
    - первые 3 задачи проекта без changelog
    - changelog первой задачи (переходы статусов)
    Позволяет убедиться что API работает корректно перед полным sync.
    """
    from app.core.config import settings
    from app.collectors.jira_collector import JiraCollector
    import httpx
    from base64 import b64encode

    if not settings.JIRA_BASE_URL:
        raise HTTPException(400, "JIRA_BASE_URL не настроен")

    jira = JiraCollector()
    result: dict = {"base_url": settings.JIRA_BASE_URL, "project_key": project_key}

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. myself
        try:
            me = await jira._get(client, f"{jira.base_url}/rest/api/3/myself")
            result["myself"] = {
                "accountId":   me.get("accountId"),
                "displayName": me.get("displayName"),
                "email":       me.get("emailAddress"),
            }
        except Exception as e:
            result["myself_error"] = str(e)

        # 2. search — первые 3 задачи без changelog
        try:
            data = await jira._get(
                client,
                f"{jira.base_url}/rest/api/3/search",
                params={
                    "jql":        f"project = {project_key} ORDER BY updated DESC",
                    "startAt":    0,
                    "maxResults": 3,
                    "fields":     "summary,status,assignee,updated",
                },
            )
            result["search_total"] = data.get("total", 0)
            result["issues_sample"] = [
                {
                    "key":      i["key"],
                    "summary":  i["fields"].get("summary", "")[:60],
                    "status":   (i["fields"].get("status") or {}).get("name"),
                    "assignee": ((i["fields"].get("assignee") or {}).get("displayName")),
                }
                for i in data.get("issues", [])
            ]
            # 3. changelog первой задачи
            if data.get("issues"):
                first_key = data["issues"][0]["key"]
                try:
                    cl = await jira._get(
                        client,
                        f"{jira.base_url}/rest/api/3/issue/{first_key}/changelog",
                        params={"startAt": 0, "maxResults": 10},
                    )
                    status_changes = [
                        {
                            "date": entry.get("created"),
                            "author": (entry.get("author") or {}).get("displayName"),
                            "from": next(
                                (it.get("fromString") for it in entry.get("items", []) if it.get("field") == "status"),
                                None,
                            ),
                            "to": next(
                                (it.get("toString") for it in entry.get("items", []) if it.get("field") == "status"),
                                None,
                            ),
                        }
                        for entry in cl.get("values", [])
                        if any(it.get("field") == "status" for it in entry.get("items", []))
                    ]
                    result["changelog_issue"]    = first_key
                    result["changelog_total"]    = cl.get("total", 0)
                    result["status_transitions"] = status_changes
                except Exception as e:
                    result["changelog_error"] = str(e)
        except Exception as e:
            result["search_error"] = str(e)

    return result
