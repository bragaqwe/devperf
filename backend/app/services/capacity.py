"""
Capacity Analysis — анализ текущей нагрузки разработчика и запаса.

Нагрузка считается через адаптивные веса (z-score):
  Для каждой метрики (commits, PRs, reviews, SP, lines) вычисляется
  среднее и стандартное отклонение по всей истории разработчика.
  Нагрузка недели = сумма z-score по каждой метрике.

  Это значит «много коммитов» = высокая нагрузка только для тех,
  у кого обычно их мало. Веса не захардкожены — они выводятся из данных.

  Итоговая нагрузка нормализуется 0–100:
    0   = самая спокойная неделя в истории
    100 = самая загруженная неделя в истории
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import math


MIN_WEEKS = 4   # минимум для анализа

# Метрики, участвующие в расчёте нагрузки
_METRIC_GETTERS = [
    ("commits",      lambda w: float(w.commits)),
    ("prs_opened",   lambda w: float(w.prs)),
    ("reviews",      lambda w: float(w.reviews)),
    ("story_points", lambda w: w.story_points),
    ("lines_k",      lambda w: w.lines_added / 1000.0),
]


@dataclass
class WeekLoad:
    week_start:   str           # ISO date строка
    commits:      int  = 0
    prs:          int  = 0
    reviews:      int  = 0
    story_points: float = 0.0
    lines_added:  int  = 0
    quality:      float = 0.0   # quality_score из PerformanceScore
    burnout:      float = 0.0   # burnout_risk_score
    after_hours:  float = 0.0
    weekend:      float = 0.0
    # заполняется внутри analyze_capacity
    load_raw:     float = 0.0   # сумма z-score (может быть отрицательной)
    load_pct:     float = 0.0   # нормализованная 0–100


@dataclass
class WipInfo:
    """Текущий портфель открытых задач из Jira."""
    task_count:   int   = 0
    total_sp:     float = 0.0
    avg_weekly_sp: float = 0.0   # среднее SP/неделю из истории (для сравнения)
    overloaded:   bool  = False  # WIP > 2× средненедельного SP


@dataclass
class SprintScenario:
    """Прогноз для одного сценария нагрузки."""
    label:             str    # «+20% задач», «+40% задач»
    load_pct:          float  # ожидаемая нагрузка
    predicted_quality: float  # прогноз quality_score
    risk:              str    # low / medium / high


@dataclass
class CapacityResult:
    current_load_pct:        float
    current_load_level:      str     # low / medium / high / overload
    # Эффективность
    efficiency_index:        float   # 0-100, quality/load нормализованный
    efficiency_level:        str     # low / medium / high
    efficiency_delta:        float   # отклонение от своей регрессионной линии
    # Потолок и резерв
    peak_sustainable_pct:    float
    headroom_pct:            float
    can_take_more:           bool
    # Качество под нагрузкой
    quality_sensitivity:     float
    high_load_quality_avg:   float
    normal_load_quality_avg: float
    already_overworked:      bool
    wip:                     WipInfo
    # Прогноз на следующий спринт
    sprint_scenarios:        list[SprintScenario]
    recommendation:          str
    confidence:              str
    weeks_analyzed:          int
    weekly: list[dict] = field(default_factory=list)
    top_load_drivers: list[dict] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────

def _mean_std(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    if n == 0:
        return 0.0, 0.0
    m = sum(vals) / n
    variance = sum((v - m) ** 2 for v in vals) / n
    return m, math.sqrt(variance)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx, sx = _mean_std(xs)
    my, sy = _mean_std(ys)
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n * sx * sy)


def _load_level(pct: float) -> str:
    if pct >= 90: return "overload"
    if pct >= 70: return "high"
    if pct >= 40: return "medium"
    return "low"


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Возвращает (slope, intercept) для y = slope*x + intercept."""
    n = len(xs)
    if n < 2:
        return 0.0, sum(ys) / max(n, 1)
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom != 0 else 0.0
    intercept = my - slope * mx
    return slope, intercept


def _efficiency_level(idx: float) -> str:
    if idx >= 70: return "high"
    if idx >= 45: return "medium"
    return "low"


def _scenario_risk(predicted_quality: float, avg_quality: float) -> str:
    drop = avg_quality - predicted_quality
    if drop >= 15: return "high"
    if drop >= 7:  return "medium"
    return "low"


def _compute_adaptive_loads(weeks: list[WeekLoad]) -> list[dict]:
    """
    Вычисляет load_raw (сумма z-score) и load_pct (0-100) для каждой недели.
    Возвращает список dict с вкладом каждой метрики — для объяснения.
    """
    n = len(weeks)
    metric_stats: dict[str, tuple[float, float]] = {}
    metric_contributions: list[dict] = [{} for _ in range(n)]

    z_sums = [0.0] * n

    for name, getter in _METRIC_GETTERS:
        vals = [getter(w) for w in weeks]
        mean, std = _mean_std(vals)
        metric_stats[name] = (mean, std)

        for i, (w, v) in enumerate(zip(weeks, vals)):
            z = (v - mean) / std if std > 0 else 0.0
            z_sums[i] += z
            metric_contributions[i][name] = round(z, 3)

    # Устанавливаем load_raw
    for w, z in zip(weeks, z_sums):
        w.load_raw = z

    # Нормализация 0–100
    min_z = min(z_sums)
    max_z = max(z_sums)
    rng   = max_z - min_z
    for w in weeks:
        w.load_pct = round((w.load_raw - min_z) / rng * 100, 1) if rng > 0 else 50.0

    return metric_contributions


def analyze_capacity(
    weeks: list[WeekLoad],
    wip_task_count: int = 0,
    wip_sp: float = 0.0,
) -> Optional[CapacityResult]:
    if len(weeks) < MIN_WEEKS:
        return None

    weeks_sorted = sorted(weeks, key=lambda w: w.week_start)

    # ── Адаптивная нагрузка ───────────────────────────────────────────────────
    metric_contribs = _compute_adaptive_loads(weeks_sorted)

    current      = weeks_sorted[-1]
    current_idx  = len(weeks_sorted) - 1

    # ── Объяснение: топ-3 драйвера нагрузки текущей недели ───────────────────
    METRIC_LABELS = {
        "commits":      "Коммиты",
        "prs_opened":   "Открытые PR",
        "reviews":      "Ревью",
        "story_points": "Story Points",
        "lines_k":      "Строки кода (тыс.)",
    }
    cur_contribs = metric_contribs[current_idx]
    top_load_drivers = sorted(
        [
            {"metric": METRIC_LABELS.get(k, k), "z_score": v,
             "direction": "выше нормы" if v > 0 else "ниже нормы"}
            for k, v in cur_contribs.items()
        ],
        key=lambda x: abs(x["z_score"]),
        reverse=True,
    )[:3]

    # ── Устойчивый потолок ────────────────────────────────────────────────────
    avg_quality       = sum(w.quality for w in weeks_sorted) / len(weeks_sorted)
    quality_threshold = max(avg_quality * 0.75, 35.0)

    sustainable = [
        w for w in weeks_sorted
        if w.quality >= quality_threshold and w.burnout < 0.65
    ]
    if sustainable:
        peak_sustainable_pct = max(w.load_pct for w in sustainable)
    else:
        sorted_loads = sorted(w.load_pct for w in weeks_sorted)
        peak_sustainable_pct = sorted_loads[len(sorted_loads) // 2]

    # ── Headroom ──────────────────────────────────────────────────────────────
    headroom_pct  = round(peak_sustainable_pct - current.load_pct, 1)
    can_take_more = headroom_pct >= 10

    # ── Корреляция нагрузка ↔ качество + линейная регрессия ──────────────────
    loads     = [w.load_pct for w in weeks_sorted]
    qualities = [w.quality  for w in weeks_sorted]
    quality_sensitivity = round(_pearson(loads, qualities), 3)

    slope, intercept = _linear_regression(loads, qualities)

    # ── Индекс эффективности ─────────────────────────────────────────────────
    # Насколько разработчик работает ЛУЧШЕ или ХУЖЕ своей регрессионной линии.
    # efficiency_delta = actual_quality - predicted_quality_at_this_load
    # Нормализуем delta в 0-100 (50 = ровно по линии, >50 = лучше нормы)
    deltas = [
        q - (slope * l + intercept)
        for l, q in zip(loads, qualities)
    ]
    delta_std = math.sqrt(sum(d ** 2 for d in deltas) / len(deltas)) if deltas else 1.0
    current_delta = deltas[-1] if deltas else 0.0

    # efficiency_index: 50 = работает ровно по своей норме
    efficiency_index = round(50 + (current_delta / max(delta_std, 1.0)) * 15, 1)
    efficiency_index = max(0.0, min(100.0, efficiency_index))

    # ── Прогноз для следующего спринта ────────────────────────────────────────
    avg_quality = sum(qualities) / len(qualities)
    scenarios: list[SprintScenario] = []
    for label, delta_load in [
        ("Текущая нагрузка",  0),
        ("+20% задач",       20),
        ("+40% задач",       40),
        ("+60% задач",       60),
    ]:
        # Намеренно НЕ ограничиваем 100 — прогноз за пределом исторического пика
        future_load = current.load_pct + delta_load
        pred_quality = slope * future_load + intercept
        pred_quality = max(0.0, min(100.0, pred_quality))
        scenarios.append(SprintScenario(
            label             = label,
            load_pct          = round(future_load, 1),
            predicted_quality = round(pred_quality, 1),
            risk              = _scenario_risk(pred_quality, avg_quality),
        ))

    # ── Качество при высокой vs обычной нагрузке ──────────────────────────────
    sorted_loads_vals = sorted(loads)
    load_75p    = sorted_loads_vals[max(0, int(len(loads) * 0.75) - 1)]
    high_weeks  = [w for w in weeks_sorted if w.load_pct >= load_75p]
    normal_weeks= [w for w in weeks_sorted if w.load_pct <  load_75p]

    def _avg_q(ws): return round(sum(w.quality for w in ws) / len(ws), 1) if ws else 0.0
    high_load_quality_avg   = _avg_q(high_weeks)
    normal_load_quality_avg = _avg_q(normal_weeks)

    # ── Burnout прямо сейчас ──────────────────────────────────────────────────
    already_overworked = (
        current.after_hours > 0.25
        or current.weekend   > 0.15
        or current.burnout  >= 0.65
    )

    # ── WIP: открытые задачи Jira ─────────────────────────────────────────────
    avg_weekly_sp = sum(w.story_points for w in weeks_sorted) / len(weeks_sorted)
    wip_overloaded = wip_sp > avg_weekly_sp * 2 if avg_weekly_sp > 0 else False
    wip = WipInfo(
        task_count    = wip_task_count,
        total_sp      = round(wip_sp, 1),
        avg_weekly_sp = round(avg_weekly_sp, 1),
        overloaded    = wip_overloaded,
    )
    # Если WIP большой — корректируем headroom и can_take_more
    if wip_overloaded:
        can_take_more = False

    # ── Рекомендация ──────────────────────────────────────────────────────────
    if already_overworked:
        recommendation = (
            "⚠️ Разработчик уже работает сверхурочно (вечера / выходные). "
            "Добавление задач несёт высокий риск выгорания вне зависимости от запаса по нагрузке."
        )
    elif headroom_pct >= 30:
        recommendation = (
            f"Хороший запас — {headroom_pct:.0f}% до исторического пика устойчивой нагрузки. "
            "Можно добавить задачи в следующий спринт без риска для качества."
        )
    elif headroom_pct >= 10:
        recommendation = (
            f"Умеренный запас ({headroom_pct:.0f}%). Небольшое увеличение нагрузки допустимо, "
            "но стоит отслеживать качество в ходе спринта."
        )
    elif headroom_pct >= 0:
        recommendation = (
            f"Нагрузка близка к устойчивому максимуму (запас {headroom_pct:.0f}%). "
            "Добавление задач скорее всего снизит качество или увеличит цикл-тайм."
        )
    else:
        recommendation = (
            f"Нагрузка уже превышает исторический устойчивый максимум на {abs(headroom_pct):.0f}%. "
            "Высокий риск снижения качества или затягивания задач."
        )

    if quality_sensitivity < -0.4:
        recommendation += (
            " Качество заметно снижается при высокой нагрузке — "
            "этот разработчик чувствителен к перегрузу."
        )

    if wip_overloaded:
        recommendation += (
            f" ⚠️ В Jira сейчас {wip_task_count} открытых задач "
            f"({wip_sp:.0f} SP) — это {wip_sp / avg_weekly_sp:.1f}× больше "
            f"обычного недельного темпа ({avg_weekly_sp:.0f} SP). "
            f"Портфель уже перегружен."
        )
    elif wip_task_count > 0:
        recommendation += (
            f" В Jira {wip_task_count} открытых задач ({wip_sp:.0f} SP) — "
            f"в пределах нормы (≈{avg_weekly_sp:.0f} SP/нед.)."
        )

    # ── Уверенность ──────────────────────────────────────────────────────────
    n = len(weeks_sorted)
    confidence = "high" if n >= 10 else "medium" if n >= 6 else "low"

    # ── Недельный breakdown для графика ──────────────────────────────────────
    weekly = [
        {
            "week":     w.week_start[:10],
            "load_pct": w.load_pct,
            "quality":  round(w.quality, 1),
            "burnout":  round(w.burnout, 3),
            "commits":  w.commits,
            "prs":      w.prs,
            "reviews":  w.reviews,
            "sp":       round(w.story_points, 1),
        }
        for w in weeks_sorted
    ]

    return CapacityResult(
        current_load_pct        = round(current.load_pct, 1),
        current_load_level      = _load_level(current.load_pct),
        efficiency_index        = efficiency_index,
        efficiency_level        = _efficiency_level(efficiency_index),
        efficiency_delta        = round(current_delta, 1),
        peak_sustainable_pct    = round(peak_sustainable_pct, 1),
        headroom_pct            = headroom_pct,
        can_take_more           = can_take_more,
        quality_sensitivity     = quality_sensitivity,
        high_load_quality_avg   = high_load_quality_avg,
        normal_load_quality_avg = normal_load_quality_avg,
        already_overworked      = already_overworked,
        wip                     = wip,
        sprint_scenarios        = scenarios,
        recommendation          = recommendation,
        confidence              = confidence,
        weeks_analyzed          = n,
        weekly                  = weekly,
        top_load_drivers        = top_load_drivers,
    )
