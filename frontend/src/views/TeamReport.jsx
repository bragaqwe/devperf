import { useState, useEffect } from 'react'
import {
  LineChart, Line, BarChart, Bar, ResponsiveContainer,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from 'recharts'
import { api } from '../api'
import { T, font, fontSans, scoreColor, burnoutColor, burnoutLabel } from '../tokens'
import { Card, Badge, Btn, Spinner, ScoreRing, ChartTooltip, Avatar, Section, EmptyState } from '../components/UI'

const PERIODS = [
  { label: '2 нед.', days: 14 },
  { label: '1 мес.',  days: 30 },
  { label: '3 мес.',  days: 90 },
]
const TABS = [
  { id: 'overview', label: 'Обзор'   },
  { id: 'members',  label: 'Участники' },
  { id: 'trend',    label: 'Тренды'  },
  { id: 'risk',     label: 'Риски'   },
]

function MemberRow({ m, onSelect }) {
  const bColor = burnoutColor[m.burnout_risk_level]
  return (
    <div onClick={() => onSelect(m.developer.id)}
      style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderBottom: `1px solid ${T.border}`, cursor: 'pointer' }}
      onMouseEnter={e => e.currentTarget.style.background = T.cardHov}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <Avatar name={m.developer.display_name} size={34} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: fontSans }}>{m.developer.display_name}</div>
        <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginTop: 2 }}>
          {m.developer.github_login ? `@${m.developer.github_login}` : ''}
          {m.developer.github_login && m.developer.jira_account_id ? ' · ' : ''}
          {m.developer.jira_account_id ? 'Jira ✓' : ''}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
        {[
          { l: 'Пост.', v: m.delivery_score,      c: T.green  },
          { l: 'Кач.',  v: m.quality_score,        c: T.purple },
          { l: 'Колл.', v: m.collaboration_score,  c: T.amber  },
        ].map(({ l, v, c }) => (
          <div key={l} style={{ textAlign: 'center', width: 36 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: c, fontFamily: font }}>{v.toFixed(0)}</div>
            <div style={{ fontSize: 9, color: T.textSm, textTransform: 'uppercase', fontFamily: font }}>{l}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 110 }}>
        <span style={{ fontSize: 11, color: T.accentLt, fontFamily: font }}>⌥{m.commits_last_week}</span>
        <span style={{ fontSize: 11, color: T.green,    fontFamily: font }}>↑{m.prs_last_week}</span>
        <span style={{ fontSize: 11, color: T.amber,    fontFamily: font }}>◎{m.sp_last_week.toFixed(0)}</span>
      </div>
      <Badge label={burnoutLabel[m.burnout_risk_level] || m.burnout_risk_level} color={bColor} />
      <ScoreRing value={m.overall_score} size={42} stroke={4} />
      <span style={{ fontSize: 11, color: T.textSm }}>→</span>
    </div>
  )
}

function RiskMatrix({ members }) {
  const toX = v => ((Math.max(-20, Math.min(20, v)) + 20) / 40) * 100
  const toY = v => (1 - Math.max(0, Math.min(1, v))) * 100
  return (
    <div style={{ position: 'relative', width: '100%', height: 240, background: T.bg, borderRadius: 8, border: `1px solid ${T.border}`, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: T.border }} />
      <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1, background: T.border }} />
      <div style={{ position: 'absolute', left: '2%', top: '2%',    fontSize: 9, color: T.green,    fontFamily: font }}>🌟 Высокая эффективность, низкий риск</div>
      <div style={{ position: 'absolute', right: '2%', top: '2%',   fontSize: 9, color: T.amber,    fontFamily: font, textAlign: 'right' }}>⚠ Высокая эффективность, риск выгорания</div>
      <div style={{ position: 'absolute', left: '2%', bottom: '2%', fontSize: 9, color: T.accentLt, fontFamily: font }}>📈 Растёт, низкий риск</div>
      <div style={{ position: 'absolute', right: '2%', bottom: '2%',fontSize: 9, color: T.red,      fontFamily: font, textAlign: 'right' }}>🚨 Низкая эффективность + выгорание</div>
      <div style={{ position: 'absolute', bottom: '44%', left: '2%', fontSize: 9, color: T.textSm, fontFamily: font }}>← Снижение</div>
      <div style={{ position: 'absolute', bottom: '44%', right: '2%',fontSize: 9, color: T.textSm, fontFamily: font }}>Рост →</div>
      {members.map(m => (
        <div key={m.developer.id} title={`${m.developer.display_name}: ${m.overall_score.toFixed(0)}`}
          style={{ position: 'absolute', left: `${toX(m.velocity_trend)}%`, top: `${toY(m.burnout_risk_score)}%`, transform: 'translate(-50%,-50%)', width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg,#2563eb,#8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#fff', border: `2px solid ${burnoutColor[m.burnout_risk_level]}`, cursor: 'default', zIndex: 2 }}>
          {m.developer.display_name.charAt(0)}
        </div>
      ))}
    </div>
  )
}

export default function TeamReportView({ teamId, teams, onSelectDev }) {
  const [report,  setReport]  = useState(null)
  const [loading, setLoading] = useState(true)
  const [period,  setPeriod]  = useState(30)
  const [tab,     setTab]     = useState('overview')
  const team = teams.find(t => t.id === teamId)

  const load = () => {
    setLoading(true)
    api.get(`/teams/${teamId}/report?period_days=${period}`)
      .then(r => { setReport(r); setLoading(false) })
      .catch(() => setLoading(false))
  }
  useEffect(() => { load() }, [teamId, period])

  if (!team) return null

  return (
    <div style={{ animation: 'fadeIn 0.25s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text, fontFamily: fontSans }}>{team.name}</h2>
            <Badge label="Отчёт команды" color={T.accentLt} />
          </div>
          <div style={{ fontSize: 12, color: T.textSm, marginTop: 3, fontFamily: font }}>
            {team.jira_project_key && `Jira: ${team.jira_project_key}`}
            {team.jira_project_key && team.github_org ? ' · ' : ''}
            {team.github_org && `GitHub: ${team.github_org}`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 2, background: T.surface, padding: 3, borderRadius: 8, border: `1px solid ${T.border}` }}>
            {PERIODS.map(p => (
              <button key={p.days} onClick={() => setPeriod(p.days)} style={{ padding: '5px 10px', borderRadius: 6, border: 'none', fontSize: 11, fontFamily: font, background: period === p.days ? T.accent : 'transparent', color: period === p.days ? '#fff' : T.textMd, cursor: 'pointer' }}>
                {p.label}
              </button>
            ))}
          </div>
          <Btn small onClick={load}>↻</Btn>
        </div>
      </div>

      {loading ? <Card style={{ textAlign: 'center', padding: 48 }}><Spinner size={28} /></Card>
      : !report ? <Card><EmptyState icon="📋" text="Не удалось загрузить отчёт." /></Card>
      : (
        <>
          {/* KPI */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 1, background: T.border, borderRadius: 10, overflow: 'hidden', marginBottom: 20 }}>
            {[
              { label: 'Ср. оценка',   v: report.avg_overall_score.toFixed(1), color: scoreColor(report.avg_overall_score) },
              { label: 'Участники',    v: report.members.length,               color: T.text    },
              { label: 'Коммиты',      v: report.total_commits,                color: T.accentLt },
              { label: 'PR влито',     v: report.total_prs_merged,             color: T.green   },
              { label: 'Story Points', v: report.total_sp,                     color: T.amber   },
              { label: 'Под риском',   v: report.burnout_alerts.length,        color: report.burnout_alerts.length > 0 ? T.red : T.green },
            ].map(({ label, v, color }) => (
              <div key={label} style={{ background: T.card, padding: '16px 8px', textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 800, color, fontFamily: font }}>{v}</div>
                <div style={{ fontSize: 9, color: T.textSm, marginTop: 3, textTransform: 'uppercase', letterSpacing: '0.07em', fontFamily: font }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Highlights */}
          {(report.top_performer || report.most_at_risk || report.burnout_alerts.length > 0) && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 16 }}>
              {report.top_performer && (
                <Card style={{ padding: '14px 16px', border: `1px solid ${T.green}33`, background: T.greenDim }}>
                  <div style={{ fontSize: 10, color: T.green, textTransform: 'uppercase', fontFamily: font, letterSpacing: '0.07em', marginBottom: 6 }}>🌟 Лучший</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{report.top_performer}</div>
                </Card>
              )}
              {report.most_at_risk && (
                <Card style={{ padding: '14px 16px', border: `1px solid ${T.red}33`, background: T.redDim }}>
                  <div style={{ fontSize: 10, color: T.red, textTransform: 'uppercase', fontFamily: font, letterSpacing: '0.07em', marginBottom: 6 }}>🚨 Риск выгорания</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{report.most_at_risk}</div>
                </Card>
              )}
              {report.burnout_alerts.length > 0 && (
                <Card style={{ padding: '14px 16px', border: `1px solid ${T.amber}33`, background: T.amberDim }}>
                  <div style={{ fontSize: 10, color: T.amber, textTransform: 'uppercase', fontFamily: font, letterSpacing: '0.07em', marginBottom: 6 }}>⚠ Предупреждения ({report.burnout_alerts.length})</div>
                  <div style={{ fontSize: 13, color: T.text, fontFamily: fontSans }}>{report.burnout_alerts.slice(0, 3).join(', ')}{report.burnout_alerts.length > 3 ? ` +${report.burnout_alerts.length - 3}` : ''}</div>
                </Card>
              )}
            </div>
          )}

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 2, marginBottom: 16, background: T.surface, padding: 4, borderRadius: 10, border: `1px solid ${T.border}`, width: 'fit-content' }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{ padding: '7px 16px', borderRadius: 8, border: 'none', fontSize: 12, fontWeight: 600, fontFamily: fontSans, background: tab === t.id ? T.accent : 'transparent', color: tab === t.id ? '#fff' : T.textMd, cursor: 'pointer' }}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Card>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Оценки участников</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {report.members.map(m => (
                    <div key={m.developer.id} onClick={() => onSelectDev(m.developer.id)}
                      style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
                      <div style={{ width: 110, fontSize: 12, color: T.textMd, fontFamily: fontSans, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'right', flexShrink: 0 }}>
                        {m.developer.display_name}
                      </div>
                      <div style={{ flex: 1, height: 20, borderRadius: 4, background: T.border, overflow: 'hidden', position: 'relative' }}>
                        <div style={{ height: '100%', width: `${m.overall_score}%`, background: `linear-gradient(90deg, ${scoreColor(m.overall_score)}88, ${scoreColor(m.overall_score)})`, borderRadius: 4, transition: 'width 0.5s ease' }} />
                        <span style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', fontSize: 11, fontWeight: 700, fontFamily: font, color: T.text }}>{m.overall_score.toFixed(0)}</span>
                      </div>
                      <Badge label={burnoutLabel[m.burnout_risk_level] || m.burnout_risk_level} color={burnoutColor[m.burnout_risk_level]} size="xs" />
                    </div>
                  ))}
                </div>
              </Card>
              {report.members.length > 0 && (
                <Card>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Активность за последние 7 дней</div>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={report.members.map(m => ({ name: m.developer.display_name.split(' ')[0], Коммиты: m.commits_last_week, PR: m.prs_last_week, SP: +m.sp_last_week.toFixed(0) }))} margin={{ top: 0, right: 8, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
                      <XAxis dataKey="name" tick={{ fill: T.textSm, fontSize: 11, fontFamily: font }} />
                      <YAxis tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 11, fontFamily: font, color: T.textSm }} />
                      <Bar dataKey="Коммиты" fill={T.accentLt} radius={[3,3,0,0]} />
                      <Bar dataKey="PR"      fill={T.green}    radius={[3,3,0,0]} />
                      <Bar dataKey="SP"      fill={T.amber}    radius={[3,3,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Card>
              )}
            </div>
          )}

          {tab === 'members' && (
            <Card style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '14px 16px', borderBottom: `1px solid ${T.border}`, display: 'flex', gap: 8 }}>
                <span style={{ fontSize: 11, color: T.textSm, fontFamily: font, flex: 1 }}>РАЗРАБОТЧИК</span>
                <span style={{ fontSize: 11, color: T.textSm, fontFamily: font, width: 180, textAlign: 'center' }}>ПОСТ / КАЧ / КОЛЛ</span>
                <span style={{ fontSize: 11, color: T.textSm, fontFamily: font, width: 110, textAlign: 'center' }}>ПРОШЛ. НЕДЕЛЯ</span>
                <span style={{ fontSize: 11, color: T.textSm, fontFamily: font, width: 60,  textAlign: 'center' }}>РИСК</span>
                <span style={{ fontSize: 11, color: T.textSm, fontFamily: font, width: 42,  textAlign: 'center' }}>ОЦЕНКА</span>
              </div>
              {report.members.length === 0
                ? <EmptyState icon="👥" text="Нет участников с данными." />
                : report.members.map(m => <MemberRow key={m.developer.id} m={m} onSelect={onSelectDev} />)
              }
            </Card>
          )}

          {tab === 'trend' && report.weekly_trend.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Card>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Динамика оценок команды</div>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={report.weekly_trend.map(w => ({ week: w.week_start.slice(5,10), 'Ср. оценка': +w.avg_overall_score.toFixed(1), Поставка: +w.avg_delivery_score.toFixed(1), Качество: +w.avg_quality_score.toFixed(1), Коллаборация: +w.avg_collab_score.toFixed(1) }))} margin={{ top: 0, right: 8, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
                    <XAxis dataKey="week" tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                    <YAxis domain={[0,100]} tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                    <Tooltip content={<ChartTooltip />} />
                    <Line type="monotone" dataKey="Ср. оценка"    stroke={T.accentLt} dot={false} strokeWidth={2.5} />
                    <Line type="monotone" dataKey="Поставка"      stroke={T.green}    dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                    <Line type="monotone" dataKey="Качество"      stroke={T.purple}   dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                    <Line type="monotone" dataKey="Коллаборация"  stroke={T.amber}    dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
              <Card>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Выпуск команды по неделям</div>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={report.weekly_trend.map(w => ({ week: w.week_start.slice(5,10), Коммиты: w.total_commits, PR: w.total_prs_merged, SP: +w.total_sp.toFixed(0) }))} margin={{ top: 0, right: 8, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
                    <XAxis dataKey="week" tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                    <YAxis tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
                    <Tooltip content={<ChartTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 11, fontFamily: font, color: T.textSm }} />
                    <Bar dataKey="Коммиты" fill={T.accentLt} radius={[3,3,0,0]} />
                    <Bar dataKey="PR"      fill={T.green}    radius={[3,3,0,0]} />
                    <Bar dataKey="SP"      fill={T.amber}    radius={[3,3,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </div>
          )}

          {tab === 'risk' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Card>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 6, fontFamily: fontSans }}>Матрица рисков</div>
                <div style={{ fontSize: 11, color: T.textSm, marginBottom: 14, fontFamily: font }}>X: динамика (рост → снижение) · Y: риск выгорания (вверх = низкий риск)</div>
                <RiskMatrix members={report.members} />
              </Card>
              <Card>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 14, fontFamily: fontSans }}>Сигналы выгорания</div>
                {report.members.filter(m => m.burnout_risk_level !== 'low').length === 0 ? (
                  <div style={{ color: T.green, fontSize: 13, fontFamily: font }}>✓ Признаков выгорания не обнаружено</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {report.members.filter(m => m.burnout_risk_level !== 'low').sort((a,b) => b.burnout_risk_score - a.burnout_risk_score).map(m => (
                      <div key={m.developer.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderRadius: 8, background: T.bg, border: `1px solid ${burnoutColor[m.burnout_risk_level]}33` }}>
                        <Avatar name={m.developer.display_name} size={32} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: fontSans }}>{m.developer.display_name}</div>
                        </div>
                        <Badge label={burnoutLabel[m.burnout_risk_level]} color={burnoutColor[m.burnout_risk_level]} />
                        <div style={{ fontSize: 12, color: T.textSm, fontFamily: font }}>
                          риск: <b style={{ color: burnoutColor[m.burnout_risk_level] }}>{(m.burnout_risk_score * 100).toFixed(0)}%</b>
                        </div>
                        <Btn small onClick={() => onSelectDev(m.developer.id)}>Профиль →</Btn>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}
