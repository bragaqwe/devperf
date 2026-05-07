from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, Any


# ── Departments ────────────────────────────────────────────────────────────────

class DepartmentOut(BaseModel):
    id:          int
    name:        str
    description: Optional[str] = None
    head_name:   Optional[str] = None
    model_config = {"from_attributes": True}


# ── Teams ─────────────────────────────────────────────────────────────────────

class TeamOut(BaseModel):
    id:               int
    name:             str
    jira_project_key: Optional[str] = None
    github_org:       Optional[str] = None
    department_id:    Optional[int] = None
    model_config = {"from_attributes": True}


# ── Developers ────────────────────────────────────────────────────────────────

class DeveloperOut(BaseModel):
    id:               int
    github_login:     Optional[str] = None
    jira_account_id:  Optional[str] = None
    display_name:     str
    email:            Optional[str] = None
    team_id:          Optional[int] = None
    model_config = {"from_attributes": True}


# ── Metrics ───────────────────────────────────────────────────────────────────

class DailyMetricOut(BaseModel):
    id:                         int
    developer_id:               int
    date:                       datetime
    commits_count:              int
    prs_opened:                 int
    prs_merged:                 int
    reviews_given:              int
    issues_resolved:            int
    story_points_delivered:     float
    lines_added:                int
    lines_removed:              int
    code_churn:                 float
    pr_review_coverage:         float
    reopen_rate:                float
    avg_pr_review_time_hours:   Optional[float] = None
    avg_issue_cycle_time_hours: Optional[float] = None
    review_comments_given:      int
    review_comments_received:   int
    model_config = {"from_attributes": True}


class PerformanceScoreOut(BaseModel):
    id:                     int
    developer_id:           int
    week_start:             datetime
    delivery_score:         float
    quality_score:          float
    collaboration_score:    float
    consistency_score:      float
    velocity_trend:         float
    overall_score:          float
    avg_daily_active_hours: Optional[float] = None
    weekend_activity_ratio: float
    after_hours_ratio:      float
    burnout_risk_score:     float
    burnout_risk_level:     str
    computed_at:            Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Timeline event ─────────────────────────────────────────────────────────────

class TimelineEvent(BaseModel):
    """A single event in the developer activity timeline."""
    id:            int
    occurred_at:   datetime
    activity_type: str
    title:         Optional[str]  = None
    description:   Optional[str]  = None
    source_type:   Optional[str]  = None
    source_url:    Optional[str]  = None      # ← clickable link
    repo:          Optional[str]  = None
    jira_issue_key: Optional[str] = None
    lines_added:   int = 0
    lines_removed: int = 0
    # enriched display fields
    badge_label:   Optional[str]  = None      # "Коммит", "PR открыт" …
    badge_color:   Optional[str]  = None


# ── Day Report ─────────────────────────────────────────────────────────────────

class DayActivityReport(BaseModel):
    developer_id:   int
    developer_name: str
    date:           date
    # aggregates
    total_commits:     int
    lines_added:       int   # только добавленные строки (зелёный)
    lines_removed:     int   # только удалённые строки (красный)
    prs_opened:        int
    prs_merged:        int
    reviews_given:     int
    issues_resolved:   int
    story_points:      float
    jira_transitions:  int   # количество смен статуса в Jira
    # unified timeline (sorted by occurred_at)
    timeline:          list[TimelineEvent]


# ── BiWeekly Score ─────────────────────────────────────────────────────────────

class BiWeeklyScoreOut(BaseModel):
    id:                     int
    developer_id:           int
    period_start:           datetime
    period_end:             datetime
    delivery_score:         float
    quality_score:          float
    collaboration_score:    float
    consistency_score:      float
    velocity_trend:         float
    overall_score:          float
    burnout_risk_score:     float
    burnout_risk_level:     str
    after_hours_ratio:      float
    weekend_activity_ratio: float
    weeks_included:         int
    delta_overall:          Optional[float] = None
    computed_at:            Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Trend ──────────────────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    week_start:          datetime
    overall_score:       float
    delivery_score:      float
    quality_score:       float
    collaboration_score: float
    burnout_risk_score:  float


class TrendAnalysis(BaseModel):
    developer_id:  int
    trend_points:  list[TrendPoint]
    slope:         float
    r2:            float
    direction:     str


# ── Team Report ────────────────────────────────────────────────────────────────

class MemberSnapshot(BaseModel):
    developer:           DeveloperOut
    overall_score:       float
    delivery_score:      float
    quality_score:       float
    collaboration_score: float
    consistency_score:   float
    burnout_risk_level:  str
    burnout_risk_score:  float
    velocity_trend:      float
    commits_last_week:   int
    prs_last_week:       int
    sp_last_week:        float


class TeamWeeklyPoint(BaseModel):
    week_start:          datetime
    avg_overall_score:   float
    avg_delivery_score:  float
    avg_quality_score:   float
    avg_collab_score:    float
    total_commits:       int
    total_prs_merged:    int
    total_sp:            float
    active_members:      int


class TeamReport(BaseModel):
    team:               TeamOut
    period_days:        int
    members:            list[MemberSnapshot]
    avg_overall_score:  float
    top_performer:      Optional[str] = None
    most_at_risk:       Optional[str] = None
    total_commits:      int
    total_prs_merged:   int
    total_sp:           float
    burnout_alerts:     list[str]
    weekly_trend:       list[TeamWeeklyPoint]


# ── Misc ───────────────────────────────────────────────────────────────────────

class DeveloperSummary(BaseModel):
    developer:    DeveloperOut
    latest_score: Optional[PerformanceScoreOut] = None
    trend:        Optional[TrendAnalysis] = None


class BurnoutAlert(BaseModel):
    developer_id:           int
    developer_name:         str
    burnout_risk_score:     float
    burnout_risk_level:     str
    after_hours_ratio:      float
    weekend_activity_ratio: float
    avg_daily_active_hours: Optional[float]
    week_start:             datetime


class SyncResponse(BaseModel):
    status:    str
    message:   str
    synced_at: datetime


# ── PR Assessment (GigaChat) ───────────────────────────────────────────────────

class PRAssessmentOut(BaseModel):
    pr_id:             int
    quality_score:     float
    complexity_score:  float
    quality_label:     str
    complexity_label:  str
    quality_reasons:   list[str]
    complexity_reasons: list[str]
    is_stub:           bool
    ai_summary:        Optional[str] = None
    assessed_at:       Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── 1:1 Meeting ───────────────────────────────────────────────────────────────

class OneOnOneTopic(BaseModel):
    topic:    str
    advice:   str
    category: str
    urgency:  int


class OneOnOneMeetingOut(BaseModel):
    id:          int
    developer_id: int
    created_at:  datetime
    risk_level:  str
    risk_score:  float
    questions:   list[OneOnOneTopic]
    notes:       Optional[str] = None
    model_config = {"from_attributes": True}
