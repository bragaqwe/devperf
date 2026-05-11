import { useState, useEffect, useRef } from 'react'
import {
  LineChart, Line, BarChart, Bar, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, ResponsiveContainer,
  XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Legend,
} from 'recharts'
import { api } from '../api'
import { T, font, fontSans, scoreColor, burnoutColor, burnoutLabel } from '../tokens'
import { Card, Badge, Btn, Spinner, ScoreRing, ChartTooltip, Avatar, Section, EmptyState } from '../components/UI'
import DayTimeline from './DayTimeline'

// ── Карта активности ─────────────────────────────────────────────────────────

function ActivityHeatmap({ daily, devId, devName }) {
  const [hovDay,   setHovDay]   = useState(null)
  const [drillDay, setDrillDay] = useState(null)

  const today = new Date()
  const cells = []
  for (let i = 83; i >= 0; i--) {
    const d   = new Date(today); d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    const row = daily.find(dm => dm.date.slice(0, 10) === key)
    const total = row ? row.commits_count + row.prs_merged + row.reviews_given + row.issues_resolved : 0
    cells.push({ key, d, total, row })
  }
  const maxTotal = Math.max(...cells.map(c => c.total), 1)
  const cellColor = t => {
    if (t === 0) return T.border
    const p = t / maxTotal
    return p > 0.75 ? T.green : p > 0.4 ? '#10b98180' : p > 0.15 ? '#10b98148' : '#10b98128'
  }
  const weeks = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))

  return (
    <>
      <div style={{ display: 'flex', gap: 3 }}>
        {weeks.map((week, wi) => (
          <div key={wi} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {week.map(cell => (
              <div key={cell.key}
                title={`${cell.key}: ${cell.total} событий`}
                onClick={() => cell.total > 0 && setDrillDay(cell.key)}
                onMouseEnter={() => setHovDay(cell.key)}
                onMouseLeave={() => setHovDay(null)}
                style={{
                  width: 13, height: 13, borderRadius: 2,
                  background: hovDay === cell.key ? T.accentLt : cellColor(cell.total),
                  cursor: cell.total > 0 ? 'pointer' : 'default',
                  transition: 'background 0.1s',
                  border: hovDay === cell.key ? `1px solid ${T.accentLt}` : '1px solid transparent',
                }}
              />
            ))}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, fontSize: 10, color: T.textSm, fontFamily: font }}>
        <span>Меньше</span>
        {[0, 0.2, 0.5, 0.8, 1].map(p => (
          <div key={p} style={{ width: 11, height: 11, borderRadius: 2, background: p === 0 ? T.border : `rgba(16,185,129,${0.2 + p * 0.8})` }} />
        ))}
        <span>Больше</span>
        <span style={{ marginLeft: 8 }}>Нажмите на день для детальной хронологии →</span>
      </div>
      {hovDay && (() => {
        const cell = cells.find(c => c.key === hovDay)
        if (!cell?.row) return null
        return (
          <div style={{ padding: '8px 12px', borderRadius: 6, background: T.surface, border: `1px solid ${T.border}`, fontSize: 11, fontFamily: font, color: T.textMd, marginTop: 6 }}>
            <span style={{ color: T.text, fontWeight: 600 }}>{hovDay}</span>{' — '}
            {cell.row.commits_count} коммитов · {cell.row.prs_merged} PR · {cell.row.reviews_given} ревью · {cell.row.issues_resolved} задач
            {cell.row.story_points_delivered > 0 ? ` · ${cell.row.story_points_delivered.toFixed(1)} SP` : ''}
          </div>
        )
      })()}
      {drillDay && <DayTimeline devId={devId} devName={devName} day={drillDay} onClose={() => setDrillDay(null)} />}
    </>
  )
}

// ── Оценки PR ─────────────────────────────────────────────────────────────────

function PRAssessmentBadge({ score, label, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <div style={{ fontSize: 16, fontWeight: 800, color, fontFamily: font }}>{score.toFixed(0)}</div>
      <div style={{ fontSize: 9, color: T.textSm, textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: font }}>{label}</div>
    </div>
  )
}

function PRList({ devId, days = 30 }) {
  const [prs,     setPrs]     = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.get(`/developers/${devId}/pull-requests?days=${days}`)
      .then(data => { setPrs(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [devId, days])

  if (loading) return <div style={{ textAlign: 'center', padding: 24 }}><Spinner size={20} /></div>
  if (!prs.length) return <div style={{ color: T.textSm, fontSize: 13, fontFamily: font, padding: '12px 0' }}>Нет PR за выбранный период</div>

  const stateLabel = { open: 'Открыт', closed: 'Закрыт', merged: 'Влит' }
  const stateColor = { open: T.accentLt, closed: T.textSm, merged: T.green }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {prs.map(pr => {
        const state = pr.merged_at ? 'merged' : pr.state
        const summary = pr.assessment?.ai_summary
        return (
          <div key={pr.id} style={{ padding: '12px 14px', borderRadius: 8, background: T.bg, border: `1px solid ${T.border}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                  <Badge label={stateLabel[state] || pr.state} color={stateColor[state] || T.textSm} />
                  <a href={pr.html_url} target="_blank" rel="noreferrer"
                    style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: fontSans, textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {pr.title}
                  </a>
                </div>
                <div style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>
                  #{pr.number} · {pr.repo} · +{pr.additions} / -{pr.deletions} строк · {pr.changed_files} файлов
                </div>
              </div>
              {pr.assessment ? (
                <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexShrink: 0, padding: '6px 12px', borderRadius: 8, background: T.surface, border: `1px solid ${T.border}` }}>
                  <PRAssessmentBadge score={pr.assessment.quality_score} label="Качество" color={T.purple} />
                  <PRAssessmentBadge score={pr.assessment.complexity_score} label="Сложность" color={T.amber} />
                  {pr.assessment.is_stub && (
                    <div style={{ fontSize: 9, color: T.textSm, fontFamily: font }}>авто</div>
                  )}
                </div>
              ) : (
                <AssessPRButton prId={pr.id} onDone={() => {
                  api.get(`/developers/${devId}/pull-requests?days=${days}`).then(setPrs).catch(() => {})
                }} />
              )}
            </div>
            {summary && (
              <div style={{ marginTop: 8, padding: '7px 10px', borderRadius: 6, background: T.surface, borderLeft: `3px solid ${T.purple}` }}>
                <div style={{ fontSize: 10, color: T.purple, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>AI-обзор</div>
                <div style={{ fontSize: 12, color: T.textMd, fontFamily: fontSans, lineHeight: 1.5 }}>{summary}</div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function AssessPRButton({ prId, onDone }) {
  const [loading, setLoading] = useState(false)
  const handle = async () => {
    setLoading(true)
    try { await api.get(`/pull-requests/${prId}/assessment`); onDone() }
    catch (e) { console.error(e) }
    finally { setLoading(false) }
  }
  return (
    <Btn small onClick={handle} disabled={loading}>
      {loading ? '…' : 'Оценить'}
    </Btn>
  )
}

// ── 1:1 Помощник ─────────────────────────────────────────────────────────────

const CATEGORY_COLOR = {
  мотивация: T.green,
  нагрузка:  T.amber,
  блокеры:   T.red,
  карьера:   T.purple,
}

// ── Двухнедельная история ─────────────────────────────────────────────────────

const SCORE_COLS = [
  { key: 'overall_score',       label: 'Общий',        color: T.accentLt },
  { key: 'delivery_score',      label: 'Поставка',     color: T.green },
  { key: 'quality_score',       label: 'Качество',     color: T.purple },
  { key: 'collaboration_score', label: 'Коллаборация', color: T.amber },
]

function DeltaBadge({ value }) {
  if (value == null) return <span style={{ color: T.textSm, fontSize: 11, fontFamily: font }}>—</span>
  const up = value >= 0
  return (
    <span style={{ fontSize: 11, fontFamily: font, fontWeight: 600, color: up ? T.green : T.red }}>
      {up ? '↑' : '↓'} {Math.abs(value).toFixed(1)}
    </span>
  )
}

const DEVIATION_BAR_MAX = 3.5   // z-score при котором полоска = 100%

function AnomalyBadge({ period }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!period.is_anomaly) return null

  const score    = period.anomaly_score != null ? `${(period.anomaly_score * 100).toFixed(0)}%` : ''
  const features = period.anomaly_features || []

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      {/* Бейдж-триггер */}
      <span
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 10, fontFamily: font, fontWeight: 700,
          color: T.amber, background: `${T.amber}18`,
          border: `1px solid ${T.amber}40`,
          borderRadius: 4, padding: '2px 7px',
          cursor: 'pointer', whiteSpace: 'nowrap',
          userSelect: 'none',
        }}
      >
        ⚠ аномалия {score}
        <span style={{ fontSize: 8, opacity: 0.7 }}>{open ? '▲' : '▼'}</span>
      </span>

      {/* Выпадашка */}
      {open && (
        <div style={{
          position: 'absolute', right: 0, top: 'calc(100% + 6px)', zIndex: 200,
          width: 300,
          background: T.surface,
          border: `1px solid ${T.amber}50`,
          borderRadius: 10,
          boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
          padding: '14px 16px',
        }}>
          {/* Заголовок */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: T.amber, fontFamily: fontSans }}>
              ⚠ Аномальный период
            </div>
            <div style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>
              индекс {score}
            </div>
          </div>

          {/* Описание */}
          <div style={{ fontSize: 11, color: T.textMd, fontFamily: fontSans, lineHeight: 1.5, marginBottom: 12 }}>
            Isolation Forest выявил этот период как статистически нетипичный
            для данного разработчика. Ниже — показатели с наибольшим отклонением от его нормы.
          </div>

          {/* Фичи */}
          {features.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {features.map((f, i) => {
                const barW = Math.min(100, (f.deviation / DEVIATION_BAR_MAX) * 100)
                const isHigh = f.direction === 'выше нормы'
                const barColor = isHigh ? T.amber : T.red
                return (
                  <div key={i}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: T.text, fontFamily: fontSans }}>
                        {f.label}
                      </span>
                      <span style={{ fontSize: 10, color: isHigh ? T.amber : T.red, fontFamily: font, fontWeight: 600 }}>
                        {isHigh ? '↑' : '↓'} {f.direction}
                      </span>
                    </div>
                    {/* Полоска отклонения */}
                    <div style={{ height: 4, background: `${T.border}`, borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', width: `${barW}%`,
                        background: barColor, borderRadius: 2,
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
                      <span style={{ fontSize: 10, color: T.textSm, fontFamily: font }}>
                        значение: <span style={{ color: T.text }}>{f.value}</span>
                      </span>
                      <span style={{ fontSize: 10, color: T.textSm, fontFamily: font }}>
                        норма: <span style={{ color: T.text }}>{f.mean}</span>
                        <span style={{ color: T.textSm }}> · z={f.deviation}</span>
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>
              Детализация недоступна
            </div>
          )}

          {/* Подсказка */}
          <div style={{
            marginTop: 14, paddingTop: 10, borderTop: `1px solid ${T.border}`,
            fontSize: 10, color: T.textSm, fontFamily: font, lineHeight: 1.5,
          }}>
            z — количество стандартных отклонений от среднего по истории разработчика
          </div>
        </div>
      )}
    </div>
  )
}

function BiWeeklyHistory({ devId }) {
  const [periods, setPeriods] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.get(`/developers/${devId}/biweekly-scores?periods=12`)
      .then(data => setPeriods(data.slice().reverse()))  // новейшие сверху
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [devId])

  if (loading) return <div style={{ padding: 40, display: 'flex', justifyContent: 'center' }}><Spinner /></div>
  if (!periods.length) return (
    <EmptyState icon="◈" text="Нет данных. Запустите синхронизацию чтобы появилась история." />
  )

  const chartData = periods.slice().reverse().map(p => ({
    period: new Date(p.period_start).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
    Общий:        +p.overall_score.toFixed(1),
    Поставка:     +p.delivery_score.toFixed(1),
    Качество:     +p.quality_score.toFixed(1),
    Коллаборация: +p.collaboration_score.toFixed(1),
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* График */}
      <Card>
        <div style={{ fontSize: 12, color: T.textSm, fontFamily: font, marginBottom: 14 }}>
          Динамика показателей по двухнедельным периодам
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
            <XAxis dataKey="period" tick={{ fontSize: 10, fill: T.textSm, fontFamily: font }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: T.textSm, fontFamily: font }} width={28} />
            <Tooltip content={<ChartTooltip />} />
            <Legend wrapperStyle={{ fontSize: 11, fontFamily: font }} />
            {SCORE_COLS.map(c => (
              <Line key={c.key} type="monotone" dataKey={c.label}
                stroke={c.color} strokeWidth={c.key === 'overall_score' ? 2.5 : 1.5}
                dot={{ r: 3 }} activeDot={{ r: 5 }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Таблица */}
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: fontSans }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                <th style={{ padding: '10px 14px', textAlign: 'left', color: T.textSm, fontFamily: font, fontSize: 11, fontWeight: 500, whiteSpace: 'nowrap' }}>Период</th>
                {SCORE_COLS.map(c => (
                  <th key={c.key} style={{ padding: '10px 12px', textAlign: 'right', color: c.color, fontFamily: font, fontSize: 11, fontWeight: 600 }}>{c.label}</th>
                ))}
                <th style={{ padding: '10px 12px', textAlign: 'right', color: T.textSm, fontFamily: font, fontSize: 11, fontWeight: 500 }}>Δ Общий</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', color: T.textSm, fontFamily: font, fontSize: 11, fontWeight: 500 }}>Выгорание</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', color: T.amber, fontFamily: font, fontSize: 11, fontWeight: 500 }}>Аномалия</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((p, i) => {
                const start = new Date(p.period_start)
                const end   = new Date(p.period_end)
                const label = `${start.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} – ${end.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}`
                const isFirst = i === 0
                return (
                  <tr key={p.id} style={{
                    borderBottom: `1px solid ${T.border}`,
                    background: p.is_anomaly
                      ? `${T.amber}0a`
                      : isFirst ? `${T.accentLt}08` : 'transparent',
                  }}>
                    <td style={{ padding: '9px 14px', color: T.text, whiteSpace: 'nowrap', fontWeight: isFirst ? 600 : 400 }}>{label}</td>
                    {SCORE_COLS.map(c => (
                      <td key={c.key} style={{ padding: '9px 12px', textAlign: 'right', color: scoreColor(p[c.key]), fontWeight: c.key === 'overall_score' ? 700 : 400 }}>
                        {p[c.key].toFixed(0)}
                      </td>
                    ))}
                    <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                      <DeltaBadge value={p.delta_overall} />
                    </td>
                    <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                      <span style={{ color: burnoutColor[p.burnout_risk_level], fontSize: 11, fontFamily: font }}>
                        {burnoutLabel[p.burnout_risk_level] || p.burnout_risk_level}
                      </span>
                    </td>
                    <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                      <AnomalyBadge period={p} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}


function OneOnOnePanel({ devId }) {
  const [meetings, setMeetings] = useState([])
  const [active,   setActive]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [notes,    setNotes]    = useState('')
  const [saving,   setSaving]   = useState(false)

  const loadMeetings = () => {
    api.get(`/developers/${devId}/one-on-one`)
      .then(data => { setMeetings(data); if (data.length) setActive(data[0]) })
      .catch(() => {})
  }

  useEffect(() => { loadMeetings() }, [devId])

  const generate = async () => {
    setLoading(true)
    try {
      const m = await api.post(`/developers/${devId}/one-on-one`)
      setMeetings(prev => [m, ...prev])
      setActive(m)
      setNotes(m.notes || '')
    } catch (e) { alert(e.message) }
    finally { setLoading(false) }
  }

  const saveNotes = async () => {
    if (!active) return
    setSaving(true)
    try {
      const updated = await api.patch(`/developers/${devId}/one-on-one/${active.id}`, notes)
      setActive(updated)
      setMeetings(prev => prev.map(m => m.id === updated.id ? updated : m))
    } catch (e) { alert(e.message) }
    finally { setSaving(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 13, color: T.textSm, fontFamily: font }}>
          {meetings.length ? `${meetings.length} встреч в истории` : 'Нет истории встреч'}
        </div>
        <Btn variant="primary" onClick={generate} disabled={loading}>
          {loading ? 'Генерирую…' : '+ Создать план встречи'}
        </Btn>
      </div>

      {meetings.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {meetings.map(m => (
            <button key={m.id} onClick={() => { setActive(m); setNotes(m.notes || '') }}
              style={{
                padding: '4px 10px', borderRadius: 6, border: `1px solid ${active?.id === m.id ? T.accentLt : T.border}`,
                background: active?.id === m.id ? T.accentDim : 'transparent',
                color: active?.id === m.id ? T.accentLt : T.textSm,
                fontSize: 11, fontFamily: font, cursor: 'pointer',
              }}>
              {new Date(m.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
            </button>
          ))}
        </div>
      )}

      {active && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {active.questions.map((q, i) => (
              <div key={i} style={{
                padding: '12px 14px', borderRadius: 8, background: T.bg,
                border: `1px solid ${(CATEGORY_COLOR[q.category] || T.border)}33`,
                borderLeft: `3px solid ${CATEGORY_COLOR[q.category] || T.border}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: q.advice ? 6 : 0 }}>
                  <div style={{ flex: 1, fontSize: 13, fontWeight: 600, color: T.text, fontFamily: fontSans, lineHeight: 1.4 }}>
                    {q.urgency === 1 && <span style={{ color: T.red, marginRight: 6, fontSize: 11 }}>●</span>}
                    {q.topic || q.question}
                  </div>
                  <Badge label={q.category} color={CATEGORY_COLOR[q.category] || T.textSm} />
                </div>
                {q.advice && (
                  <div style={{ fontSize: 12, color: T.textMd, fontFamily: fontSans, lineHeight: 1.55 }}>{q.advice}</div>
                )}
              </div>
            ))}
          </div>

          <div>
            <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginBottom: 6 }}>Заметки по итогам встречи</div>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Запишите ключевые договорённости и наблюдения…"
              style={{
                width: '100%', minHeight: 80, padding: '8px 12px',
                background: T.bg, border: `1px solid ${T.border}`, borderRadius: 8,
                color: T.text, fontFamily: fontSans, fontSize: 13, resize: 'vertical',
                boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 6 }}>
              <Btn onClick={saveNotes} disabled={saving}>{saving ? 'Сохраняю…' : 'Сохранить'}</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Анализ нагрузки ───────────────────────────────────────────────────────────

const LOAD_LEVEL_META = {
  low:      { label: 'Низкая',   color: T.green,    bg: `${T.green}18`    },
  medium:   { label: 'Средняя',  color: T.accentLt, bg: `${T.accentLt}18` },
  high:     { label: 'Высокая',  color: T.amber,    bg: `${T.amber}18`    },
  overload: { label: 'Перегруз', color: T.red,      bg: `${T.red}18`      },
}
const EFF_LEVEL_META = {
  low:    { label: 'Низкая',   color: T.red    },
  medium: { label: 'Средняя',  color: T.amber  },
  high:   { label: 'Высокая',  color: T.green  },
}
const RISK_COLOR = { low: T.green, medium: T.amber, high: T.red }
const CONFIDENCE_LABEL = { low: 'низкая', medium: 'средняя', high: 'высокая' }

function GaugeBar({ value, color, label, sublabel }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: T.text, fontFamily: fontSans }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: font }}>{value.toFixed(0)}%</span>
      </div>
      <div style={{ height: 8, borderRadius: 5, background: T.border, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min(100, Math.max(0, value))}%`, background: color, borderRadius: 5, transition: 'width 0.6s ease' }} />
      </div>
      {sublabel && <div style={{ fontSize: 10, color: T.textSm, fontFamily: font, marginTop: 3 }}>{sublabel}</div>}
    </div>
  )
}

function EfficiencyPanel({ devId }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    setLoading(true); setError(null)
    api.get(`/developers/${devId}/capacity-analysis?weeks=16`)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e?.message || 'Ошибка'); setLoading(false) })
  }, [devId])

  if (loading) return <div style={{ padding: 48, display: 'flex', justifyContent: 'center' }}><Spinner /></div>
  if (error || !data) return <EmptyState icon="◎" text="Нет данных для анализа. Запустите синхронизацию." />

  const lvl = LOAD_LEVEL_META[data.current_load_level] || LOAD_LEVEL_META.medium
  const eff = EFF_LEVEL_META[data.efficiency_level]    || EFF_LEVEL_META.medium
  const sensColor = data.quality_sensitivity < -0.3 ? T.red : data.quality_sensitivity > 0.3 ? T.green : T.textMd
  const sensLabel = data.quality_sensitivity < -0.3 ? 'падает под нагрузкой' :
                    data.quality_sensitivity >  0.3 ? 'растёт под нагрузкой' : 'стабильно'

  const chartData = data.weekly.map(w => ({
    week:         w.week.slice(5),
    'Нагрузка %': w.load_pct,
    'Качество':   w.quality,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Строка 1: Индекс эффективности + Нагрузка + Резерв ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr 1fr', gap: 14 }}>

        {/* Индекс эффективности — главная карточка */}
        <Card style={{ border: `1px solid ${eff.color}40` }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.textSm, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Индекс эффективности
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
            <div style={{
              width: 72, height: 72, borderRadius: '50%', flexShrink: 0,
              background: `${eff.color}15`, border: `3px solid ${eff.color}`,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: eff.color, fontFamily: font, lineHeight: 1 }}>
                {data.efficiency_index.toFixed(0)}
              </div>
              <div style={{ fontSize: 9, color: eff.color, fontFamily: font }}>/ 100</div>
            </div>
            <div>
              <div style={{
                fontSize: 13, fontWeight: 700, color: eff.color, fontFamily: fontSans,
                background: `${eff.color}14`, border: `1px solid ${eff.color}40`,
                borderRadius: 6, padding: '3px 10px', display: 'inline-block', marginBottom: 6,
              }}>{eff.label}</div>
              <div style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>
                {data.efficiency_delta >= 0
                  ? `↑ +${data.efficiency_delta.toFixed(1)} пт. выше нормы`
                  : `↓ ${data.efficiency_delta.toFixed(1)} пт. ниже нормы`}
              </div>
            </div>
          </div>
          <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, lineHeight: 1.5 }}>
            Качество / нагрузка относительно личного baseline. 50 = работает строго по норме.
          </div>
        </Card>

        {/* Нагрузка */}
        <Card>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.textSm, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Текущая нагрузка
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: '50%', flexShrink: 0,
              background: lvl.bg, border: `2px solid ${lvl.color}`,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ fontSize: 16, fontWeight: 800, color: lvl.color, fontFamily: font, lineHeight: 1 }}>
                {data.current_load_pct.toFixed(0)}
              </div>
              <div style={{ fontSize: 8, color: lvl.color, fontFamily: font }}>%</div>
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: lvl.color, fontFamily: fontSans }}>{lvl.label}</div>
              <div style={{ fontSize: 10, color: T.textSm, fontFamily: font }}>от личного максимума</div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <GaugeBar value={data.current_load_pct} color={lvl.color} label="Нагрузка сейчас" sublabel={`${data.weeks_analyzed} нед. истории`} />
            <GaugeBar value={data.peak_sustainable_pct} color={T.green} label="Устойчивый потолок" sublabel="без потери качества" />
          </div>
          {data.already_overworked && (
            <div style={{ marginTop: 10, padding: '6px 10px', borderRadius: 6, background: `${T.red}12`, border: `1px solid ${T.red}40`, fontSize: 11, color: T.red, fontFamily: fontSans }}>
              ⚠ Работает сверхурочно
            </div>
          )}
        </Card>

        {/* Резерв / рекомендация */}
        <Card>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.textSm, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Можно добавить задачи?
          </div>

          {/* Два независимых критерия */}
          {(() => {
            const headroomOk = data.headroom_pct >= 10
            const wipOk      = !data.wip_overloaded && !data.already_overworked
            const finalOk    = data.can_take_more

            const criteria = [
              {
                label: 'По нагрузке',
                ok: headroomOk,
                detail: headroomOk
                  ? `запас ${data.headroom_pct.toFixed(0)}% до потолка`
                  : data.headroom_pct < 0
                    ? `превышение на ${Math.abs(data.headroom_pct).toFixed(0)}%`
                    : `запас всего ${data.headroom_pct.toFixed(0)}%`,
              },
              {
                label: 'По портфелю Jira',
                ok: wipOk,
                detail: wipOk
                  ? data.wip_task_count > 0
                    ? `${data.wip_task_count} задач в норме`
                    : 'WIP не превышен'
                  : data.already_overworked
                    ? 'работает сверхурочно'
                    : `WIP ${(data.wip_sp / Math.max(data.wip_avg_weekly_sp, 1)).toFixed(1)}× нормы`,
              },
            ]

            return (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 14 }}>
                  {criteria.map(c => (
                    <div key={c.label} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '9px 12px', borderRadius: 8,
                      background: c.ok ? `${T.green}10` : `${T.red}10`,
                      border: `1px solid ${c.ok ? T.green : T.red}35`,
                    }}>
                      <span style={{ fontSize: 14, color: c.ok ? T.green : T.red, flexShrink: 0 }}>
                        {c.ok ? '✓' : '✕'}
                      </span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: c.ok ? T.green : T.red, fontFamily: fontSans }}>{c.label}</div>
                        <div style={{ fontSize: 10, color: T.textMd, fontFamily: font, marginTop: 1 }}>{c.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Итог */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 14px', borderRadius: 8,
                  background: finalOk ? `${T.green}15` : `${T.red}15`,
                  border: `1px solid ${finalOk ? T.green : T.red}50`,
                  marginBottom: 12,
                }}>
                  <span style={{ fontSize: 18 }}>{finalOk ? '✓' : '✕'}</span>
                  <span style={{ fontSize: 13, fontWeight: 800, color: finalOk ? T.green : T.red, fontFamily: fontSans }}>
                    {finalOk ? 'Да, можно добавить задачи' : 'Нет — нельзя добавлять'}
                  </span>
                </div>
              </>
            )
          })()}

          <div style={{ fontSize: 10, color: T.textSm, fontFamily: font }}>
            Уверенность: {CONFIDENCE_LABEL[data.confidence]} · {data.weeks_analyzed} нед. данных
          </div>
        </Card>
      </div>

      {/* ── Прогноз на следующий спринт ── */}
      {data.sprint_scenarios?.length > 0 && (
        <Card>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, fontFamily: fontSans, marginBottom: 4 }}>
            Прогноз качества при увеличении нагрузки
          </div>
          <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginBottom: 16 }}>
            Линейная регрессия по {data.weeks_analyzed} неделям истории. Показывает ожидаемое quality_score при разных сценариях нагрузки.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${data.sprint_scenarios.length}, 1fr)`, gap: 10 }}>
            {data.sprint_scenarios.map((s, i) => {
              const rc = RISK_COLOR[s.risk] || T.textMd
              const isBase = i === 0
              return (
                <div key={i} style={{
                  padding: '14px 16px', borderRadius: 10,
                  background: isBase ? `${T.accentLt}10` : T.bg,
                  border: `1px solid ${isBase ? T.accentLt : rc}40`,
                  position: 'relative',
                }}>
                  {isBase && (
                    <div style={{ position: 'absolute', top: 8, right: 8, fontSize: 9, color: T.accentLt, fontFamily: font, fontWeight: 700 }}>СЕЙЧАС</div>
                  )}
                  <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginBottom: 8 }}>{s.label}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: rc, fontFamily: font, lineHeight: 1, marginBottom: 4 }}>
                    {s.predicted_quality.toFixed(0)}
                  </div>
                  <div style={{ fontSize: 10, color: T.textSm, fontFamily: font, marginBottom: 8 }}>ожид. качество</div>
                  <div style={{ height: 4, borderRadius: 2, background: T.border, overflow: 'hidden', marginBottom: 8 }}>
                    <div style={{ height: '100%', width: `${s.predicted_quality}%`, background: rc, borderRadius: 2 }} />
                  </div>
                  <div style={{ fontSize: 10, color: rc, fontFamily: font, fontWeight: 600 }}>
                    нагрузка {s.load_pct.toFixed(0)}% · риск {s.risk === 'low' ? 'низкий' : s.risk === 'medium' ? 'средний' : 'высокий'}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* ── График: нагрузка vs качество ── */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, fontFamily: fontSans }}>
            Динамика нагрузки и качества
          </div>
          <div style={{ fontSize: 11, fontFamily: font, color: sensColor, background: `${sensColor}14`, border: `1px solid ${sensColor}40`, borderRadius: 6, padding: '3px 10px' }}>
            Качество {sensLabel}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
            <XAxis dataKey="week" tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
            <YAxis domain={[0, 100]} tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
            <Tooltip content={<ChartTooltip />} />
            <Legend wrapperStyle={{ fontSize: 11, fontFamily: font }} />
            <ReferenceLine y={data.peak_sustainable_pct} stroke={T.green} strokeDasharray="4 2"
              label={{ value: 'потолок', fill: T.green, fontSize: 9, fontFamily: font, position: 'right' }} />
            <Line type="monotone" dataKey="Нагрузка %" stroke={T.amber}  dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="Качество"   stroke={T.purple} dot={false} strokeWidth={2} strokeDasharray="4 2" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* ── WIP Jira ── */}
      {data.wip_task_count > 0 ? (
        <Card style={{ border: `1px solid ${data.wip_overloaded ? T.red : T.border}55` }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.text, fontFamily: fontSans }}>Открытые задачи Jira (в работе сейчас)</div>
            {data.wip_overloaded && <span style={{ fontSize: 11, fontFamily: font, fontWeight: 700, color: T.red, background: `${T.red}14`, border: `1px solid ${T.red}40`, borderRadius: 6, padding: '3px 10px' }}>⚠ Перегружен</span>}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
            {[
              { label: 'Открытых задач',       value: data.wip_task_count,                                                                 suffix: '',    color: T.text,                                    sub: 'статус не Done' },
              { label: 'Story Points в работе', value: data.wip_sp.toFixed(0),                                                              suffix: ' SP', color: data.wip_overloaded ? T.red : T.amber,    sub: `норма ≈ ${data.wip_avg_weekly_sp.toFixed(0)} SP/нед.` },
              { label: 'Кратность нормы',       value: data.wip_avg_weekly_sp > 0 ? (data.wip_sp / data.wip_avg_weekly_sp).toFixed(1) : '—', suffix: '×',  color: data.wip_overloaded ? T.red : T.green,    sub: data.wip_overloaded ? 'выше нормы в 2+ раза' : 'в пределах нормы' },
            ].map(({ label, value, suffix, color, sub }) => (
              <div key={label} style={{ padding: '12px 14px', borderRadius: 8, background: T.bg, border: `1px solid ${T.border}` }}>
                <div style={{ fontSize: 24, fontWeight: 800, color, fontFamily: font, lineHeight: 1 }}>{value}<span style={{ fontSize: 13 }}>{suffix}</span></div>
                <div style={{ fontSize: 11, color: T.textMd, fontFamily: fontSans, marginTop: 4 }}>{label}</div>
                <div style={{ fontSize: 10, color: T.textSm, fontFamily: font, marginTop: 2 }}>{sub}</div>
              </div>
            ))}
          </div>
        </Card>
      ) : (
        <div style={{ padding: '10px 14px', borderRadius: 8, background: T.surface, border: `1px solid ${T.border}`, fontSize: 12, color: T.textSm, fontFamily: font }}>
          Jira: открытых задач не найдено (или Jira не подключена)
        </div>
      )}

      {/* ── Что формирует нагрузку ── */}
      {data.top_load_drivers?.length > 0 && (
        <Card>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, fontFamily: fontSans, marginBottom: 4 }}>Что формирует нагрузку сейчас</div>
          <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginBottom: 14 }}>
            Метрики с наибольшим отклонением от личной нормы (адаптивные z-score веса)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.top_load_drivers.map((d, i) => {
              const isHigh = d.direction === 'выше нормы'
              const color  = isHigh ? T.amber : T.accentLt
              const barW   = Math.min(100, Math.abs(d.z_score) / 3 * 100)
              return (
                <div key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: T.text, fontFamily: fontSans }}>{d.metric}</span>
                    <span style={{ fontSize: 11, color, fontFamily: font, fontWeight: 600 }}>{isHigh ? '↑' : '↓'} {d.direction}</span>
                  </div>
                  <div style={{ height: 5, background: T.border, borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${barW}%`, background: color, borderRadius: 3, transition: 'width 0.4s ease' }} />
                  </div>
                  <div style={{ fontSize: 10, color: T.textSm, fontFamily: font, marginTop: 3 }}>
                    z = {d.z_score > 0 ? '+' : ''}{d.z_score.toFixed(2)} — отклонение от личной нормы
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}

// ── Основной компонент ────────────────────────────────────────────────────────

export default function DeveloperDetail({ devId, developers, teams, onEdit, onSync }) {
  const [scores,  setScores]  = useState([])
  const [daily,   setDaily]   = useState([])
  const [loading, setLoading] = useState(true)
  const [tab,     setTab]     = useState('overview')

  const dev  = developers.find(d => d.id === devId)
  const team = teams.find(t => t.id === dev?.team_id)

  useEffect(() => {
    if (!devId) return
    setLoading(true)
    Promise.all([
      api.get(`/developers/${devId}/scores?weeks=12`).catch(() => []),
      api.get(`/developers/${devId}/daily-metrics?days=90`).catch(() => []),
    ]).then(([s, d]) => { setScores(s); setDaily(d); setLoading(false) })
  }, [devId])

  if (!dev) return <div style={{ color: T.textSm, padding: 40 }}>Разработчик не найден</div>

  const latest = scores[scores.length - 1]
  const scoreLineData = scores.map(s => ({
    week:         s.week_start?.slice(5, 10),
    Общий:        +s.overall_score.toFixed(1),
    Поставка:     +s.delivery_score.toFixed(1),
    Качество:     +s.quality_score.toFixed(1),
    Коллаборация: +s.collaboration_score.toFixed(1),
  }))
  const radarData = latest ? [
    { subject: 'Поставка',     value: +latest.delivery_score.toFixed(1) },
    { subject: 'Качество',     value: +latest.quality_score.toFixed(1) },
    { subject: 'Коллаборация', value: +latest.collaboration_score.toFixed(1) },
  ] : []
  const actData = daily.slice(-21).map(d => ({
    день:    d.date?.slice(5, 10),
    Коммиты: d.commits_count,
    PR:      d.prs_merged,
    Ревью:   d.reviews_given,
    SP:      +d.story_points_delivered.toFixed(1),
  }))

  const TABS = [
    { id: 'overview',   label: 'Обзор' },
    { id: 'biweekly',   label: 'История (2 нед.)' },
    { id: 'workload',   label: 'Эффективность' },
    { id: 'prs',        label: 'Pull Requests' },
    { id: 'one_on_one', label: '1:1 Помощник' },
  ]

  return (
    <div style={{ animation: 'fadeIn 0.25s ease' }}>
      {/* Заголовок */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <Avatar name={dev.display_name} size={52} />
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text, fontFamily: fontSans }}>{dev.display_name}</h2>
            <div style={{ display: 'flex', gap: 8, marginTop: 5, flexWrap: 'wrap', alignItems: 'center' }}>
              {team && <Badge label={team.name} color={T.textMd} />}
              {dev.github_login    && <Badge label={`⌥ ${dev.github_login}`} color={T.purple} />}
              {dev.jira_account_id && <Badge label="✓ Jira" color={T.cyan} />}
              {dev.email && <span style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>{dev.email}</span>}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn onClick={() => onSync(dev)}>↻ Синхронизировать</Btn>
          <Btn onClick={() => onEdit(dev)}>Редактировать</Btn>
        </div>
      </div>

      {loading ? (
        <Card style={{ textAlign: 'center', padding: 48 }}><Spinner size={28} /></Card>
      ) : (
        <>
          {/* Вкладки */}
          <div style={{ display: 'flex', gap: 2, marginBottom: 16, background: T.surface, padding: 4, borderRadius: 10, border: `1px solid ${T.border}`, width: 'fit-content' }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                padding: '7px 16px', borderRadius: 8, border: 'none',
                fontSize: 12, fontWeight: 600, fontFamily: fontSans,
                background: tab === t.id ? T.accent : 'transparent',
                color: tab === t.id ? '#fff' : T.textMd, cursor: 'pointer',
              }}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            scores.length === 0 ? (
              <Card><EmptyState icon="📊" text="Нет данных о производительности. Запустите синхронизацию."
                action={<Btn variant="primary" onClick={() => onSync(dev)}>↻ Синхронизировать</Btn>} /></Card>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {latest && (
                  <Card>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: T.text, fontFamily: fontSans }}>Оценка за последнюю неделю</div>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        {latest.burnout_risk_level !== 'low' && <Badge label={`⚠ ${burnoutLabel[latest.burnout_risk_level]}`} color={burnoutColor[latest.burnout_risk_level]} />}
                        <ScoreRing value={latest.overall_score} size={60} stroke={6} />
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 1, background: T.border, borderRadius: 8, overflow: 'hidden' }}>
                      {[
                        { label: 'Поставка',     v: latest.delivery_score,      color: T.green  },
                        { label: 'Качество',     v: latest.quality_score,       color: T.purple },
                        { label: 'Коллаборация', v: latest.collaboration_score, color: T.amber  },
                      ].map(({ label, v, color }) => (
                        <div key={label} style={{ background: T.card, padding: '14px 8px', textAlign: 'center' }}>
                          <div style={{ fontSize: 24, fontWeight: 800, color, fontFamily: font }}>{v.toFixed(0)}</div>
                          <div style={{ fontSize: 10, color: T.textSm, marginTop: 3, textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: font }}>{label}</div>
                          <div style={{ margin: '6px auto 0', width: '60%', height: 3, borderRadius: 2, background: T.border }}>
                            <div style={{ height: '100%', width: `${v}%`, background: color, borderRadius: 2 }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                <Card>
                  <Section title="Карта активности (90 дней)">
                    <ActivityHeatmap daily={daily} devId={devId} devName={dev.display_name} />
                  </Section>
                </Card>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <Card>
                    <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Динамика оценок (12 недель)</div>
                    <ResponsiveContainer width="100%" height={190}>
                      <LineChart data={scoreLineData} margin={{ top: 0, right: 8, bottom: 0, left: -20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
                        <XAxis dataKey="week" tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                        <YAxis domain={[0, 100]} tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                        <Tooltip content={<ChartTooltip />} />
                        <ReferenceLine y={70} stroke={T.green} strokeDasharray="3 3" strokeOpacity={0.5} />
                        <Line type="monotone" dataKey="Общий"        stroke={T.accentLt} dot={false} strokeWidth={2.5} />
                        <Line type="monotone" dataKey="Поставка"     stroke={T.green}    dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                        <Line type="monotone" dataKey="Качество"     stroke={T.purple}   dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                        <Line type="monotone" dataKey="Коллаборация" stroke={T.amber}    dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                      </LineChart>
                    </ResponsiveContainer>
                  </Card>

                  <Card>
                    <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Профиль навыков</div>
                    <ResponsiveContainer width="100%" height={190}>
                      <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={68}>
                        <PolarGrid stroke={T.border} />
                        <PolarAngleAxis dataKey="subject" tick={{ fill: T.textSm, fontSize: 11, fontFamily: font }} />
                        <Radar name="Оценка" dataKey="value" stroke={T.accentLt} fill={T.accentLt} fillOpacity={0.2} strokeWidth={2} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </Card>
                </div>

                {daily.length > 0 && (
                  <Card>
                    <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Ежедневная активность (21 день)</div>
                    <ResponsiveContainer width="100%" height={160}>
                      <BarChart data={actData} margin={{ top: 0, right: 8, bottom: 0, left: -20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
                        <XAxis dataKey="день" tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                        <YAxis tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11, fontFamily: font, color: T.textSm }} />
                        <Bar dataKey="Коммиты" fill={T.accentLt} radius={[2,2,0,0]} maxBarSize={14} />
                        <Bar dataKey="PR"      fill={T.green}    radius={[2,2,0,0]} maxBarSize={14} />
                        <Bar dataKey="Ревью"   fill={T.purple}   radius={[2,2,0,0]} maxBarSize={14} />
                        <Bar dataKey="SP"      fill={T.amber}    radius={[2,2,0,0]} maxBarSize={14} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                )}

                {latest && latest.burnout_risk_level !== 'low' && (
                  <Card style={{ border: `1px solid ${burnoutColor[latest.burnout_risk_level]}55` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                      <span style={{ fontSize: 20 }}>⚠️</span>
                      <div style={{ fontSize: 14, fontWeight: 700, color: burnoutColor[latest.burnout_risk_level], fontFamily: fontSans }}>
                        Риск выгорания: {burnoutLabel[latest.burnout_risk_level].toUpperCase()}
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
                      {[
                        { label: 'Нерабочее время',  value: `${((latest.after_hours_ratio||0)*100).toFixed(0)}%`,       threshold: '> 20%' },
                        { label: 'Выходные дни',     value: `${((latest.weekend_activity_ratio||0)*100).toFixed(0)}%`, threshold: '> 10%' },
                        { label: 'Ср. часов в день', value: `${latest.avg_daily_active_hours?.toFixed(1) || '—'}ч`,    threshold: '> 9ч'  },
                      ].map(({ label, value, threshold }) => (
                        <div key={label} style={{ padding: '12px 14px', borderRadius: 8, background: T.bg, border: `1px solid ${T.border}` }}>
                          <div style={{ fontSize: 22, fontWeight: 800, color: T.text, fontFamily: font }}>{value}</div>
                          <div style={{ fontSize: 10, color: T.textSm, marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: font }}>{label}</div>
                          <div style={{ fontSize: 10, color: T.amber, marginTop: 2 }}>порог {threshold}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            )
          )}

          {tab === 'biweekly' && (
            <div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text, fontFamily: fontSans, marginBottom: 4 }}>
                  История по двухнедельным периодам
                </div>
                <div style={{ fontSize: 12, color: T.textSm, fontFamily: font }}>
                  Усреднённые показатели за каждые 2 недели. Δ — изменение общего score относительно предыдущего периода.
                </div>
              </div>
              <BiWeeklyHistory devId={devId} />
            </div>
          )}

          {tab === 'workload' && (
            <EfficiencyPanel devId={devId} />
          )}

          {tab === 'prs' && (
            <Card>
              <div style={{ fontSize: 14, fontWeight: 700, color: T.text, fontFamily: fontSans, marginBottom: 4 }}>Pull Requests</div>
              <div style={{ fontSize: 12, color: T.textSm, fontFamily: font, marginBottom: 16 }}>
                Оценка качества и сложности по метрикам PR
              </div>
              <PRList devId={devId} days={60} />
            </Card>
          )}

          {tab === 'one_on_one' && (
            <Card>
              <div style={{ fontSize: 14, fontWeight: 700, color: T.text, fontFamily: fontSans, marginBottom: 4 }}>1:1 Помощник</div>
              <div style={{ fontSize: 12, color: T.textSm, fontFamily: font, marginBottom: 16 }}>
                Вопросы для встречи генерируются на основе risk score и метрик разработчика
              </div>
              <OneOnOnePanel devId={devId} />
            </Card>
          )}
        </>
      )}
    </div>
  )
}
