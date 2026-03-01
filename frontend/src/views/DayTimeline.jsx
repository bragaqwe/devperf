import { useState, useEffect } from 'react'
import { api } from '../api'
import { T, font, fontSans, EVENT_META } from '../tokens'
import { Modal, Spinner, Badge, Tag } from '../components/UI'

const fmtTime = dt => new Date(dt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
const fmtDate = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

function EventCard({ ev, isLast }) {
  const [expanded, setExpanded] = useState(false)
  const meta  = EVENT_META[ev.activity_type] || { label: ev.activity_type, color: T.textSm }
  const color = ev.badge_color || meta.color
  const label = ev.badge_label || meta.label

  const hasLink      = Boolean(ev.source_url)
  const hasDesc      = Boolean(ev.description)
  const isJira       = ev.source_type === 'jira_issue' || ev.source_type === 'jira_transition'
  const isGitHub     = !isJira
  // Для GitHub показываем описание только в раскрывашке; для Jira — сразу инлайн
  const showDescInline  = isJira && hasDesc
  const showDescExpand  = !isJira && hasDesc
  const hasSub          = showDescExpand

  return (
    <div style={{ display: 'flex', gap: 0, position: 'relative' }}>
      {/* Вертикальная линия + точка */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 40, flexShrink: 0 }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%', background: color,
          border: `2px solid ${T.bg}`, marginTop: 14, flexShrink: 0, zIndex: 1,
          boxShadow: `0 0 8px ${color}88`,
        }} />
        {!isLast && <div style={{ width: 2, flex: 1, minHeight: 12, background: T.border, marginTop: 4 }} />}
      </div>

      {/* Карточка */}
      <div style={{ flex: 1, marginBottom: 12 }}>
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 10, overflow: 'hidden',
          borderLeft: `3px solid ${color}`,
        }}>
          {/* Основная строка */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px' }}>
            {/* Время */}
            <span style={{ fontSize: 12, color: T.textSm, fontFamily: font, flexShrink: 0, minWidth: 42, marginTop: 2 }}>
              {fmtTime(ev.occurred_at)}
            </span>

            {/* Бейдж типа */}
            <Badge label={label} color={color} size="xs" />

            {/* Заголовок + мета */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13, color: T.text, fontFamily: fontSans, fontWeight: 500, wordBreak: 'break-word' }}>
                  {ev.title || label}
                </span>
                {ev.jira_issue_key && !ev.title?.startsWith(ev.jira_issue_key) && (
                  <Tag color={T.cyan}>{ev.jira_issue_key}</Tag>
                )}
                {ev.repo && (
                  <span style={{ fontSize: 10, color: T.textSm, fontFamily: font }}>
                    {ev.repo.split('/')[1] || ev.repo}
                  </span>
                )}
                {/* Строки — только для GitHub-событий */}
                {isGitHub && ev.lines_added > 0 && (
                  <>
                    <span style={{ fontSize: 11, color: T.green, fontFamily: font, fontWeight: 600 }}>+{ev.lines_added}</span>
                    <span style={{ fontSize: 11, color: T.red,   fontFamily: font, fontWeight: 600 }}>−{ev.lines_removed}</span>
                  </>
                )}
              </div>
              {/* Jira description всегда видна инлайн */}
              {showDescInline && (
                <div style={{ fontSize: 11, color: T.textMd, fontFamily: font, marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {ev.description}
                </div>
              )}
            </div>

            {/* Кнопки */}
            <div style={{ display: 'flex', gap: 6, flexShrink: 0, alignItems: 'center' }}>
              {hasSub && (
                <button onClick={() => setExpanded(!expanded)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.textSm, fontSize: 11, fontFamily: font, padding: '2px 6px', borderRadius: 4, transition: 'color 0.1s' }}
                  onMouseEnter={e => e.target.style.color = T.text}
                  onMouseLeave={e => e.target.style.color = T.textSm}
                >
                  {expanded ? '▴ скрыть' : '▾ детали'}
                </button>
              )}
              {hasLink && (
                <a href={ev.source_url} target="_blank" rel="noopener noreferrer"
                  style={{ color: T.accentLt, fontSize: 11, fontFamily: font, textDecoration: 'none', padding: '2px 8px', borderRadius: 4, background: T.accentDim, border: `1px solid ${T.accent}44`, display: 'inline-flex', alignItems: 'center', gap: 4, flexShrink: 0 }}
                  onMouseEnter={e => e.currentTarget.style.background = T.accent + '33'}
                  onMouseLeave={e => e.currentTarget.style.background = T.accentDim}
                >
                  ↗ открыть
                </a>
              )}
            </div>
          </div>

          {/* Раскрываемое описание (GitHub: ревью/комментарии) */}
          {expanded && hasSub && (
            <div style={{ padding: '0 14px 12px 62px', borderTop: `1px solid ${T.border}` }}>
              <div style={{ fontSize: 12, color: T.textMd, fontFamily: fontSans, lineHeight: 1.6, marginTop: 10, borderLeft: `2px solid ${T.borderLt}`, paddingLeft: 10 }}>
                {ev.description}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function KpiTile({ label, value, color }) {
  return (
    <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 8, padding: '14px 10px', textAlign: 'center', flex: 1 }}>
      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: font, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 9, color: T.textSm, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.07em', fontFamily: font }}>{label}</div>
    </div>
  )
}

export default function DayTimeline({ devId, devName, day, onClose }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [filter,  setFilter]  = useState('all')

  useEffect(() => {
    setLoading(true); setError('')
    api.get(`/developers/${devId}/day/${day}`)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [devId, day])

  const allTypes = data ? [...new Set(data.timeline.map(e => e.activity_type))] : []
  const filtered = data ? (filter === 'all' ? data.timeline : data.timeline.filter(e => e.activity_type === filter)) : []

  return (
    <Modal title={`${devName} — ${fmtDate(day)}`} onClose={onClose} wide>
      {loading && <div style={{ textAlign: 'center', padding: 48 }}><Spinner size={28} /></div>}
      {error   && <div style={{ color: T.red, fontSize: 13, padding: 20 }}>Ошибка: {error}</div>}
      {data && (
        <>
          {/* KPI strip */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
            <KpiTile label="Коммиты"         value={data.total_commits}                                        color={T.accentLt} />
            <KpiTile label="Строк добавлено" value={`+${data.lines_added}`}                                   color={T.green}    />
            <KpiTile label="Строк удалено"   value={`-${data.lines_removed}`}                                 color={T.red}      />
            <KpiTile label="PR открыто"      value={data.prs_opened}                                          color={T.textMd}   />
            <KpiTile label="PR влито"        value={data.prs_merged}                                          color={T.purple}   />
            <KpiTile label="Ревью"           value={data.reviews_given}                                       color={T.amber}    />
            <KpiTile label="Задач закрыто"   value={data.issues_resolved}                                     color={T.cyan}     />
            <KpiTile label="Story Points"    value={data.story_points > 0 ? data.story_points.toFixed(1) : '—'} color={T.cyan}  />
          </div>

          {/* Filter tabs */}
          {allTypes.length > 1 && (
            <div style={{ display: 'flex', gap: 4, marginBottom: 18, flexWrap: 'wrap' }}>
              <FilterPill value="all" current={filter} label="Все" count={data.timeline.length} onClick={setFilter} />
              {allTypes.map(t => {
                const meta = EVENT_META[t] || { label: t, color: T.textSm }
                return (
                  <FilterPill key={t} value={t} current={filter}
                    label={meta.label} color={meta.color}
                    count={data.timeline.filter(e => e.activity_type === t).length}
                    onClick={setFilter}
                  />
                )
              })}
            </div>
          )}

          {/* Timeline */}
          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: T.textSm, fontSize: 13 }}>
              Нет активности за этот день
            </div>
          ) : (
            <div style={{ paddingLeft: 4 }}>
              {filtered.map((ev, i) => (
                <EventCard key={ev.id} ev={ev} isLast={i === filtered.length - 1} />
              ))}
            </div>
          )}
        </>
      )}
    </Modal>
  )
}

function FilterPill({ value, current, label, color = T.textSm, count, onClick }) {
  const active = value === current
  return (
    <button onClick={() => onClick(value)} style={{
      padding: '4px 12px', borderRadius: 20, border: `1px solid ${active ? color : T.border}`,
      background: active ? color + '22' : T.surface, color: active ? color : T.textSm,
      fontSize: 11, fontFamily: font, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5,
    }}>
      {label}
      <span style={{ fontSize: 10, opacity: 0.7 }}>{count}</span>
    </button>
  )
}
