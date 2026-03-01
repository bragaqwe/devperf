import { useState, useEffect } from 'react'
import {
  LineChart, Line, BarChart, Bar, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, ResponsiveContainer,
  XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Legend,
} from 'recharts'
import { api } from '../api'
import { T, font, fontSans, scoreColor, burnoutColor, burnoutLabel } from '../tokens'
import { Card, Badge, Btn, Spinner, ScoreRing, ChartTooltip, Avatar, Section, EmptyState } from '../components/UI'
import DayTimeline from './DayTimeline'

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
              <div key={cell.key} title={`${cell.key}: ${cell.total} событий`}
                onClick={() => cell.total > 0 && setDrillDay(cell.key)}
                onMouseEnter={() => setHovDay(cell.key)}
                onMouseLeave={() => setHovDay(null)}
                style={{ width: 13, height: 13, borderRadius: 2, background: hovDay === cell.key ? T.accentLt : cellColor(cell.total), cursor: cell.total > 0 ? 'pointer' : 'default', transition: 'background 0.1s', border: hovDay === cell.key ? `1px solid ${T.accentLt}` : '1px solid transparent' }}
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

export default function DeveloperDetail({ devId, developers, teams, onEdit, onSync }) {
  const [scores,  setScores]  = useState([])
  const [daily,   setDaily]   = useState([])
  const [loading, setLoading] = useState(true)

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
    week:     s.week_start?.slice(5, 10),
    Общий:    +s.overall_score.toFixed(1),
    Поставка: +s.delivery_score.toFixed(1),
    Качество: +s.quality_score.toFixed(1),
    Коллаборация: +s.collaboration_score.toFixed(1),
  }))
  const radarData = latest ? [
    { subject: 'Поставка',     value: +latest.delivery_score.toFixed(1) },
    { subject: 'Качество',     value: +latest.quality_score.toFixed(1) },
    { subject: 'Коллаборация', value: +latest.collaboration_score.toFixed(1) },
    { subject: 'Стабильность', value: +latest.consistency_score.toFixed(1) },
  ] : []
  const actData = daily.slice(-21).map(d => ({
    day:      d.date?.slice(5, 10),
    Коммиты:  d.commits_count,
    PR:       d.prs_merged,
    Ревью:    d.reviews_given,
    SP:       +d.story_points_delivered.toFixed(1),
  }))

  return (
    <div style={{ animation: 'fadeIn 0.25s ease' }}>
      {/* Header */}
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
      ) : scores.length === 0 ? (
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
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 1, background: T.border, borderRadius: 8, overflow: 'hidden' }}>
                {[
                  { label: 'Поставка',     v: latest.delivery_score,      color: T.green  },
                  { label: 'Качество',     v: latest.quality_score,       color: T.purple },
                  { label: 'Коллаборация', v: latest.collaboration_score, color: T.amber  },
                  { label: 'Стабильность', v: latest.consistency_score,   color: T.cyan   },
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
                  <XAxis dataKey="day"  tick={{ fill: T.textSm, fontSize: 10, fontFamily: font }} />
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
                  { label: 'Нерабочее время', value: `${((latest.after_hours_ratio||0)*100).toFixed(0)}%`, threshold: '> 20%' },
                  { label: 'Выходные дни',    value: `${((latest.weekend_activity_ratio||0)*100).toFixed(0)}%`, threshold: '> 10%' },
                  { label: 'Ср. часов в день', value: `${latest.avg_daily_active_hours?.toFixed(1) || '—'}ч`, threshold: '> 9ч' },
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
      )}
    </div>
  )
}
