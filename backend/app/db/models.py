from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text,
    ForeignKey, JSON, Enum as SAEnum, Index, UniqueConstraint, BigInteger,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    pass


class ActivityType(str, enum.Enum):
    COMMIT          = "commit"
    PR_OPENED       = "pr_opened"
    PR_MERGED       = "pr_merged"
    PR_CLOSED       = "pr_closed"
    PR_REVIEW       = "pr_review"
    PR_COMMENT      = "pr_comment"
    ISSUE_RESOLVED  = "issue_resolved"
    ISSUE_CREATED   = "issue_created"
    ISSUE_UPDATED   = "issue_updated"
    ISSUE_REOPENED  = "issue_reopened"
    JIRA_TRANSITION = "jira_transition"
    RELEASE         = "release"


class Department(Base):
    __tablename__ = "departments"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    head_name   = Column(String(255), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    teams       = relationship("Team", back_populates="department")


class Team(Base):
    __tablename__ = "teams"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(255), nullable=False)
    jira_project_key = Column(String(50),  nullable=True)
    github_org       = Column(String(255), nullable=True)
    department_id    = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    department       = relationship("Department", back_populates="teams")
    members          = relationship("Developer",  back_populates="team")


class Developer(Base):
    __tablename__ = "developers"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    github_login     = Column(String(255), unique=True, nullable=True)
    jira_account_id  = Column(String(255), unique=True, nullable=True)
    display_name     = Column(String(255), nullable=False)
    email            = Column(String(255), nullable=True)
    team_id          = Column(Integer, ForeignKey("teams.id"), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    team               = relationship("Team",             back_populates="members")
    activities         = relationship("ActivityEvent",    back_populates="developer")
    daily_metrics      = relationship("DailyMetric",      back_populates="developer")
    performance_scores = relationship("PerformanceScore", back_populates="developer")
    biweekly_scores    = relationship("BiWeeklyScore",    back_populates="developer")


class GitHubPullRequest(Base):
    __tablename__ = "github_pull_requests"
    id              = Column(Integer,    primary_key=True, autoincrement=True)
    gh_id           = Column(BigInteger, nullable=False)
    repo_full_name  = Column(String(512), nullable=False)
    number          = Column(Integer,    nullable=False)
    title           = Column(Text,       nullable=False)
    state           = Column(String(50), nullable=False)
    author_login    = Column(String(255), nullable=True)
    html_url        = Column(Text,       nullable=True)
    created_at      = Column(DateTime(timezone=True), nullable=False)
    merged_at       = Column(DateTime(timezone=True), nullable=True)
    closed_at       = Column(DateTime(timezone=True), nullable=True)
    additions       = Column(Integer, default=0)
    deletions       = Column(Integer, default=0)
    changed_files   = Column(Integer, default=0)
    review_comments = Column(Integer, default=0)
    commits_count   = Column(Integer, default=0)
    jira_issue_key  = Column(String(50), nullable=True)
    raw_data        = Column(JSON,       nullable=True)
    reviews         = relationship("GitHubReview", back_populates="pull_request")
    __table_args__ = (
        UniqueConstraint("repo_full_name", "number", name="uq_pr_repo_number"),
        Index("ix_pr_author",  "author_login"),
        Index("ix_pr_created", "created_at"),
    )


class GitHubCommit(Base):
    __tablename__ = "github_commits"
    id             = Column(Integer,    primary_key=True, autoincrement=True)
    sha            = Column(String(40), unique=True, nullable=False)
    repo_full_name = Column(String(512), nullable=False)
    author_login   = Column(String(255), nullable=True)
    author_email   = Column(String(255), nullable=True)
    message        = Column(Text,       nullable=False)
    html_url       = Column(Text,       nullable=True)
    committed_at   = Column(DateTime(timezone=True), nullable=False)
    additions      = Column(Integer, default=0)
    deletions      = Column(Integer, default=0)
    jira_issue_key = Column(String(50), nullable=True)
    __table_args__ = (
        Index("ix_commit_author", "author_login"),
        Index("ix_commit_date",   "committed_at"),
    )


class GitHubReview(Base):
    __tablename__ = "github_reviews"
    id             = Column(Integer,    primary_key=True, autoincrement=True)
    gh_id          = Column(BigInteger, nullable=False)
    pr_id          = Column(Integer,    ForeignKey("github_pull_requests.id"))
    reviewer_login = Column(String(255), nullable=True)
    state          = Column(String(50),  nullable=False)
    html_url       = Column(Text,        nullable=True)
    submitted_at   = Column(DateTime(timezone=True), nullable=False)
    body           = Column(Text, nullable=True)
    pull_request   = relationship("GitHubPullRequest", back_populates="reviews")
    __table_args__ = (
        Index("ix_review_reviewer", "reviewer_login"),
        Index("ix_review_date",     "submitted_at"),
    )


class GitHubComment(Base):
    __tablename__ = "github_comments"
    id           = Column(Integer,    primary_key=True, autoincrement=True)
    gh_id        = Column(BigInteger, nullable=False, unique=True)
    pr_id        = Column(Integer,    ForeignKey("github_pull_requests.id"), nullable=True)
    author_login = Column(String(255), nullable=True)
    body         = Column(Text,       nullable=True)
    html_url     = Column(Text,       nullable=True)
    created_at   = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index("ix_comment_author", "author_login"),
        Index("ix_comment_date",   "created_at"),
    )


class JiraIssue(Base):
    __tablename__ = "jira_issues"
    id                  = Column(Integer,    primary_key=True, autoincrement=True)
    jira_id             = Column(String(50), unique=True, nullable=False)
    key                 = Column(String(50), unique=True, nullable=False)
    project_key         = Column(String(50), nullable=False)
    issue_type          = Column(String(100), nullable=False)
    summary             = Column(Text,       nullable=False)
    status              = Column(String(100), nullable=False)
    assignee_account_id = Column(String(255), nullable=True)
    reporter_account_id = Column(String(255), nullable=True)
    priority            = Column(String(50),  nullable=True)
    story_points        = Column(Float,       nullable=True)
    html_url            = Column(Text,        nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False)
    updated_at          = Column(DateTime(timezone=True), nullable=True)
    resolved_at         = Column(DateTime(timezone=True), nullable=True)
    due_date            = Column(DateTime(timezone=True), nullable=True)
    reopen_count        = Column(Integer, default=0)
    labels              = Column(JSON,    nullable=True)
    raw_data            = Column(JSON,    nullable=True)
    transitions         = relationship("JiraTransition", back_populates="issue")
    __table_args__ = (
        Index("ix_jira_assignee", "assignee_account_id"),
        Index("ix_jira_project",  "project_key"),
        Index("ix_jira_date",     "resolved_at"),
    )


class JiraTransition(Base):
    __tablename__ = "jira_transitions"
    id                = Column(Integer,    primary_key=True, autoincrement=True)
    issue_id          = Column(Integer,    ForeignKey("jira_issues.id"), nullable=False)
    from_status       = Column(String(100), nullable=True)
    to_status         = Column(String(100), nullable=False)
    author_account_id = Column(String(255), nullable=True)
    transitioned_at   = Column(DateTime(timezone=True), nullable=False)
    issue             = relationship("JiraIssue", back_populates="transitions")
    __table_args__    = (Index("ix_transition_date", "transitioned_at"),)


class ActivityEvent(Base):
    """Single row per developer action — powers the timeline."""
    __tablename__ = "activity_events"
    id               = Column(Integer,  primary_key=True, autoincrement=True)
    developer_id     = Column(Integer,  ForeignKey("developers.id"), nullable=False)
    activity_type    = Column(SAEnum(ActivityType), nullable=False)
    occurred_at      = Column(DateTime(timezone=True), nullable=False)
    lines_added      = Column(Integer, default=0)
    lines_removed    = Column(Integer, default=0)
    complexity_score = Column(Float,   default=0.0)
    quality_signal   = Column(Float,   default=0.0)
    source_id        = Column(Integer, nullable=True)
    source_type      = Column(String(50), nullable=True)
    source_url       = Column(Text,    nullable=True)
    jira_issue_key   = Column(String(50),  nullable=True)
    repo             = Column(String(512), nullable=True)
    title            = Column(Text,    nullable=True)
    description      = Column(Text,    nullable=True)
    extra_data       = Column(JSON,    nullable=True)
    developer        = relationship("Developer", back_populates="activities")
    __table_args__ = (
        Index("ix_activity_dev_date", "developer_id", "occurred_at"),
        Index("ix_activity_date",     "occurred_at"),
        Index("ix_activity_type",     "activity_type"),
    )


class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    id                         = Column(Integer, primary_key=True, autoincrement=True)
    developer_id               = Column(Integer, ForeignKey("developers.id"), nullable=False)
    date                       = Column(DateTime(timezone=True), nullable=False)
    commits_count              = Column(Integer, default=0)
    prs_opened                 = Column(Integer, default=0)
    prs_merged                 = Column(Integer, default=0)
    reviews_given              = Column(Integer, default=0)
    issues_resolved            = Column(Integer, default=0)
    story_points_delivered     = Column(Float,   default=0.0)
    lines_added                = Column(Integer, default=0)
    lines_removed              = Column(Integer, default=0)
    code_churn                 = Column(Float,   default=0.0)
    pr_review_coverage         = Column(Float,   default=0.0)
    reopen_rate                = Column(Float,   default=0.0)
    avg_pr_review_time_hours   = Column(Float,   nullable=True)
    avg_issue_cycle_time_hours = Column(Float,   nullable=True)
    review_comments_given      = Column(Integer, default=0)
    review_comments_received   = Column(Integer, default=0)
    developer                  = relationship("Developer", back_populates="daily_metrics")
    __table_args__ = (
        UniqueConstraint("developer_id", "date", name="uq_daily_metric"),
        Index("ix_daily_metric_date", "date"),
    )


class PerformanceScore(Base):
    __tablename__ = "performance_scores"
    id                     = Column(Integer, primary_key=True, autoincrement=True)
    developer_id           = Column(Integer, ForeignKey("developers.id"), nullable=False)
    week_start             = Column(DateTime(timezone=True), nullable=False)
    delivery_score         = Column(Float, default=0.0)
    quality_score          = Column(Float, default=0.0)
    collaboration_score    = Column(Float, default=0.0)
    consistency_score      = Column(Float, default=0.0)
    velocity_trend         = Column(Float, default=0.0)
    overall_score          = Column(Float, default=0.0)
    avg_daily_active_hours = Column(Float, nullable=True)
    weekend_activity_ratio = Column(Float, default=0.0)
    after_hours_ratio      = Column(Float, default=0.0)
    burnout_risk_score     = Column(Float, default=0.0)
    burnout_risk_level     = Column(String(20), default="low")
    computed_at            = Column(DateTime(timezone=True), server_default=func.now())
    developer              = relationship("Developer", back_populates="performance_scores")
    __table_args__ = (
        UniqueConstraint("developer_id", "week_start", name="uq_perf_score_week"),
        Index("ix_perf_score_date", "week_start"),
    )


class BiWeeklyScore(Base):
    """Агрегированный score за двухнедельный период (среднее двух weekly scores)."""
    __tablename__ = "biweekly_scores"
    id                     = Column(Integer, primary_key=True, autoincrement=True)
    developer_id           = Column(Integer, ForeignKey("developers.id"), nullable=False)
    period_start           = Column(DateTime(timezone=True), nullable=False)  # первый день периода
    period_end             = Column(DateTime(timezone=True), nullable=False)  # последний день (не включая)
    delivery_score         = Column(Float, default=0.0)
    quality_score          = Column(Float, default=0.0)
    collaboration_score    = Column(Float, default=0.0)
    consistency_score      = Column(Float, default=0.0)
    velocity_trend         = Column(Float, default=0.0)
    overall_score          = Column(Float, default=0.0)
    burnout_risk_score     = Column(Float, default=0.0)
    burnout_risk_level     = Column(String(20), default="low")
    after_hours_ratio      = Column(Float, default=0.0)
    weekend_activity_ratio = Column(Float, default=0.0)
    weeks_included         = Column(Integer, default=2)   # сколько weekly records усреднено
    delta_overall          = Column(Float, nullable=True) # разница с предыдущим периодом
    computed_at            = Column(DateTime(timezone=True), server_default=func.now())
    developer              = relationship("Developer", back_populates="biweekly_scores")
    __table_args__ = (
        UniqueConstraint("developer_id", "period_start", name="uq_biweekly_period"),
        Index("ix_biweekly_period", "period_start"),
    )


class GitHubIssue(Base):
    """GitHub Issues (не PR) — для отслеживания участия разработчика."""
    __tablename__ = "github_issues"
    id             = Column(Integer,    primary_key=True, autoincrement=True)
    gh_id          = Column(BigInteger, nullable=False)
    repo_full_name = Column(String(512), nullable=False)
    number         = Column(Integer,    nullable=False)
    title          = Column(Text,       nullable=False)
    state          = Column(String(50), nullable=False)
    author_login   = Column(String(255), nullable=True)
    assignee_login = Column(String(255), nullable=True)
    html_url       = Column(Text,       nullable=True)
    created_at     = Column(DateTime(timezone=True), nullable=False)
    updated_at     = Column(DateTime(timezone=True), nullable=True)
    closed_at      = Column(DateTime(timezone=True), nullable=True)
    labels         = Column(JSON, nullable=True)
    comments_count = Column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("repo_full_name", "number", name="uq_gh_issue_repo_number"),
        Index("ix_gh_issue_author",   "author_login"),
        Index("ix_gh_issue_assignee", "assignee_login"),
        Index("ix_gh_issue_date",     "created_at"),
    )


class GitHubIssueComment(Base):
    """Комментарии к GitHub Issues (не PR-ревью)."""
    __tablename__ = "github_issue_comments"
    id             = Column(Integer,    primary_key=True, autoincrement=True)
    gh_id          = Column(BigInteger, unique=True, nullable=False)
    repo_full_name = Column(String(512), nullable=False)
    issue_number   = Column(Integer,    nullable=True)
    author_login   = Column(String(255), nullable=True)
    body           = Column(Text,       nullable=True)
    html_url       = Column(Text,       nullable=True)
    created_at     = Column(DateTime(timezone=True), nullable=False)
    updated_at     = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index("ix_gh_issue_comment_author", "author_login"),
        Index("ix_gh_issue_comment_date",   "created_at"),
    )


class PRGigaChatAssessment(Base):
    """Оценка PR через GigaChat (или заглушку)."""
    __tablename__ = "pr_gigachat_assessments"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    pr_id            = Column(Integer, ForeignKey("github_pull_requests.id"), nullable=False, unique=True)
    quality_score    = Column(Float,  nullable=False)
    complexity_score = Column(Float,  nullable=False)
    quality_label    = Column(String(50), nullable=False)
    complexity_label = Column(String(50), nullable=False)
    quality_reasons  = Column(JSON,   nullable=True)
    complexity_reasons = Column(JSON, nullable=True)
    is_stub          = Column(Integer, default=1)
    ai_summary       = Column(Text, nullable=True)
    assessed_at      = Column(DateTime(timezone=True), server_default=func.now())
    pull_request     = relationship("GitHubPullRequest")
    __table_args__   = (Index("ix_pr_assessment_pr", "pr_id"),)


class OneOnOneMeeting(Base):
    """Записи о 1:1 встречах с вопросами, сгенерированными по risk score."""
    __tablename__ = "one_on_one_meetings"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    developer_id = Column(Integer, ForeignKey("developers.id"), nullable=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    risk_level   = Column(String(20), nullable=False)
    risk_score   = Column(Float,      nullable=False)
    questions    = Column(JSON,       nullable=False)
    notes        = Column(Text,       nullable=True)
    developer    = relationship("Developer")
    __table_args__ = (Index("ix_one_on_one_dev", "developer_id"),)
