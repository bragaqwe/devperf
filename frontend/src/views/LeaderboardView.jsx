import { useState, useEffect } from 'react'
import { api } from '../api'
import { T, font, fontSans } from '../tokens'
import { Card, Badge, Spinner, EmptyState } from '../components/UI'

const GRADE_COLORS = {
  junior: '#64748b', middle: '#3b82f6', senior: '#8b5cf6', staff: '#f59e0b', lead: '#ef4444',
}
const GRADE_LABELS = {
  junior: 'Junior', middle: 'Middle', senior: 'Senior', staff: 'Staff', lead: 'Lead',
}
const RISK_COLORS = { low: '#10b981', medium: '#f59e0b', high: '#ef4444' }
const RISK_LABELS = { low: 'Норма', medium: 'Внимание', high: 'Высокий' }

function MetricBar({ label, value, max = 100, color = T.accentLt }) {
  const pct = Math.max(0, Math.min(100, ((value ?? 0) / max) * 100))
  return (
    <div style={{ flex: 1, minWidth: 72 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 10, color: T.textSm, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: font }}>{value?.toFixed(0) ?? '—'}</span>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: T.border }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
    </div>
  )
}

function MomentumBadge({ value }) {
  const pct   = Math.round((value ?? 0) * 100)
  const pos   = pct >= 0
  const color = pct >= 10 ? '#10b981' : pct >= -10 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 68 }}>
      <span style={{ fontSize: 18, fontWeight: 800, color, fontFamily: font, lineHeight: 1 }}>
        {pos ? '+' : ''}{pct}%
      </span>
      <span style={{ fontSize: 9, color: T.textSm, fontFamily: font, textTransform: 'uppercase', marginTop: 2 }}>Динамика</span>
    </div>
  )
}

export default function PerformanceView({ teams, onSelectDev }) {
  const [tab,       setTab]       = useState('metrics')  // metrics | attrition | burnout
  const [sel,       setSel]       = useState('all')
  const [metrics,   setMetrics]   = useState([])
  const [attrition, setAttrition] = useState([])
  const [burnout,   setBurnout]   = useState([])
  const [loading,   setLoading]   = useState(true)

  const teamMap = Object.fromEntries(teams.map(t => [t.id, t]))

  useEffect(() => {
    setLoading(true)
    const q = sel === 'all' ? '' : `?team_id=${sel}`
    Promise.all([
      api.get(`/leaderboard${q}`).catch(() => []),
      api.get(`/attrition/alerts${q}`).catch(() => []),
      api.get(`/burnout/alerts${q}`).catch(() => []),
    ]).then(([lb, at, bu]) => {
      setMetrics(lb); setAttrition(at); setBurnout(bu)
      setLoading(false)
    })
  }, [sel])

  const TABS = [
    { id: 'metrics',   label: 'Показатели эффективности', count: metrics.length },
    { id: 'attrition', label: 'Риск увольнения',          count: attrition.filter(a => a.attrition_risk_level !== 'low').length, alert: attrition.some(a => a.attrition_risk_level === 'high') },
    { id: 'burnout',   label: 'Выгорание',                count: burnout.length, alert: burnout.some(b => b.burnout_risk_level === 'high') },
  ]

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text, fontFamily: fontSans }}>Аналитика команды</h2>
          <div style={{ fontSize: 12, color: T.textSm, marginTop: 2 }}>Метрики эффективности, риски выгорания и увольнения</div>
        </div>
        <select value={sel} onChange={e => setSel(e.target.value)}
          style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 12, fontFamily: font, outline: 'none', cursor: 'pointer' }}>
          <option value="all">Все команды</option>
          {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 16, borderBottom: `1px solid ${T.border}` }}>
        {TABS.map(t => {
          const active = tab === t.id
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              style={{ padding: '8px 16px', border: 'none', cursor: 'pointer', fontFamily: fontSans, fontSize: 13,
                fontWeight: active ? 600 : 400,
                color: active ? T.accentLt : t.alert ? '#f59e0b' : T.textMd,
                background: 'transparent',
                borderBottom: active ? `2px solid ${T.accentLt}` : '2px solid transparent',
                marginBottom: -1, transition: 'all 0.15s', whiteSpace: 'nowrap' }}>
              {t.label}
              {t.count > 0 && (
                <span style={{ marginLeft: 6, padding: '1px 6px', borderRadius: 10, fontSize: 11,
                  background: t.alert ? '#ef444420' : T.border,
                  color: t.alert ? '#ef4444' : T.textSm }}>
                  {t.count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {loading ? (
        <Card style={{ textAlign: 'center', padding: 48 }}><Spinner size={28} /></Card>
      ) : (
        <>
          {/* ── ПОКАЗАТЕЛИ ЭФФЕКТИВНОСТИ ── */}
          {tab === 'metrics' && (
            metrics.length === 0
              ? <Card><EmptyState icon="📊" text="Нет данных — загрузите демо-данные или синхронизируйте разработчиков." /></Card>
              : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {metrics.map(row => (
                    <Card key={row.developer_id}
                      style={{ padding: '16px 20px', cursor: onSelectDev ? 'pointer' : 'default' }}
                      onClick={() => onSelectDev && onSelectDev(row.developer_id)}>
                      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

                        {/* Имя + мета */}
                        <div style={{ minWidth: 180, flexShrink: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                            <span style={{ fontSize: 15, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{row.display_name}</span>
                          </div>
                          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                            {row.grade && (
                              <span style={{ padding: '2px 7px', borderRadius: 10, fontSize: 10, fontWeight: 700, fontFamily: fontSans,
                                background: (GRADE_COLORS[row.grade] || T.textSm) + '20',
                                color: GRADE_COLORS[row.grade] || T.textSm }}>
                                {GRADE_LABELS[row.grade] || row.grade}
                              </span>
                            )}
                            {row.team_id && teamMap[row.team_id] && (
                              <Badge label={teamMap[row.team_id].name} color={T.textSm} size="xs" />
                            )}
                          </div>
                          {row.github_login && (
                            <div style={{ fontSize: 11, color: T.textSm, marginTop: 5, fontFamily: font }}>@{row.github_login}</div>
                          )}
                        </div>

                        {/* Динамика */}
                        <MomentumBadge value={row.momentum} />

                        {/* Метрики — полосы */}
                        <div style={{ flex: 1, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
                          <MetricBar label="Отклик PR"    value={row.responsiveness_score}   color={T.accentLt} />
                          <MetricBar label="Скорость"     value={row.task_velocity_score}    color='#8b5cf6' />
                          <MetricBar label="Вовлечённость" value={row.engagement_depth_score} color='#10b981' />
                          <MetricBar label="Код"          value={row.code_health_score}      color='#f59e0b' />
                          <MetricBar label="Ритм"         value={row.rhythm_score}           color='#06b6d4' />
                        </div>

                        {/* Риск-бейджи (только если не low) */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0, minWidth: 80 }}>
                          {row.attrition_risk_level && row.attrition_risk_level !== 'low' && (
                            <span style={{ padding: '3px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                              background: RISK_COLORS[row.attrition_risk_level] + '20',
                              color: RISK_COLORS[row.attrition_risk_level], fontFamily: fontSans, whiteSpace: 'nowrap' }}>
                              ⚑ Риск увольнения
                            </span>
                          )}
                          {row.burnout_risk_level && row.burnout_risk_level !== 'low' && (
                            <span style={{ padding: '3px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                              background: RISK_COLORS[row.burnout_risk_level] + '20',
                              color: RISK_COLORS[row.burnout_risk_level], fontFamily: fontSans, whiteSpace: 'nowrap' }}>
                              ◷ Выгорание
                            </span>
                          )}
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )
          )}

          {/* ── РИСК УВОЛЬНЕНИЯ ── */}
          {tab === 'attrition' && (
            attrition.filter(a => a.attrition_risk_level !== 'low').length === 0
              ? <Card><EmptyState icon="✓" text="Нет алертов о риске увольнения." /></Card>
              : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {attrition.filter(a => a.attrition_risk_level !== 'low').map(alert => (
                    <Card key={alert.developer_id}
                      style={{ borderLeft: `3px solid ${RISK_COLORS[alert.attrition_risk_level]}`, cursor: onSelectDev ? 'pointer' : 'default' }}
                      onClick={() => onSelectDev && onSelectDev(alert.developer_id)}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                            <span style={{ fontSize: 15, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{alert.developer_name}</span>
                            {alert.grade && (
                              <span style={{ padding: '1px 7px', borderRadius: 10, fontSize: 10, fontWeight: 700, fontFamily: fontSans,
                                background: (GRADE_COLORS[alert.grade] || T.textSm) + '20',
                                color: GRADE_COLORS[alert.grade] || T.textSm }}>
                                {GRADE_LABELS[alert.grade] || alert.grade}
                              </span>
                            )}
                          </div>
                          <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
                            background: RISK_COLORS[alert.attrition_risk_level] + '20',
                            color: RISK_COLORS[alert.attrition_risk_level], fontFamily: fontSans }}>
                            {RISK_LABELS[alert.attrition_risk_level]} · {(alert.attrition_risk_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, flexShrink: 0 }}>
                          {new Date(alert.week_start).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                        </div>
                      </div>

                      {alert.signals?.length > 0 && (
                        <div>
                          <div style={{ fontSize: 10, fontWeight: 700, color: T.textSm, textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: font, marginBottom: 6 }}>Сигналы</div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                            {alert.signals.map((s, i) => (
                              <div key={i} style={{ display: 'flex', gap: 7, fontSize: 12, color: T.textMd, fontFamily: font }}>
                                <span style={{ color: RISK_COLORS[alert.attrition_risk_level], flexShrink: 0 }}>→</span>
                                <span>{s}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              )
          )}

          {/* ── ВЫГОРАНИЕ ── */}
          {tab === 'burnout' && (
            burnout.length === 0
              ? <Card><EmptyState icon="✓" text="Нет алертов о выгорании." /></Card>
              : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {burnout.map(alert => (
                    <Card key={alert.developer_id}
                      style={{ borderLeft: `3px solid ${RISK_COLORS[alert.burnout_risk_level]}`, cursor: onSelectDev ? 'pointer' : 'default' }}
                      onClick={() => onSelectDev && onSelectDev(alert.developer_id)}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                            <span style={{ fontSize: 15, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{alert.developer_name}</span>
                            {alert.grade && (
                              <span style={{ padding: '1px 7px', borderRadius: 10, fontSize: 10, fontWeight: 700, fontFamily: fontSans,
                                background: (GRADE_COLORS[alert.grade] || T.textSm) + '20',
                                color: GRADE_COLORS[alert.grade] || T.textSm }}>
                                {GRADE_LABELS[alert.grade] || alert.grade}
                              </span>
                            )}
                          </div>
                          <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
                            background: RISK_COLORS[alert.burnout_risk_level] + '20',
                            color: RISK_COLORS[alert.burnout_risk_level], fontFamily: fontSans }}>
                            Выгорание · {RISK_LABELS[alert.burnout_risk_level]}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>
                          {new Date(alert.week_start).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                        </div>
                      </div>

                      {/* Ключевые индикаторы выгорания */}
                      <div style={{ display: 'flex', gap: 24 }}>
                        {[
                          { l: 'Работа вне рабочих часов', v: `${(alert.after_hours_ratio * 100).toFixed(0)}%`, threshold: 0.3 },
                          { l: 'Активность в выходные',    v: `${(alert.weekend_activity_ratio * 100).toFixed(0)}%`, threshold: 0.25 },
                          { l: 'Активных часов/день',      v: alert.avg_daily_active_hours?.toFixed(1) ?? '—', threshold: null },
                        ].map(({ l, v, threshold }) => (
                          <div key={l}>
                            <div style={{ fontSize: 15, fontWeight: 800, color: T.text, fontFamily: font }}>{v}</div>
                            <div style={{ fontSize: 10, color: T.textSm, textTransform: 'uppercase', fontFamily: font, marginTop: 2 }}>{l}</div>
                          </div>
                        ))}
                      </div>
                    </Card>
                  ))}
                </div>
              )
          )}
        </>
      )}
    </div>
  )
}
