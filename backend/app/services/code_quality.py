"""
code_quality.py — модуль оценки качества коммитов и pull request'ов.

Подключается к metrics_engine.py и используется при seed/sync.
Все функции — чистые (pure), без зависимостей от БД.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# COMMIT QUALITY
# ══════════════════════════════════════════════════════════════════════════════

# Conventional Commits: https://www.conventionalcommits.org/
_CONVENTIONAL_PATTERN = re.compile(
    r'^(feat|fix|refactor|perf|test|docs|chore|style|ci|build|revert)'
    r'(\(.+\))?(!)?:\s.{3,}',
    re.IGNORECASE,
)

# Мусорные сообщения — сигнал низкого качества
_GARBAGE_MSGS = {
    'wip', 'fix', 'fixes', 'fixed', 'update', 'updates', 'updated',
    'changes', 'change', 'misc', 'stuff', 'test', 'temp', 'tmp',
    'asdf', 'qwerty', '...', '..', '.', 'commit', 'push', 'done',
    'работа', 'правки', 'правка', 'исправление', 'обновление',
}

# Размерные категории PR/коммита (по добавленным строкам)
_SIZE_LABELS = [
    (0,   'XS'),   # 0–9 строк
    (10,  'S'),    # 10–49
    (50,  'M'),    # 50–199
    (200, 'L'),    # 200–499
    (500, 'XL'),   # 500+
]


@dataclass
class CommitQuality:
    """Результат анализа одного коммита."""
    sha:                  str
    message:              str

    # Структура сообщения
    has_conventional_prefix: bool = False   # feat:/fix:/refactor: и т.д.
    commit_type:          Optional[str] = None  # feat, fix, refactor…
    is_breaking_change:   bool = False      # содержит '!' или BREAKING CHANGE
    subject_length:       int  = 0          # длина первой строки
    has_body:             bool = False      # есть описание после пустой строки
    is_garbage_message:   bool = False      # мусорное сообщение

    # Размер изменений
    additions:            int  = 0
    deletions:            int  = 0
    size_label:           str  = 'XS'      # XS/S/M/L/XL
    churn_ratio:          float = 0.0      # (add+del)/max(add,del)

    # Итоговая оценка [0..100]
    quality_score:        float = 0.0

    # Факторы для отображения
    score_breakdown:      dict  = field(default_factory=dict)


def analyze_commit(
    sha: str,
    message: str,
    additions: int = 0,
    deletions: int  = 0,
) -> CommitQuality:
    """
    Анализирует один коммит и возвращает CommitQuality.
    Вызывается при seed и при реальном sync с GitHub.
    """
    result = CommitQuality(sha=sha, message=message,
                           additions=additions, deletions=deletions)

    # ── Анализ сообщения ─────────────────────────────────────────────────────
    first_line = message.split('\n')[0].strip()
    result.subject_length = len(first_line)

    m = _CONVENTIONAL_PATTERN.match(first_line)
    if m:
        result.has_conventional_prefix = True
        result.commit_type = m.group(1).lower()
        result.is_breaking_change = bool(m.group(3))  # '!'
    else:
        result.commit_type = _guess_commit_type(first_line)

    # Есть ли тело (описание)?
    lines = message.strip().split('\n')
    if len(lines) > 2 and lines[1].strip() == '':
        result.has_body = True

    # Мусорное сообщение?
    result.is_garbage_message = (
        first_line.lower().strip('.!? ') in _GARBAGE_MSGS
        or result.subject_length < 8
    )

    # ── Анализ размера ───────────────────────────────────────────────────────
    result.size_label = _size_label(additions)
    total = additions + deletions
    peak  = max(additions, deletions, 1)
    result.churn_ratio = round(total / peak, 3)

    # ── Итоговый скор ────────────────────────────────────────────────────────
    result.quality_score, result.score_breakdown = _commit_score(result)
    return result


def _guess_commit_type(msg: str) -> Optional[str]:
    """Эвристика типа коммита без conventional prefix."""
    lower = msg.lower()
    if any(w in lower for w in ('fix', 'bug', 'hotfix', 'patch', 'resolve')):
        return 'fix'
    if any(w in lower for w in ('feat', 'add', 'implement', 'new', 'create', 'support')):
        return 'feat'
    if any(w in lower for w in ('refactor', 'cleanup', 'clean', 'restructure', 'extract')):
        return 'refactor'
    if any(w in lower for w in ('test', 'spec', 'coverage')):
        return 'test'
    if any(w in lower for w in ('perf', 'optim', 'speed', 'slow', 'cache')):
        return 'perf'
    if any(w in lower for w in ('doc', 'readme', 'comment', 'changelog')):
        return 'docs'
    return None


def _size_label(additions: int) -> str:
    label = 'XS'
    for threshold, lbl in _SIZE_LABELS:
        if additions >= threshold:
            label = lbl
    return label


def _commit_score(c: CommitQuality) -> tuple[float, dict]:
    """
    Считает итоговый скор [0..100] и разбивку по факторам.

    Компоненты:
      - message_quality  (40 pts) — conventional prefix, длина, тело
      - size_quality     (30 pts) — штраф за огромные коммиты
      - type_value       (20 pts) — тип изменения (feat/fix > chore)
      - body_bonus       (10 pts) — есть описание
    """
    breakdown = {}

    # 1. Качество сообщения (40)
    if c.is_garbage_message:
        msg_score = 0.0
    elif c.has_conventional_prefix:
        msg_score = 40.0
        # Бонус за длину субъекта (идеал 50–72 символа)
        if 20 <= c.subject_length <= 72:
            msg_score = 40.0
        elif c.subject_length < 20:
            msg_score = 25.0
    else:
        # Есть смысловое сообщение, но без prefix
        msg_score = 18.0 if c.subject_length >= 15 else 8.0
    breakdown['message'] = round(msg_score, 1)

    # 2. Размер коммита (30) — маленькие коммиты проще ревьюировать
    additions = c.additions
    if additions == 0:
        size_score = 15.0   # только удаление — нейтрально
    elif additions <= 50:
        size_score = 30.0   # XS/S — отлично
    elif additions <= 200:
        size_score = 25.0   # M — хорошо
    elif additions <= 500:
        size_score = 15.0   # L — штраф
    else:
        size_score = 5.0    # XL — большой штраф
    breakdown['size'] = round(size_score, 1)

    # 3. Ценность типа (20)
    type_scores = {
        'fix':      20.0,   # исправление бага — высокая ценность
        'feat':     18.0,
        'perf':     18.0,
        'refactor': 15.0,
        'test':     14.0,
        'docs':     10.0,
        'chore':     8.0,
        'style':     5.0,
        'ci':        8.0,
        'build':     8.0,
        'revert':   12.0,
    }
    type_score = type_scores.get(c.commit_type or '', 10.0)
    breakdown['type'] = round(type_score, 1)

    # 4. Тело коммита (10)
    body_score = 10.0 if c.has_body else 0.0
    breakdown['body'] = body_score

    total = min(msg_score + size_score + type_score + body_score, 100.0)
    return round(total, 2), breakdown


# ══════════════════════════════════════════════════════════════════════════════
# PR QUALITY
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PRQuality:
    """Результат анализа одного Pull Request."""
    pr_number:            int
    title:                str

    # Структура заголовка
    has_conventional_prefix: bool = False
    pr_type:              Optional[str] = None
    title_length:         int  = 0
    title_is_generic:     bool = False   # "WIP", "fix", "Update X"

    # Связь с задачами
    has_jira_link:        bool = False   # ссылка на Jira в заголовке/теле
    jira_issue_key:       Optional[str] = None

    # Размер
    additions:            int  = 0
    deletions:            int  = 0
    changed_files:        int  = 0
    size_label:           str  = 'XS'
    is_oversized:         bool = False   # >500 additions — риск

    # Ревью
    review_comments:      int  = 0
    was_reviewed:         bool = False   # есть хоть один ревью
    approved_without_changes: bool = False  # LGTM без замечаний
    had_changes_requested:    bool = False  # просили изменить
    review_iterations:    int  = 0       # сколько раз просили изменения

    # Время
    time_to_merge_hours:  Optional[float] = None
    is_fast_merge:        bool = False   # < 1ч — возможно без ревью

    # Итог
    quality_score:        float = 0.0
    risk_flags:           list  = field(default_factory=list)
    score_breakdown:      dict  = field(default_factory=dict)


_GENERIC_PR_TITLES = {
    'wip', 'fix', 'fixes', 'update', 'updates', 'changes',
    'draft', 'test', 'temp', 'hotfix', 'patch',
}

_CONVENTIONAL_PR = re.compile(
    r'^(feat|fix|refactor|perf|test|docs|chore|style|ci|build|revert)'
    r'(\(.+\))?(!)?:\s.{3,}',
    re.IGNORECASE,
)

_JIRA_KEY = re.compile(r'\b([A-Z]{2,10}-\d+)\b')


def analyze_pr(
    pr_number:       int,
    title:           str,
    additions:       int   = 0,
    deletions:       int   = 0,
    changed_files:   int   = 0,
    review_comments: int   = 0,
    jira_issue_key:  Optional[str] = None,
    review_states:   list[str] = None,   # ['APPROVED', 'CHANGES_REQUESTED', ...]
    time_to_merge_hours: Optional[float] = None,
) -> PRQuality:
    """
    Анализирует один PR и возвращает PRQuality.
    review_states — список состояний всех ревью на этот PR.
    """
    review_states = review_states or []
    result = PRQuality(
        pr_number=pr_number, title=title,
        additions=additions, deletions=deletions,
        changed_files=changed_files, review_comments=review_comments,
        jira_issue_key=jira_issue_key,
        time_to_merge_hours=time_to_merge_hours,
    )

    # ── Анализ заголовка ─────────────────────────────────────────────────────
    result.title_length = len(title.strip())
    result.title_is_generic = title.lower().strip() in _GENERIC_PR_TITLES

    m = _CONVENTIONAL_PR.match(title.strip())
    if m:
        result.has_conventional_prefix = True
        result.pr_type = m.group(1).lower()
    else:
        result.pr_type = _guess_commit_type(title)

    # ── Jira ─────────────────────────────────────────────────────────────────
    if jira_issue_key:
        result.has_jira_link = True
    elif _JIRA_KEY.search(title):
        result.has_jira_link = True
        result.jira_issue_key = _JIRA_KEY.search(title).group(1)

    # ── Размер ───────────────────────────────────────────────────────────────
    result.size_label  = _size_label(additions)
    result.is_oversized = additions > 500

    # ── Ревью ─────────────────────────────────────────────────────────────────
    result.was_reviewed = len(review_states) > 0
    result.had_changes_requested = 'CHANGES_REQUESTED' in review_states
    result.approved_without_changes = (
        'APPROVED' in review_states and 'CHANGES_REQUESTED' not in review_states
    )
    result.review_iterations = review_states.count('CHANGES_REQUESTED')

    # ── Время ─────────────────────────────────────────────────────────────────
    if time_to_merge_hours is not None:
        result.is_fast_merge = time_to_merge_hours < 1.0

    # ── Флаги риска ──────────────────────────────────────────────────────────
    flags = []
    if result.is_oversized:
        flags.append('oversized_pr')         # большой PR — сложнее ревьюировать
    if not result.was_reviewed:
        flags.append('no_review')            # влит без ревью
    if result.is_fast_merge and not result.was_reviewed:
        flags.append('fast_merge_no_review') # быстро влит без ревью
    if result.title_is_generic:
        flags.append('generic_title')        # неинформативный заголовок
    if not result.has_jira_link:
        flags.append('no_jira_link')         # нет трекинга
    result.risk_flags = flags

    # ── Итоговый скор ────────────────────────────────────────────────────────
    result.quality_score, result.score_breakdown = _pr_score(result)
    return result


def _pr_score(p: PRQuality) -> tuple[float, dict]:
    """
    Итоговый скор PR [0..100].

    Компоненты:
      - review_quality  (35 pts) — было ревью, итерации, approved
      - title_quality   (20 pts) — conventional, длина, не generic
      - size_quality    (20 pts) — штраф за огромные PR
      - traceability    (15 pts) — ссылка на Jira
      - merge_hygiene   (10 pts) — время до merge, не fast merge без ревью
    """
    breakdown = {}

    # 1. Качество ревью (35)
    if not p.was_reviewed:
        review_score = 0.0
    elif p.approved_without_changes:
        review_score = 35.0
    elif p.had_changes_requested:
        # Итерации — хорошо (код обсуждался), но не бесконечно
        review_score = min(25.0 + p.review_iterations * 2, 30.0)
    else:
        review_score = 20.0   # Commented, но не Approved/CR
    breakdown['review'] = round(review_score, 1)

    # 2. Качество заголовка (20)
    if p.title_is_generic:
        title_score = 0.0
    elif p.has_conventional_prefix:
        title_score = 20.0
    elif p.title_length >= 15:
        title_score = 12.0
    else:
        title_score = 5.0
    breakdown['title'] = round(title_score, 1)

    # 3. Размер PR (20)
    if p.additions <= 50:
        size_score = 20.0
    elif p.additions <= 200:
        size_score = 16.0
    elif p.additions <= 500:
        size_score = 8.0
    else:
        size_score = 2.0
    breakdown['size'] = round(size_score, 1)

    # 4. Трассируемость (15)
    traceability_score = 15.0 if p.has_jira_link else 0.0
    breakdown['traceability'] = traceability_score

    # 5. Merge hygiene (10)
    if p.is_fast_merge and not p.was_reviewed:
        hygiene_score = 0.0   # быстро влит без ревью — плохо
    elif p.time_to_merge_hours is not None and p.time_to_merge_hours > 168:
        hygiene_score = 5.0   # висел более недели
    else:
        hygiene_score = 10.0
    breakdown['hygiene'] = round(hygiene_score, 1)

    total = min(review_score + title_score + size_score
                + traceability_score + hygiene_score, 100.0)
    return round(total, 2), breakdown


# ══════════════════════════════════════════════════════════════════════════════
# АГРЕГАЦИЯ ДЛЯ DAILY/WEEKLY МЕТРИК
# ══════════════════════════════════════════════════════════════════════════════

def aggregate_commit_quality(commits: list[CommitQuality]) -> dict:
    """
    Агрегирует качество коммитов за период.
    Возвращает поля для DailyMetric/PerformanceScore.
    """
    if not commits:
        return {
            'avg_commit_quality':        0.0,
            'conventional_commit_ratio': 0.0,
            'avg_commit_size':           'XS',
            'large_commit_count':        0,
            'commit_type_distribution':  {},
        }

    scores = [c.quality_score for c in commits]
    conventional = sum(1 for c in commits if c.has_conventional_prefix)
    large = sum(1 for c in commits if c.additions > 200)

    # Распределение типов
    type_dist: dict[str, int] = {}
    for c in commits:
        t = c.commit_type or 'unknown'
        type_dist[t] = type_dist.get(t, 0) + 1

    return {
        'avg_commit_quality':        round(sum(scores) / len(scores), 2),
        'conventional_commit_ratio': round(conventional / len(commits), 3),
        'avg_commit_size':           _most_common_size(commits),
        'large_commit_count':        large,
        'commit_type_distribution':  type_dist,
    }


def aggregate_pr_quality(prs: list[PRQuality]) -> dict:
    """
    Агрегирует качество PR за период.
    Возвращает поля для DailyMetric/PerformanceScore.
    """
    if not prs:
        return {
            'avg_pr_quality':       0.0,
            'pr_review_rate':       0.0,
            'oversized_pr_count':   0,
            'no_jira_pr_count':     0,
            'fast_merge_rate':      0.0,
            'avg_pr_size_label':    'XS',
            'pr_risk_flags':        [],
        }

    scores    = [p.quality_score for p in prs]
    reviewed  = sum(1 for p in prs if p.was_reviewed)
    oversized = sum(1 for p in prs if p.is_oversized)
    no_jira   = sum(1 for p in prs if not p.has_jira_link)
    fast_merge = sum(1 for p in prs if p.is_fast_merge)

    all_flags: list[str] = []
    for p in prs:
        all_flags.extend(p.risk_flags)

    return {
        'avg_pr_quality':     round(sum(scores) / len(scores), 2),
        'pr_review_rate':     round(reviewed / len(prs), 3),
        'oversized_pr_count': oversized,
        'no_jira_pr_count':   no_jira,
        'fast_merge_rate':    round(fast_merge / len(prs), 3),
        'avg_pr_size_label':  _most_common_size_pr(prs),
        'pr_risk_flags':      list(set(all_flags)),
    }


def _most_common_size(commits: list[CommitQuality]) -> str:
    counts: dict[str, int] = {}
    for c in commits:
        counts[c.size_label] = counts.get(c.size_label, 0) + 1
    return max(counts, key=counts.get) if counts else 'XS'


def _most_common_size_pr(prs: list[PRQuality]) -> str:
    counts: dict[str, int] = {}
    for p in prs:
        counts[p.size_label] = counts.get(p.size_label, 0) + 1
    return max(counts, key=counts.get) if counts else 'XS'