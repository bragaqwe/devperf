"""
Anomaly detection для недельной активности разработчика.

Использует Isolation Forest на сырых агрегатах DailyMetric за неделю —
коммиты, PR, ревью, строки кода, SP, комментарии, активные дни.

Принцип: не используем вычисленные score (они уже сглажены формулами),
а берём реальную активность и ищем недели, нетипичные для конкретного
разработчика.

Минимум данных: 5 недель истории.
"""
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Сырые признаки из DailyMetric, агрегированные за неделю
FEATURES: list[str] = [
    "commits_total",           # sum(commits_count)
    "prs_opened",              # sum(prs_opened)
    "prs_merged",              # sum(prs_merged)
    "reviews_given",           # sum(reviews_given)
    "issues_resolved",         # sum(issues_resolved)
    "story_points",            # sum(story_points_delivered)
    "lines_added",             # sum(lines_added)
    "lines_removed",           # sum(lines_removed)
    "review_comments_given",   # sum(review_comments_given)
    "active_days",             # кол-во дней с хоть какой-то активностью
    "avg_churn",               # mean(code_churn) — только по активным дням
]

FEATURE_LABELS: dict[str, str] = {
    "commits_total":         "Коммиты",
    "prs_opened":            "Открытые PR",
    "prs_merged":            "Влитые PR",
    "reviews_given":         "Ревью",
    "issues_resolved":       "Закрытые задачи",
    "story_points":          "Story Points",
    "lines_added":           "Строки добавлено",
    "lines_removed":         "Строки удалено",
    "review_comments_given": "Комментарии в ревью",
    "active_days":           "Активных дней",
    "avg_churn":             "Code churn",
}

MIN_WEEKS = 5          # минимум недель для запуска детектора
_CONTAMINATION = 0.12  # ~12% недель считаем потенциально аномальными


def build_weekly_features(daily_metrics: list[dict]) -> dict:
    """
    Принимает список записей DailyMetric за одну неделю.
    Возвращает dict с агрегированными признаками для Isolation Forest.
    """
    if not daily_metrics:
        return {f: 0.0 for f in FEATURES}

    active = [d for d in daily_metrics if (
        d.get("commits_count", 0) or 0) +
        (d.get("prs_opened", 0) or 0) +
        (d.get("prs_merged", 0) or 0) +
        (d.get("reviews_given", 0) or 0) +
        (d.get("issues_resolved", 0) or 0) > 0
    ]

    churn_vals = [d.get("code_churn") or 0.0 for d in active if d.get("code_churn") is not None]

    return {
        "commits_total":         float(sum(d.get("commits_count", 0) or 0 for d in daily_metrics)),
        "prs_opened":            float(sum(d.get("prs_opened", 0) or 0 for d in daily_metrics)),
        "prs_merged":            float(sum(d.get("prs_merged", 0) or 0 for d in daily_metrics)),
        "reviews_given":         float(sum(d.get("reviews_given", 0) or 0 for d in daily_metrics)),
        "issues_resolved":       float(sum(d.get("issues_resolved", 0) or 0 for d in daily_metrics)),
        "story_points":          float(sum(d.get("story_points_delivered", 0) or 0 for d in daily_metrics)),
        "lines_added":           float(sum(d.get("lines_added", 0) or 0 for d in daily_metrics)),
        "lines_removed":         float(sum(d.get("lines_removed", 0) or 0 for d in daily_metrics)),
        "review_comments_given": float(sum(d.get("review_comments_given", 0) or 0 for d in daily_metrics)),
        "active_days":           float(len(active)),
        "avg_churn":             float(sum(churn_vals) / len(churn_vals)) if churn_vals else 0.0,
    }


def detect_weekly_anomalies(weeks: list[dict]) -> list[dict]:
    """
    Принимает список dict'ов вида:
        {"week_key": ..., **build_weekly_features(...)}

    Возвращает тот же список с добавленными полями:
        week_anomaly_score, week_is_anomaly, week_anomaly_features

    Если данных недостаточно — нейтральные значения.
    """
    if len(weeks) < MIN_WEEKS:
        return [
            {**w, "week_anomaly_score": None,
             "week_is_anomaly": False, "week_anomaly_features": []}
            for w in weeks
        ]

    try:
        return _run(weeks)
    except Exception as exc:
        logger.warning("Isolation Forest (weekly) failed: %s", exc)
        return [
            {**w, "week_anomaly_score": None,
             "week_is_anomaly": False, "week_anomaly_features": []}
            for w in weeks
        ]


def _run(weeks: list[dict]) -> list[dict]:
    from sklearn.ensemble import IsolationForest

    X = np.array(
        [[float(w.get(f) or 0) for f in FEATURES] for w in weeks],
        dtype=np.float64,
    )

    contamination = min(_CONTAMINATION, max(0.05, 1.0 / len(weeks)))

    clf = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        max_samples="auto",
        random_state=42,
    )
    clf.fit(X)

    raw_scores  = clf.decision_function(X)   # меньше = аномальнее
    predictions = clf.predict(X)             # -1 = аномалия

    s_min, s_max = raw_scores.min(), raw_scores.max()
    normalized = (
        1.0 - (raw_scores - s_min) / (s_max - s_min)
        if s_max > s_min else np.zeros(len(raw_scores))
    )

    means = X.mean(axis=0)
    stds  = X.std(axis=0) + 1e-9

    result = []
    for i, w in enumerate(weeks):
        is_anomaly = bool(predictions[i] == -1)

        anomaly_features: list[dict[str, Any]] = []
        if is_anomaly:
            z = np.abs((X[i] - means) / stds)
            top_idx = np.argsort(z)[::-1][:3]
            for idx in top_idx:
                if z[idx] > 1.0:
                    fname = FEATURES[idx]
                    val   = float(X[i][idx])
                    mean  = float(means[idx])
                    anomaly_features.append({
                        "feature":   fname,
                        "label":     FEATURE_LABELS[fname],
                        "direction": "выше нормы" if val > mean else "ниже нормы",
                        "deviation": round(float(z[idx]), 2),
                        "value":     round(val, 2),
                        "mean":      round(mean, 2),
                    })

        result.append({
            **w,
            "week_anomaly_score":    round(float(normalized[i]), 3),
            "week_is_anomaly":       is_anomaly,
            "week_anomaly_features": anomaly_features,
        })

    return result


# ── BiWeekly-уровень ───────────────────────────────────────────────────────────

def biweekly_is_anomaly(week1_anomaly: bool, week2_anomaly: bool) -> bool:
    """Период аномальный если хотя бы одна из двух недель аномальная."""
    return week1_anomaly or week2_anomaly
