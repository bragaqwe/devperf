"""
Metrics engine v2 — новые 7 метрик + attrition risk + 1-on-1 helper.

Принципы:
- Все метрики relative (vs личный baseline), не absolute
- Burnout-сигналы сохранены для модели предсказания
- compute_daily_metrics() не меняется — таймлайн остаётся
- Все функции — чистый Python/numpy, без ML-зависимостей
"""
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

WORK_HOURS_START = 9   # 9:00
WORK_HOURS_END   = 19  # 19:00


# ══════════════════════════════════════════════════════════════════════════════
# DAILY METRICS — не меняем, таймлайн остаётся как есть
# ══════════════════════════════════════════════════════════════════════════════

def compute_daily_metrics(
    developer_id: int,
    target_date: date,
    activities: list[dict],
    jira_issues: list[dict],
    pr_data: list[dict],
) -> dict:
    """
    Агрегирует raw activity events в DailyMetric row.
    Логика не менялась — используется для таймлайна.
    """
    commits   = [a for a in activities if a.get("activity_type") == "commit"]
    prs_open  = [a for a in activities if a.get("activity_type") == "pr_opened"]
    prs_merge = [a for a in activities if a.get("activity_type") == "pr_merged"]
    reviews   = [a for a in activities if a.get("activity_type") == "pr_review"]
    comments  = [a for a in activities if a.get("activity_type") == "pr_comment"]

    lines_added   = sum(a.get("lines_added",   0) for a in commits)
    lines_removed = sum(a.get("lines_removed", 0) for a in commits)
    total_lines   = lines_added + lines_removed
    peak          = max(lines_added, lines_removed, 1)
    code_churn    = round(total_lines / peak, 3)

    resolved = sum(1 for i in jira_issues if i.get("resolved_today"))
    sp       = sum(i.get("story_points", 0) or 0 for i in jira_issues if i.get("resolved_today"))

    review_times  = [p.get("review_time_hours") for p in pr_data if p.get("review_time_hours")]
    cycle_times   = [i.get("cycle_time_hours")  for i in jira_issues if i.get("cycle_time_hours")]
    reopen_rate   = (
        sum(1 for p in pr_data if p.get("reopened")) / max(len(pr_data), 1)
        if pr_data else 0.0
    )
    reviewed_prs  = sum(1 for p in pr_data if p.get("has_review"))
    coverage      = reviewed_prs / max(len(pr_data), 1) if pr_data else 0.0

    return {
        "developer_id":               developer_id,
        "date":                       datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc),
        "commits_count":              len(commits),
        "prs_opened":                 len(prs_open),
        "prs_merged":                 len(prs_merge),
        "reviews_given":              len(reviews),
        "issues_resolved":            resolved,
        "story_points_delivered":     round(sp, 1),
        "lines_added":                lines_added,
        "lines_removed":              lines_removed,
        "code_churn":                 code_churn,
        "pr_review_coverage":         round(coverage, 3),
        "reopen_rate":                round(reopen_rate, 3),
        "avg_pr_review_time_hours":   round(float(np.mean(review_times)), 2) if review_times else None,
        "avg_issue_cycle_time_hours": round(float(np.mean(cycle_times)),  2) if cycle_times else None,
        "review_comments_given":      len(comments),
        "review_comments_received":   sum(a.get("comments_received", 0) for a in activities),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE SCORE — 7 новых метрик
# ══════════════════════════════════════════════════════════════════════════════

def compute_performance_score(
    developer_id:        int,
    week_start:          datetime,
    daily_metrics:       list[dict],   # текущая неделя
    prev_weeks_metrics:  list[list[dict]],  # последние N недель для baseline
    activity_timestamps: list[datetime],
    pr_response_times:   list[float],  # часы от открытия PR до первого ревью
    comment_lengths:     list[int],    # длины комментариев в review
    task_complexities:   list[float],  # story points закрытых задач
    pr_rework_count:     int,          # PR возвращённых на доработку
    pr_total:            int,          # всего PR за неделю
    vacation_periods:    list[dict],   # [{started_at, ended_at}]
) -> dict:
    """
    Считает недельный PerformanceScore с 7 новыми метриками.
    Все метрики relative — считаются vs личный baseline из prev_weeks_metrics.
    """
    if not daily_metrics:
        return _empty_score(developer_id, week_start)

    # Личный baseline из предыдущих недель
    baseline = _compute_baseline(prev_weeks_metrics)

    momentum        = _momentum(daily_metrics, baseline)
    responsiveness  = _responsiveness(pr_response_times, baseline)
    task_velocity   = _task_velocity(daily_metrics, baseline)
    engagement      = _engagement_depth(comment_lengths, task_complexities, baseline)
    code_health     = _code_health(daily_metrics, pr_rework_count, pr_total)
    recovery        = _recovery_pattern(daily_metrics, vacation_periods, activity_timestamps)
    burnout         = _burnout_signals(activity_timestamps, daily_metrics)
    attrition       = _attrition_signals(
        momentum=momentum["momentum"],
        responsiveness_score=responsiveness["responsiveness_score"],
        engagement_depth_score=engagement["engagement_depth_score"],
        burnout_risk_score=burnout["burnout_risk_score"],
        prev_weeks_metrics=prev_weeks_metrics,
    )

    # Сводные score для UI (0–100)
    # Стабильность удалена — метрика меряла паттерн коммитов, а не реальный ритм работы
    delivery_score      = task_velocity["task_velocity_score"]
    quality_score       = code_health["code_health_score"]
    collaboration_score = (
        engagement["engagement_depth_score"] * 0.6
        + responsiveness["responsiveness_score"] * 0.4
    )
    velocity_trend      = momentum["momentum"]  # -1..+1
    overall_score       = round(
        delivery_score      * 0.40
        + quality_score     * 0.30
        + collaboration_score * 0.30,
        2,
    )

    return {
        "developer_id":        developer_id,
        "week_start":          week_start,
        "delivery_score":      round(delivery_score,       2),
        "quality_score":       round(quality_score,        2),
        "collaboration_score": round(collaboration_score,  2),
        "consistency_score":   0.0,   # удалено, колонка сохранена для совместимости с БД
        "velocity_trend":      round(velocity_trend,       3),
        "overall_score":       overall_score,
        **momentum,
        **responsiveness,
        **task_velocity,
        **engagement,
        **code_health,
        **recovery,
        **burnout,
        **attrition,
    }


# ══════════════════════════════════════════════════════════════════════════════
# МЕТРИКА 1: MOMENTUM
# Динамика throughput vs личный baseline
# ══════════════════════════════════════════════════════════════════════════════

def _momentum(daily_metrics: list[dict], baseline: dict) -> dict:
    """
    Momentum = изменение throughput текущей недели vs baseline.
    Throughput = story_points + prs_merged (взвешенно).
    Возвращает значение от -1.0 до +1.0.
      +0.2 = на 20% выше baseline
      -0.3 = на 30% ниже baseline
    """
    sp   = sum(m.get("story_points_delivered", 0) for m in daily_metrics)
    prs  = sum(m.get("prs_merged",             0) for m in daily_metrics)
    curr = sp * 0.6 + prs * 0.4

    base = baseline.get("avg_throughput", 0)
    if base == 0:
        return {"momentum": 0.0}

    delta = (curr - base) / base
    return {"momentum": round(float(np.clip(delta, -1.0, 1.0)), 3)}


# ══════════════════════════════════════════════════════════════════════════════
# МЕТРИКА 2: RESPONSIVENESS
# Время отклика на PR и комментарии
# ══════════════════════════════════════════════════════════════════════════════

def _responsiveness(
    pr_response_times: list[float],   # часы от assign до первого ревью
    baseline: dict,
) -> dict:
    """
    Responsiveness score 0–100.
    Считается как нормализованное время отклика vs личный baseline.
    Быстрее baseline → выше score.
    Абсолютная шкала: ≤2ч = 100, ≥48ч = 0.
    Финальный score = среднее абсолютного и relative.
    """
    if not pr_response_times:
        # Нет данных — нейтральный score, не штрафуем
        return {
            "avg_response_time_hours": None,
            "responsiveness_score":    50.0,
        }

    avg_hours = float(np.mean(pr_response_times))

    # Абсолютный score: ≤2ч = 100, ≥48ч = 0
    abs_score = max(0.0, 100.0 - (avg_hours - 2) * (100 / 46))

    # Relative score: vs личный baseline
    base_rt = baseline.get("avg_response_time_hours")
    if base_rt and base_rt > 0:
        # Быстрее baseline → > 50, медленнее → < 50
        ratio = base_rt / avg_hours  # > 1 если сейчас быстрее
        rel_score = float(np.clip(50 * ratio, 0, 100))
    else:
        rel_score = abs_score

    score = round((abs_score + rel_score) / 2, 2)
    return {
        "avg_response_time_hours": round(avg_hours, 2),
        "responsiveness_score":    score,
    }


# ══════════════════════════════════════════════════════════════════════════════
# МЕТРИКА 3: TASK VELOCITY
# Скорость закрытия задач с поправкой на сложность
# ══════════════════════════════════════════════════════════════════════════════

def _task_velocity(daily_metrics: list[dict], baseline: dict) -> dict:
    """
    Task velocity = (issues_resolved / avg_cycle_time) нормализованное vs baseline.
    Поправка на сложность через avg_issue_cycle_time_hours.
    Score 0–100.
    """
    issues = sum(m.get("issues_resolved",          0)    for m in daily_metrics)
    cycle_times = [
        m["avg_issue_cycle_time_hours"]
        for m in daily_metrics
        if m.get("avg_issue_cycle_time_hours") is not None
    ]

    if not cycle_times or issues == 0:
        return {"task_velocity_score": 50.0}

    avg_ct = float(np.mean(cycle_times))
    # Нормализуем: ≤8ч = 100, ≥96ч = 0
    ct_score = max(0.0, 100.0 - (avg_ct - 8) * (100 / 88))

    # Vs baseline
    base_ct = baseline.get("avg_cycle_time_hours")
    if base_ct and base_ct > 0:
        rel = base_ct / avg_ct
        rel_score = float(np.clip(50 * rel, 0, 100))
        score = (ct_score + rel_score) / 2
    else:
        score = ct_score

    return {"task_velocity_score": round(score, 2)}


# ══════════════════════════════════════════════════════════════════════════════
# МЕТРИКА 4: ENGAGEMENT DEPTH
# Качество вовлечённости: сложность задач + содержательность комментариев
# ══════════════════════════════════════════════════════════════════════════════

def _engagement_depth(
    comment_lengths:   list[int],    # длины review-комментариев в символах
    task_complexities: list[float],  # story points закрытых задач
    baseline: dict,
) -> dict:
    """
    Engagement depth = комбинация:
    - Средняя длина комментариев (прокси качества фидбека)
    - Средняя сложность задач которые берёт (растёт или падает?)

    Падение engagement — один из главных сигналов перед увольнением.
    Score 0–100.
    """
    # Длина комментариев: медиана лучше среднего (устойчива к выбросам)
    if comment_lengths:
        avg_comment = float(np.median(comment_lengths))
        # ≥200 символов = хороший комментарий, ≤20 = LGTM
        comment_score = float(np.clip(avg_comment / 200 * 100, 0, 100))
    else:
        avg_comment   = 0.0
        comment_score = 50.0  # нет данных — нейтрально

    # Сложность задач vs baseline
    if task_complexities:
        avg_complexity = float(np.mean(task_complexities))
        base_complexity = baseline.get("avg_task_complexity", avg_complexity)
        if base_complexity > 0:
            complexity_ratio = avg_complexity / base_complexity
            complexity_score = float(np.clip(complexity_ratio * 50, 0, 100))
        else:
            complexity_score = 50.0
    else:
        avg_complexity   = 0.0
        complexity_score = 50.0

    score = comment_score * 0.5 + complexity_score * 0.5
    return {
        "avg_comment_length":     round(avg_comment,   2),
        "avg_task_complexity":    round(avg_complexity, 2),
        "engagement_depth_score": round(score,          2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# МЕТРИКА 5: CODE HEALTH
# Качество кода: churn + возвраты PR
# ══════════════════════════════════════════════════════════════════════════════

def _code_health(
    daily_metrics:  list[dict],
    pr_rework_count: int,   # PR возвращённых на доработку
    pr_total:        int,   # всего PR
) -> dict:
    """
    Code health = комбинация:
    - Churn ratio: сколько кода переписывается (низкий = лучше)
    - PR rework rate: % PR возвращённых на доработку (низкий = лучше)
    Score 0–100 (100 = здоровый код).
    """
    # Churn: среднее по дням
    churns = [m.get("code_churn", 0) for m in daily_metrics if m.get("code_churn")]
    avg_churn = float(np.mean(churns)) if churns else 1.0
    # churn 1.0 = нет переписывания (ideal), >2.5 = много переписывания
    churn_score = max(0.0, 100.0 - (avg_churn - 1.0) * (100 / 1.5))

    # PR rework rate
    rework_rate = pr_rework_count / max(pr_total, 1) if pr_total > 0 else 0.0
    rework_score = (1 - rework_rate) * 100

    score = churn_score * 0.4 + rework_score * 0.6
    return {
        "code_churn_ratio":   round(avg_churn,   3),
        "pr_rework_rate":     round(rework_rate,  3),
        "code_health_score":  round(score,         2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# МЕТРИКА 6: RHYTHM
# ══════════════════════════════════════════════════════════════════════════════
# МЕТРИКА 7: RECOVERY PATTERN
# История отпусков и восстановление
# ══════════════════════════════════════════════════════════════════════════════

def _recovery_pattern(
    daily_metrics:       list[dict],
    vacation_periods:    list[dict],   # [{started_at: datetime, ended_at: datetime}]
    activity_timestamps: list[datetime],
) -> dict:
    """
    Recovery pattern анализирует:
    1. Сколько дней прошло с последнего отпуска
    2. Как изменился momentum после отпуска (восстановился ли человек)

    Score 0–100:
    - 100 = недавно был в отпуске, хорошо восстановился
    - 50  = нет данных / давно не был
    - 0   = очень давно без отпуска при высокой нагрузке
    """
    now = datetime.now(tz=timezone.utc)

    # Дней с последнего отпуска
    days_since = None
    last_vacation_end = None
    if vacation_periods:
        ended_dates = []
        for v in vacation_periods:
            end = v.get("ended_at")
            if end:
                if isinstance(end, str):
                    end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                ended_dates.append(end)
        if ended_dates:
            last_vacation_end = max(ended_dates)
            days_since = (now - last_vacation_end).days

    # Momentum после отпуска — смотрим текущую неделю
    # (сравнение с pre-vacation делается на уровне routes через GradePromotionReport)
    post_vacation_momentum = None

    # Score
    if days_since is None:
        # Нет данных об отпусках — нейтрально
        recovery_score = 50.0
    elif days_since <= 14:
        # Недавно вернулся — хорошо
        recovery_score = 90.0
    elif days_since <= 60:
        recovery_score = 70.0
    elif days_since <= 120:
        recovery_score = 50.0
    elif days_since <= 180:
        recovery_score = 30.0
    else:
        # Больше полугода без отпуска — тревожный сигнал
        recovery_score = 10.0

    return {
        "days_since_last_vacation": days_since,
        "post_vacation_momentum":   post_vacation_momentum,
        "recovery_score":           round(recovery_score, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# BURNOUT SIGNALS — сохранены для модели предсказания
# ══════════════════════════════════════════════════════════════════════════════

def _burnout_signals(
    timestamps:    list[datetime],
    daily_metrics: list[dict],
) -> dict:
    """
    Burnout risk из паттернов активности:
    - After-hours ratio
    - Weekend activity ratio
    - Overload (слишком много часов)
    - Consecutive streak (без выходных)
    """
    if not timestamps:
        return {
            "avg_daily_active_hours": None,
            "weekend_activity_ratio": 0.0,
            "after_hours_ratio":      0.0,
            "burnout_risk_score":     0.0,
            "burnout_risk_level":     "low",
        }

    total      = len(timestamps)
    after_hrs  = sum(1 for t in timestamps if t.hour < WORK_HOURS_START or t.hour >= WORK_HOURS_END)
    weekends   = sum(1 for t in timestamps if t.weekday() >= 5)

    after_hours_ratio = after_hrs  / total
    weekend_ratio     = weekends   / total

    # Активные часы в день
    by_day: dict[date, list[datetime]] = {}
    for t in sorted(timestamps):
        by_day.setdefault(t.date(), []).append(t)

    span_hours = [
        (max(ts) - min(ts)).total_seconds() / 3600
        for ts in by_day.values()
    ]
    avg_daily_hours = float(np.mean(span_hours)) if span_hours else None

    overload_signal = 0.0
    if avg_daily_hours and avg_daily_hours > 10:
        overload_signal = min((avg_daily_hours - 10) / 4, 1.0)

    # Максимальная серия подряд без выходных
    sorted_dates = sorted(by_day.keys())
    max_streak = cur = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 1
    streak_signal = min((max_streak - 5) / 9, 1.0) if max_streak > 5 else 0.0

    burnout_score = round(float(min(
        after_hours_ratio * 0.35
        + weekend_ratio   * 0.25
        + overload_signal * 0.25
        + streak_signal   * 0.15,
        1.0
    )), 3)

    level = "low"
    if burnout_score >= 0.65:
        level = "high"
    elif burnout_score >= 0.35:
        level = "medium"

    return {
        "avg_daily_active_hours": round(avg_daily_hours, 2) if avg_daily_hours else None,
        "weekend_activity_ratio": round(weekend_ratio,    3),
        "after_hours_ratio":      round(after_hours_ratio, 3),
        "burnout_risk_score":     burnout_score,
        "burnout_risk_level":     level,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ATTRITION SIGNALS — предсказание увольнения
# ══════════════════════════════════════════════════════════════════════════════

def _attrition_signals(
    momentum:              float,
    responsiveness_score:  float,
    engagement_depth_score: float,
    burnout_risk_score:    float,
    prev_weeks_metrics:    list[list[dict]],
) -> dict:
    """
    Attrition risk — детерминированная модель на основе сигналов.

    Сигналы (каждый 0–1):
    1. momentum_decline:    momentum падает vs baseline
    2. engagement_drop:     engagement_depth упал на 40%+ vs baseline
    3. responsiveness_drop: responsiveness упала вдвое
    4. burnout_combo:       высокий burnout
    5. isolation:           резкое снижение reviews_given
    """
    signal_texts = []

    # 1. Momentum decline
    momentum_signal = 0.0
    if momentum < -0.2:
        momentum_signal = min(abs(momentum), 1.0)
        signal_texts.append(f"Momentum снизился на {abs(momentum)*100:.0f}% vs baseline")

    # 2. Engagement drop
    engagement_signal = 0.0
    if engagement_depth_score < 40:
        engagement_signal = (40 - engagement_depth_score) / 40
        signal_texts.append(f"Engagement depth низкий: {engagement_depth_score:.0f}/100")

    # 3. Responsiveness drop
    responsiveness_signal = 0.0
    if responsiveness_score < 35:
        responsiveness_signal = (35 - responsiveness_score) / 35
        signal_texts.append(f"Responsiveness упала: {responsiveness_score:.0f}/100")

    # 4. Burnout (без rhythm — удалена)
    burnout_combo = 0.0
    if burnout_risk_score >= 0.65:
        burnout_combo = burnout_risk_score * 0.8
        signal_texts.append(f"Высокий риск выгорания: {burnout_risk_score:.0%}")

    # 5. Isolation: снижение reviews_given
    isolation_signal = 0.0
    if len(prev_weeks_metrics) >= 3:
        recent_reviews = [
            sum(m.get("reviews_given", 0) for m in week)
            for week in prev_weeks_metrics[-3:]
        ]
        if recent_reviews and max(recent_reviews) > 0:
            decline = (max(recent_reviews) - min(recent_reviews)) / max(recent_reviews)
            if decline > 0.5:
                isolation_signal = decline * 0.7
                signal_texts.append(f"Количество ревью упало на {decline*100:.0f}% за 3 недели")

    # Взвешенный итог
    attrition_score = round(float(min(
        momentum_signal      * 0.30
        + engagement_signal  * 0.25
        + responsiveness_signal * 0.20
        + burnout_combo      * 0.15
        + isolation_signal   * 0.10,
        1.0
    )), 3)

    level = "low"
    if attrition_score >= 0.60:
        level = "high"
    elif attrition_score >= 0.30:
        level = "medium"

    return {
        "attrition_risk_score": attrition_score,
        "attrition_risk_level": level,
        "_attrition_signals":   signal_texts,   # временное поле, используется в routes
    }


# ══════════════════════════════════════════════════════════════════════════════
# BASELINE — личный baseline из истории
# ══════════════════════════════════════════════════════════════════════════════

def _compute_baseline(prev_weeks: list[list[dict]]) -> dict:
    """
    Считает личный baseline разработчика из последних N недель.
    Используется для нормализации всех relative метрик.
    """
    if not prev_weeks:
        return {
            "avg_throughput":          0,
            "avg_response_time_hours": None,
            "avg_cycle_time_hours":    None,
            "avg_task_complexity":     3.0,
        }

    all_metrics = [m for week in prev_weeks for m in week]

    # Throughput = SP * 0.6 + PRs * 0.4 (по неделям)
    weekly_throughputs = [
        sum(m.get("story_points_delivered", 0) for m in week) * 0.6
        + sum(m.get("prs_merged", 0) for m in week) * 0.4
        for week in prev_weeks
    ]
    avg_throughput = float(np.mean(weekly_throughputs)) if weekly_throughputs else 0

    # Cycle time
    cycle_times = [
        m["avg_issue_cycle_time_hours"]
        for m in all_metrics
        if m.get("avg_issue_cycle_time_hours") is not None
    ]

    # PR review time (хранится в DailyMetric как avg_pr_review_time_hours)
    review_times = [
        m["avg_pr_review_time_hours"]
        for m in all_metrics
        if m.get("avg_pr_review_time_hours") is not None
    ]

    return {
        "avg_throughput":          round(avg_throughput, 2),
        "avg_response_time_hours": round(float(np.mean(review_times)),  2) if review_times else None,
        "avg_cycle_time_hours":    round(float(np.mean(cycle_times)),   2) if cycle_times  else None,
        "avg_task_complexity":     3.0,  # обновляется когда есть story points история
    }


# ══════════════════════════════════════════════════════════════════════════════
# 1-ON-1 HELPER
# ══════════════════════════════════════════════════════════════════════════════

def generate_one_on_one_report(
    developer_id:   int,
    developer_name: str,
    grade:          Optional[str],
    current_score:  dict,
    prev_score:     Optional[dict],
    attrition_signals: list[str],
) -> dict:
    """
    Генерирует помощник для подготовки к 1-1.
    Анализирует изменения за последние 2 недели и формирует:
    - changes: что изменилось (с категорией и вопросом для тимлида)
    - highlights: позитивные моменты
    - overall_mood: общий статус
    - summary: 1-2 предложения
    """
    changes    = []
    highlights = []

    if prev_score:
        # Momentum
        mom_delta = current_score.get("momentum", 0) - prev_score.get("momentum", 0)
        if mom_delta < -0.2:
            changes.append({
                "category": "risk",
                "signal":   f"Momentum упал на {abs(mom_delta)*100:.0f}% за неделю",
                "question": "Есть ли что-то что мешает двигаться с обычной скоростью?",
            })
        elif mom_delta > 0.2:
            highlights.append(f"Momentum вырос на {mom_delta*100:.0f}% — отличная неделя по скорости")

        # Responsiveness
        resp_delta = (
            current_score.get("responsiveness_score", 50)
            - prev_score.get("responsiveness_score", 50)
        )
        if resp_delta < -20:
            changes.append({
                "category": "workload",
                "signal":   "Время ответа на PR и комментарии значительно выросло",
                "question": "Чувствуешь ли ты что времени на ревью не хватает? Что можно убрать?",
            })

        # Engagement depth
        eng_delta = (
            current_score.get("engagement_depth_score", 50)
            - prev_score.get("engagement_depth_score", 50)
        )
        if eng_delta < -15:
            changes.append({
                "category": "risk",
                "signal":   "Глубина вовлечённости снизилась: комментарии короче, задачи проще",
                "question": "Как тебе текущие задачи? Есть что-то что реально цепляет?",
            })
        elif eng_delta > 15:
            highlights.append("Качество ревью и сложность задач выросли — заметный прогресс")

        # Recovery
        days_since = current_score.get("days_since_last_vacation")
        if days_since and days_since > 120:
            changes.append({
                "category": "workload",
                "signal":   f"Последний отпуск был {days_since} дней назад",
                "question": "Планируешь ли ты взять отпуск в ближайшее время?",
            })

    # Attrition сигналы → вопросы для 1-1
    for signal in attrition_signals:
        changes.append({
            "category": "risk",
            "signal":   signal,
            "question": "Есть ли что-то что тебя сейчас демотивирует или беспокоит?",
        })

    # Code health highlight
    if current_score.get("code_health_score", 0) > 85:
        highlights.append("Отличное качество кода на этой неделе — низкий churn и мало возвратов")

    # Burnout
    burnout_level = current_score.get("burnout_risk_level", "low")
    if burnout_level == "high":
        changes.append({
            "category": "risk",
            "signal":   "Высокий burnout: много работы в нерабочее время и выходные",
            "question": "Как ты себя чувствуешь в целом? Удаётся ли отдыхать?",
        })
    elif burnout_level == "medium":
        changes.append({
            "category": "workload",
            "signal":   "Умеренный burnout: есть активность вне рабочего времени",
            "question": "Как баланс работы и отдыха на этой неделе?",
        })

    # Общий статус
    attrition_level = current_score.get("attrition_risk_level", "low")
    if attrition_level == "high" or burnout_level == "high":
        overall_mood = "urgent"
        summary = (
            f"{developer_name} показывает тревожные сигналы — "
            "стоит провести глубокий разговор о состоянии и мотивации."
        )
    elif attrition_level == "medium" or burnout_level == "medium" or len(changes) >= 2:
        overall_mood = "watch"
        summary = (
            f"У {developer_name} есть несколько изменений которые стоит обсудить. "
            "Хороший момент для проверки нагрузки и мотивации."
        )
    else:
        overall_mood = "healthy"
        summary = (
            f"{developer_name} в хорошем состоянии. "
            "1-1 — отличный момент обсудить рост и следующие цели."
        )

    return {
        "developer_id":   developer_id,
        "developer_name": developer_name,
        "grade":          grade,
        "generated_at":   datetime.now(tz=timezone.utc).isoformat(),
        "changes":        changes,
        "highlights":     highlights,
        "overall_mood":   overall_mood,
        "summary":        summary,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GRADE PROMOTION REPORT
# ══════════════════════════════════════════════════════════════════════════════

def compute_grade_promotion_report(
    developer_id:   int,
    developer_name: str,
    old_grade:      str,
    new_grade:      str,
    promoted_at:    datetime,
    before_scores:  list[dict],   # PerformanceScore за 4 нед ДО
    after_scores:   list[dict],   # PerformanceScore за 4 нед ПОСЛЕ (может быть пустым)
) -> dict:
    """
    Отчёт об адаптации после повышения грейда.
    Сравнивает ключевые метрики до и после события.
    """
    def avg_metrics(scores: list[dict]) -> dict:
        if not scores:
            return {}
        keys = [
            "momentum", "responsiveness_score", "task_velocity_score",
            "engagement_depth_score", "code_health_score",
            "burnout_risk_score",
        ]
        return {
            k: round(float(np.mean([s.get(k, 0) for s in scores])), 2)
            for k in keys
        }

    before = avg_metrics(before_scores)
    after  = avg_metrics(after_scores) if after_scores else None

    # Статус адаптации
    if not after:
        status = "adapting"
        note   = "Прошло недостаточно времени для оценки адаптации"
    else:
        # Смотрим на ключевые метрики: momentum + engagement
        mom_change = after.get("momentum", 0) - before.get("momentum", 0)
        eng_change = (
            after.get("engagement_depth_score", 50)
            - before.get("engagement_depth_score", 50)
        )
        if mom_change > 0.05 and eng_change > 5:
            status = "thriving"
            note   = "Отличная адаптация — метрики выросли после повышения"
        elif mom_change < -0.15 or eng_change < -15:
            status = "struggling"
            note   = "Сложная адаптация — стоит обсудить ожидания и поддержку"
        else:
            status = "adapting"
            note   = "Идёт нормальная адаптация к новому грейду"

    return {
        "developer_id":      developer_id,
        "developer_name":    developer_name,
        "old_grade":         old_grade,
        "new_grade":         new_grade,
        "promoted_at":       promoted_at.isoformat(),
        "before":            before,
        "after":             after,
        "adaptation_status": status,
        "adaptation_note":   note,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TREND ANALYSIS — обновлён под новые метрики
# ══════════════════════════════════════════════════════════════════════════════

def compute_trend(scores: list[float], window: int = 4) -> dict:
    """
    Линейная регрессия по последним N неделям.
    Возвращает slope, R² и direction.
    """
    if len(scores) < 2:
        return {"slope": 0.0, "r2": 0.0, "direction": "stable"}

    y = np.array(scores[-window:], dtype=float)
    x = np.arange(len(y), dtype=float)

    A      = np.vstack([x, np.ones(len(x))]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]

    y_hat  = slope * x + intercept
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2     = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    direction = "stable"
    if abs(slope) > 1.0:
        direction = "improving" if slope > 0 else "declining"

    return {
        "slope":     round(float(slope), 4),
        "r2":        round(r2,           4),
        "direction": direction,
    }


# ══════════════════════════════════════════════════════════════════════════════
# EMPTY SCORE
# ══════════════════════════════════════════════════════════════════════════════

def _empty_score(developer_id: int, week_start: datetime) -> dict:
    return {
        "developer_id":             developer_id,
        "week_start":               week_start,
        "momentum":                 0.0,
        "avg_response_time_hours":  None,
        "responsiveness_score":     50.0,
        "task_velocity_score":      50.0,
        "avg_comment_length":       0.0,
        "avg_task_complexity":      0.0,
        "engagement_depth_score":   50.0,
        "code_churn_ratio":         1.0,
        "pr_rework_rate":           0.0,
        "code_health_score":        50.0,
        "days_since_last_vacation": None,
        "post_vacation_momentum":   None,
        "recovery_score":           50.0,
        "avg_daily_active_hours":   None,
        "weekend_activity_ratio":   0.0,
        "after_hours_ratio":        0.0,
        "burnout_risk_score":       0.0,
        "burnout_risk_level":       "low",
        "attrition_risk_score":     0.0,
        "attrition_risk_level":     "low",
        "_attrition_signals":       [],
    }