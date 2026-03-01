"""
Metrics engine — computes daily metrics and performance scores.
All logic is pure Python/numpy, no ML framework dependency.
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

WORK_HOURS_START = 9   # 9:00
WORK_HOURS_END = 19    # 19:00


# ─── Daily Metrics ────────────────────────────────────────────────────────────

def compute_daily_metrics(
    developer_id: str,
    target_date: date,
    activities: list[dict],
    jira_issues: list[dict],
    pr_data: list[dict],
) -> dict:
    """
    Aggregate raw activity events into a DailyMetric row.
    `activities` = list of ActivityEvent dicts for this dev on this date.
    """
    # Volume
    commits = [a for a in activities if a["activity_type"] == "commit"]
    prs_opened = [a for a in activities if a["activity_type"] == "pr_opened"]
    prs_merged = [a for a in activities if a["activity_type"] == "pr_merged"]
    reviews = [a for a in activities if a["activity_type"] == "pr_review"]
    issues_resolved = [a for a in activities if a["activity_type"] == "issue_resolved"]

    # Story points from resolved issues today
    sp_delivered = sum(
        (i.get("story_points") or 0)
        for i in jira_issues
        if i.get("resolved_date") == target_date
    )

    # Code volume
    lines_added = sum(a.get("lines_added", 0) for a in commits)
    lines_removed = sum(a.get("lines_removed", 0) for a in commits)
    code_churn = _code_churn(lines_added, lines_removed)

    # Quality: review coverage
    opened_count = len(prs_opened)
    approved_reviews = [r for r in reviews if r.get("quality_signal", 0) > 0]
    review_coverage = len(approved_reviews) / max(opened_count, 1)

    # Reopen rate
    total_resolved = len(issues_resolved)
    reopened = sum(
        1 for i in jira_issues
        if i.get("resolved_date") == target_date and (i.get("reopen_count") or 0) > 0
    )
    reopen_rate = reopened / max(total_resolved, 1)

    # PR review turnaround
    review_times = [
        a.get("extra_data", {}).get("review_time_hours")
        for a in reviews
        if a.get("extra_data", {}).get("review_time_hours") is not None
    ]
    avg_review_time = float(np.mean(review_times)) if review_times else None

    # Issue cycle time
    cycle_times = [
        i.get("cycle_time_hours")
        for i in jira_issues
        if i.get("resolved_date") == target_date
        and i.get("cycle_time_hours") is not None
    ]
    avg_cycle_time = float(np.mean(cycle_times)) if cycle_times else None

    # Collaboration
    review_comments_given = sum(
        a.get("extra_data", {}).get("comment_count", 0) for a in reviews
    )
    review_comments_received = sum(
        p.get("review_comments", 0) for p in pr_data
    )

    return {
        # "id": str(uuid.uuid4()),
        "developer_id": developer_id,
        "date": target_date,
        "commits_count": len(commits),
        "prs_opened": opened_count,
        "prs_merged": len(prs_merged),
        "reviews_given": len(reviews),
        "issues_resolved": len(issues_resolved),
        "story_points_delivered": sp_delivered,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "code_churn": code_churn,
        "pr_review_coverage": round(review_coverage, 3),
        "reopen_rate": round(reopen_rate, 3),
        "avg_pr_review_time_hours": avg_review_time,
        "avg_issue_cycle_time_hours": avg_cycle_time,
        "review_comments_given": review_comments_given,
        "review_comments_received": review_comments_received,
    }


def _code_churn(added: int, removed: int) -> float:
    """Churn = (added + removed) / max(added, removed). High = rewrites."""
    total = added + removed
    peak = max(added, removed, 1)
    return round(total / peak, 3)


# ─── Performance Score ─────────────────────────────────────────────────────────

def compute_performance_score(
    developer_id: str,
    week_start: datetime,
    daily_metrics: list[dict],   # 7 days of DailyMetric rows
    prev_week_metrics: list[dict],
    activity_timestamps: list[datetime],  # all activity timestamps for burnout
) -> dict:
    """
    Compute composite performance score for a week.
    Returns a PerformanceScore dict.
    """
    if not daily_metrics:
        return _empty_score(developer_id, week_start)

    delivery = _delivery_score(daily_metrics)
    quality = _quality_score(daily_metrics)
    collaboration = _collaboration_score(daily_metrics)
    consistency = _consistency_score(daily_metrics)
    velocity_trend = _velocity_trend(daily_metrics, prev_week_metrics)

    overall = (
        delivery * settings.WEIGHT_DELIVERY
        + quality * settings.WEIGHT_QUALITY
        + collaboration * settings.WEIGHT_COLLABORATION
        + consistency * settings.WEIGHT_CONSISTENCY
    )

    burnout = _burnout_signals(activity_timestamps, daily_metrics)

    return {
        # "id": str(uuid.uuid4()),
        "developer_id": developer_id,
        "week_start": week_start,
        "delivery_score": round(delivery, 2),
        "quality_score": round(quality, 2),
        "collaboration_score": round(collaboration, 2),
        "consistency_score": round(consistency, 2),
        "velocity_trend": round(velocity_trend, 3),
        "overall_score": round(overall, 2),
        **burnout,
    }


def _delivery_score(metrics: list[dict]) -> float:
    """Score based on story points, merged PRs, resolved issues."""
    sp = sum(m.get("story_points_delivered", 0) for m in metrics)
    prs = sum(m.get("prs_merged", 0) for m in metrics)
    issues = sum(m.get("issues_resolved", 0) for m in metrics)

    # Normalize: assume good week = 8SP + 4PRs + 5 issues → score 100
    raw = (sp / 8) * 50 + (prs / 4) * 30 + (issues / 5) * 20
    return min(raw, 100.0)


def _quality_score(metrics: list[dict]) -> float:
    """Score based on review coverage, reopen rate, cycle time."""
    avg_coverage = np.mean([m.get("pr_review_coverage", 0) for m in metrics])
    avg_reopen = np.mean([m.get("reopen_rate", 0) for m in metrics])

    cycle_times = [m["avg_issue_cycle_time_hours"] for m in metrics
                   if m.get("avg_issue_cycle_time_hours") is not None]
    # Lower cycle time = better; normalize: ≤8h = 100, ≥72h = 0
    if cycle_times:
        avg_ct = np.mean(cycle_times)
        ct_score = max(0, 100 - (avg_ct - 8) * (100 / 64))
    else:
        ct_score = 50  # neutral when no data

    quality = (
        avg_coverage * 40           # review discipline
        + (1 - avg_reopen) * 30     # low reopen = quality
        + ct_score * 0.30           # fast cycle
    )
    return float(min(quality, 100.0))


def _collaboration_score(metrics: list[dict]) -> float:
    """Score based on reviews given and comments."""
    reviews = sum(m.get("reviews_given", 0) for m in metrics)
    comments = sum(m.get("review_comments_given", 0) for m in metrics)

    # Good: ≥5 reviews/week + ≥10 comments/week
    score = min(reviews / 5, 1.0) * 60 + min(comments / 10, 1.0) * 40
    return float(score * 100)


def _consistency_score(metrics: list[dict]) -> float:
    """Score based on active days out of 5 work days."""
    active_days = sum(
        1 for m in metrics
        if (m.get("commits_count", 0) + m.get("prs_opened", 0)
            + m.get("reviews_given", 0) + m.get("issues_resolved", 0)) > 0
    )
    work_days = min(len(metrics), 5)
    return (active_days / max(work_days, 1)) * 100


def _velocity_trend(current: list[dict], previous: list[dict]) -> float:
    """
    Week-over-week velocity change.
    Returns delta as fraction: +0.1 = 10% improvement.
    """
    def week_throughput(ms):
        return sum(m.get("story_points_delivered", 0) + m.get("prs_merged", 0) for m in ms)

    curr_tp = week_throughput(current)
    prev_tp = week_throughput(previous)
    if prev_tp == 0:
        return 0.0
    return round((curr_tp - prev_tp) / prev_tp, 3)


def _burnout_signals(
    timestamps: list[datetime],
    daily_metrics: list[dict],
) -> dict:
    """
    Detect burnout risk from activity pattern:
    - After-hours activity ratio
    - Weekend activity ratio
    - Overload (story points >> baseline)
    - Consecutive high-activity days
    """
    if not timestamps:
        return {
            "avg_daily_active_hours": None,
            "weekend_activity_ratio": 0.0,
            "after_hours_ratio": 0.0,
            "burnout_risk_score": 0.0,
            "burnout_risk_level": "low",
        }

    total = len(timestamps)
    after_hours = sum(
        1 for t in timestamps
        if t.hour < WORK_HOURS_START or t.hour >= WORK_HOURS_END
    )
    weekends = sum(1 for t in timestamps if t.weekday() >= 5)

    after_hours_ratio = after_hours / total
    weekend_ratio = weekends / total

    # Active hours per day (rough)
    sorted_ts = sorted(timestamps)
    active_days: dict[date, list[datetime]] = {}
    for t in sorted_ts:
        d = t.date()
        active_days.setdefault(d, []).append(t)

    span_hours = []
    for day_ts in active_days.values():
        span = (day_ts[-1] - day_ts[0]).total_seconds() / 3600
        span_hours.append(span)
    avg_daily_hours = float(np.mean(span_hours)) if span_hours else None

    # Overload: too many hours worked
    overload_signal = 0.0
    if avg_daily_hours and avg_daily_hours > 10:
        overload_signal = min((avg_daily_hours - 10) / 4, 1.0)

    # Consecutive active days
    sorted_dates = sorted(active_days.keys())
    max_streak = current_streak = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1
    streak_signal = min((max_streak - 5) / 9, 1.0) if max_streak > 5 else 0.0

    # Composite burnout risk score
    burnout_score = (
        after_hours_ratio * 0.35
        + weekend_ratio * 0.25
        + overload_signal * 0.25
        + streak_signal * 0.15
    )
    burnout_score = round(float(min(burnout_score, 1.0)), 3)

    level = "low"
    if burnout_score >= 0.65:
        level = "high"
    elif burnout_score >= 0.35:
        level = "medium"

    return {
        "avg_daily_active_hours": round(avg_daily_hours, 2) if avg_daily_hours else None,
        "weekend_activity_ratio": round(weekend_ratio, 3),
        "after_hours_ratio": round(after_hours_ratio, 3),
        "burnout_risk_score": burnout_score,
        "burnout_risk_level": level,
    }


def _empty_score(developer_id: str, week_start: datetime) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "developer_id": developer_id,
        "week_start": week_start,
        "delivery_score": 0.0,
        "quality_score": 0.0,
        "collaboration_score": 0.0,
        "consistency_score": 0.0,
        "velocity_trend": 0.0,
        "overall_score": 0.0,
        "avg_daily_active_hours": None,
        "weekend_activity_ratio": 0.0,
        "after_hours_ratio": 0.0,
        "burnout_risk_score": 0.0,
        "burnout_risk_level": "low",
    }


# ─── Trend Analysis ────────────────────────────────────────────────────────────

def compute_trend(scores: list[float], window: int = 4) -> dict:
    """
    Simple trend analysis using linear regression on recent N weeks.
    Returns slope (positive = improving) and R².
    """
    if len(scores) < 2:
        return {"slope": 0.0, "r2": 0.0, "direction": "stable"}

    y = np.array(scores[-window:], dtype=float)
    x = np.arange(len(y), dtype=float)
    if len(x) < 2:
        return {"slope": 0.0, "r2": 0.0, "direction": "stable"}

    # Linear regression via least squares
    A = np.vstack([x, np.ones(len(x))]).T
    result = np.linalg.lstsq(A, y, rcond=None)
    slope, intercept = result[0]

    # R²
    y_hat = slope * x + intercept
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    direction = "stable"
    if abs(slope) > 1.0:
        direction = "improving" if slope > 0 else "declining"

    return {
        "slope": round(float(slope), 4),
        "r2": round(float(r2), 4),
        "direction": direction,
    }
