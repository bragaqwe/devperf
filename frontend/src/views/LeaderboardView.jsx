import { useState, useEffect } from 'react'
import { api } from '../api'
import { T, font, fontSans, burnoutColor, burnoutLabel } from '../tokens'
import { Card, Badge, Spinner, ScoreRing, EmptyState } from '../components/UI'

export default function LeaderboardView({ teams, departments }) {
  const [sel,         setSel]         = useState('all')
  const [leaderboard, setLeaderboard] = useState([])
  const [loading,     setLoading]     = useState(true)
  const teamMap = Object.fromEntries(teams.map(t => [t.id, t]))

  useEffect(() => {
    setLoading(true)
    const q = sel === 'all' ? '/leaderboard' : `/leaderboard?team_id=${sel}`
    api.get(q).then(setLeaderboard).catch(() => setLeaderboard([]))
      .finally(() => setLoading(false))
  }, [sel])

  const medalColor = i => [T.amber, '#94a3b8', '#cd7c2f'][i] ?? T.textSm

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text, fontFamily: fontSans }}>Рейтинг</h2>
          <div style={{ fontSize: 12, color: T.textSm, marginTop: 2 }}>По общей оценке</div>
        </div>
        <select value={sel} onChange={e => setSel(e.target.value)}
          style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 12, fontFamily: font, outline: 'none' }}>
          <option value="all">Все команды</option>
          {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>

      {loading ? <Card style={{ textAlign: 'center', padding: 48 }}><Spinner size={28} /></Card>
      : leaderboard.length === 0 ? <Card><EmptyState icon="🏆" text="Нет данных — сначала синхронизируйте разработчиков." /></Card>
      : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {leaderboard.map((row, idx) => (
            <Card key={row.developer_id} style={{ padding: '12px 18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, background: idx < 3 ? medalColor(idx) + '18' : T.border, border: `1px solid ${medalColor(idx)}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800, color: medalColor(idx), fontFamily: font }}>
                  {idx + 1}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{row.display_name}</div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 3, flexWrap: 'wrap', alignItems: 'center' }}>
                    {row.team_id && teamMap[row.team_id] && <Badge label={teamMap[row.team_id].name} color={T.textSm} size="xs" />}
                    {row.github_login && <span style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>@{row.github_login}</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexShrink: 0 }}>
                  {[
                    { l: 'Поставка', v: row.delivery_score,      c: T.green  },
                    { l: 'Качество', v: row.quality_score,       c: T.purple },
                    { l: 'Коллаб.',  v: row.collaboration_score, c: T.amber  },
                  ].map(({ l, v, c }) => (
                    <div key={l} style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 18, fontWeight: 800, color: c, fontFamily: font }}>{v?.toFixed(0)}</div>
                      <div style={{ fontSize: 9, color: T.textSm, textTransform: 'uppercase', fontFamily: font }}>{l}</div>
                    </div>
                  ))}
                  <Badge label={burnoutLabel[row.burnout_risk_level] || row.burnout_risk_level} color={burnoutColor[row.burnout_risk_level]} />
                  <ScoreRing value={row.overall_score} size={46} stroke={4} />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
