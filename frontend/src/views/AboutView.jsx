import { T, font, fontSans } from '../tokens'

const S = {
  page:    { maxWidth: 860, margin: '0 auto' },
  h1:      { fontSize: 26, fontWeight: 800, color: T.text, fontFamily: fontSans, letterSpacing: '-0.03em', marginBottom: 6 },
  lead:    { fontSize: 14, color: T.textMd, fontFamily: fontSans, lineHeight: 1.7, marginBottom: 32 },
  section: { marginBottom: 40 },
  h2:      { fontSize: 13, fontWeight: 700, color: T.textMd, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 16 },
  card:    { background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '18px 20px', marginBottom: 10 },
  cardTitle: { fontSize: 14, fontWeight: 700, color: T.text, fontFamily: fontSans, marginBottom: 6 },
  cardBody:  { fontSize: 13, color: T.textMd, fontFamily: fontSans, lineHeight: 1.65 },
  formula:   { fontFamily: font, fontSize: 12, color: T.cyan, background: T.card, borderRadius: 6, padding: '8px 12px', margin: '8px 0', display: 'block' },
  tag:       { display: 'inline-block', fontSize: 11, fontFamily: font, padding: '2px 8px', borderRadius: 4, marginRight: 6, marginBottom: 4 },
  warn:      { background: `${T.amber}18`, border: `1px solid ${T.amber}40`, borderRadius: 8, padding: '12px 16px', fontSize: 13, color: T.textMd, fontFamily: fontSans, lineHeight: 1.6 },
  note:      { background: `${T.accentLt}12`, border: `1px solid ${T.accentLt}30`, borderRadius: 8, padding: '12px 16px', fontSize: 13, color: T.textMd, fontFamily: fontSans, lineHeight: 1.6 },
  row:       { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 },
  dot:       { display: 'inline-block', width: 8, height: 8, borderRadius: '50%', marginRight: 8, flexShrink: 0 },
}

function Score({ label, color, value, desc }) {
  return (
    <div style={{ ...S.card, borderLeft: `3px solid ${color}`, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color, fontFamily: fontSans }}>{label}</span>
        {value && <span style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>{value}</span>}
      </div>
      <div style={S.cardBody}>{desc}</div>
    </div>
  )
}

function Block({ title, children }) {
  return (
    <div style={S.card}>
      <div style={S.cardTitle}>{title}</div>
      <div style={S.cardBody}>{children}</div>
    </div>
  )
}

export default function AboutView() {
  return (
    <div style={S.page}>
      <h1 style={S.h1}>Как работает DevPerf</h1>
      <p style={S.lead}>
        DevPerf — система аналитики эффективности команды разработки. Она собирает данные из GitHub и Jira,
        вычисляет метрики на основе реальной активности и помогает менеджеру готовиться к 1:1 встречам.
        Система не заменяет суждение — она даёт контекст для разговора.
      </p>

      {/* ── Источники данных ── */}
      <div style={S.section}>
        <div style={S.h2}>Источники данных</div>
        <div style={S.row}>
          <Block title="GitHub">
            При синхронизации система загружает: коммиты (дата, +/− строки), pull requests (создание, мёрж,
            size), ревью (APPROVED / CHANGES_REQUESTED / COMMENTED), комментарии к PR, issues.
            Для каждого PR дополнительно запрашивается unified diff — он передаётся в GigaChat для
            смыслового анализа.
          </Block>
          <Block title="Jira">
            Загружаются задачи назначенные на разработчика: тип, статус, story points, дата создания и
            закрытия, история переходов (transitions), количество переоткрытий.
          </Block>
        </div>
        <div style={{ ...S.note, marginTop: 8 }}>
          <strong style={{ color: T.accentLt }}>Важно:</strong> все метрики считаются относительно
          личного baseline разработчика — среднего за последние 4 недели. Система не сравнивает людей
          между собой, а каждого с самим собой.
        </div>
      </div>

      {/* ── Четыре показателя ── */}
      <div style={S.section}>
        <div style={S.h2}>Четыре показателя (0–100)</div>

        <Score
          label="Поставка" color={T.green}
          value="= task_velocity_score"
          desc={<>
            Скорость закрытия Jira-задач с поправкой на сложность. Берётся среднее время жизни задачи
            (cycle time) по всем закрытым за неделю.
            <code style={S.formula}>
              abs_score = max(0, 100 − (avg_cycle_hours − 8) × 1.14)<br/>
              rel_score = clip(50 × baseline_ct / curr_ct, 0, 100)<br/>
              delivery  = (abs_score + rel_score) / 2
            </code>
            ≤8ч cycle time = 100 баллов, ≥96ч = 0. Если нет данных Jira — нейтральные 50.
            Если разработчик закрывает задачи быстрее своего обычного темпа — оценка растёт.
          </>}
        />

        <Score
          label="Качество" color={T.purple}
          value="= 50% code_health + 50% GigaChat avg"
          desc={<>
            Составная метрика из двух источников:
            <br/><br/>
            <strong style={{ color: T.text }}>Code health (структурное качество):</strong>
            <code style={S.formula}>
              churn_score  = max(0, 100 − (avg_churn − 1.0) × 66.7)  // churn 1.0 = идеал<br/>
              rework_score = (1 − CHANGES_REQUESTED / total_pr) × 100<br/>
              code_health  = churn_score × 0.4 + rework_score × 0.6
            </code>
            Churn ratio = (added + deleted) / max(added, deleted). Значение 1.0 означает новый код
            без переписывания. Чем больше CHANGES_REQUESTED на PR разработчика, тем ниже оценка.
            <br/><br/>
            <strong style={{ color: T.text }}>GigaChat (смысловое качество):</strong> для каждого PR
            GigaChat получает diff и оценивает качество по шкале 0–100. Итог блендируется с code health 50/50.
            Если GigaChat-оценок нет — используется только code health.
          </>}
        />

        <Score
          label="Коллаборация" color={T.amber}
          value="= 60% engagement_depth + 40% responsiveness"
          desc={<>
            <strong style={{ color: T.text }}>Engagement depth (60%):</strong>
            <code style={S.formula}>
              comment_score    = clip(median_comment_length / 200 × 100, 0, 100)<br/>
              complexity_score = clip(avg_sp / baseline_sp × 50, 0, 100)<br/>
              engagement       = comment_score × 0.5 + complexity_score × 0.5
            </code>
            Медиана длины ревью-комментариев: ≥200 символов = 100 баллов. Сложность задач (story points)
            относительно личного baseline — берёт ли разработчик задачи сложнее обычного.
            <br/><br/>
            <strong style={{ color: T.text }}>Responsiveness (40%):</strong> время от создания PR разработчика
            до первого ревью от коллеги. ≤2ч = 100, ≥48ч = 0. Также сравнивается с личным baseline.
          </>}
        />

        <div style={{ ...S.card, borderTop: `2px solid ${T.border}` }}>
          <div style={S.cardTitle}>Итоговый Overall Score</div>
          <code style={S.formula}>
            overall = delivery×0.40 + quality×0.30 + collaboration×0.30
          </code>
          <div style={S.cardBody}>
            Поставка имеет наибольший вес — это главный результат работы разработчика.
            Качество и Коллаборация равнозначны.
          </div>
        </div>
      </div>

      {/* ── AI-функции ── */}
      <div style={S.section}>
        <div style={S.h2}>AI-функции (GigaChat)</div>
        <div style={S.row}>
          <Block title="Оценка PR">
            При синхронизации или по запросу система получает unified diff PR из GitHub и отправляет его
            в GigaChat вместе с метаданными. Модель возвращает: оценку качества (0–100), оценку сложности,
            причины оценок и краткий AI-обзор — одно предложение о том что изменено и зачем.
            Используется модель GigaChat (базовая).
          </Block>
          <Block title="Помощник 1:1">
            Генерирует вопросы для встречи на основе метрик разработчика. Получает все четыре
            показателя с объяснением как они считаются, тренд velocity, риск выгорания, долю
            активности в нерабочее время и по выходным. Задаёт острые вопросы там где видит аномалию —
            и не задаёт общих вопросов там где всё в норме.
          </Block>
        </div>
      </div>

      {/* ── Бизнес-ценность ── */}
      <div style={S.section}>
        <div style={S.h2}>Бизнес-ценность</div>
        <div style={S.row}>
          <Block title="Для менеджера">
            Видит динамику каждого разработчика без ручного сбора данных из Jira и GitHub.
            Получает готовые вопросы для 1:1 основанные на реальных метриках, а не ощущениях.
            Может заметить снижение эффективности за 2–3 недели до того, как оно станет очевидным.
          </Block>
          <Block title="Для команды">
            Прозрачные правила оценки — каждый может понять почему его показатель такой.
            Нет сравнения с коллегами — только с самим собой. Риск выгорания виден заранее.
          </Block>
          <Block title="Раннее обнаружение проблем">
            Падение velocity_trend три недели подряд — сигнал для разговора, не для выговора.
            Высокая активность по ночам и выходным при падающем overall — классический паттерн
            предвыгорания.
          </Block>
          <Block title="Качество процесса">
            Rhythm-метрика выявляет спринты где команда работает рывками. Code health показывает
            технический долг через churn и rework rate задолго до того, как он станет проблемой.
          </Block>
        </div>
      </div>

      {/* ── Ограничения ── */}
      <div style={S.section}>
        <div style={S.h2}>Ограничения системы</div>
        <div style={{ ...S.warn }}>
          <strong style={{ color: T.amber }}>Система — инструмент для диалога, не для кадровых решений.</strong>
          <br/><br/>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {[
              'Низкая Поставка может означать отпуск, болезнь или архитектурную работу без Jira-задач',
              'Низкое Качество в ревью может означать сложный PR с обоснованными замечаниями, а не плохой код',
              'Если Jira не ведётся дисциплинированно — Поставка будет занижена независимо от реальной работы',
              'Метрики считаются по времени последней синхронизации — без синхронизации данные устаревают',
              'Система не видит код-ревью в Slack, дизайн-сессии, онбординг, менторинг и другую нетрекаемую работу',
            ].map((t, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <span style={{ ...S.dot, background: T.amber, marginTop: 6 }} />
                <span style={{ fontSize: 13, color: T.textMd, fontFamily: fontSans, lineHeight: 1.5 }}>{t}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Stack ── */}
      <div style={S.section}>
        <div style={S.h2}>Технический стек</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {[
            ['FastAPI', T.accentLt], ['SQLAlchemy async', T.accentLt], ['PostgreSQL 16', T.accentLt],
            ['React 18', T.green], ['Vite', T.green],
            ['GitHub REST API v3', T.amber], ['Jira Cloud API v3', T.amber],
            ['GigaChat API', T.purple], ['Docker Compose', T.textMd],
          ].map(([label, color]) => (
            <span key={label} style={{ ...S.tag, background: `${color}18`, color, border: `1px solid ${color}30` }}>
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
