export const T = {
  bg:       '#070b14', surface: '#0d1220', card:    '#111827',
  cardHov:  '#141f32', border:  '#1c2a3d', borderLt:'#253548',
  accent:   '#2563eb', accentLt:'#3b82f6', accentDim:'#1d4ed820',
  green:    '#10b981', greenDim:'#10b98118',
  amber:    '#f59e0b', amberDim:'#f59e0b18',
  red:      '#ef4444', redDim:  '#ef444418',
  purple:   '#8b5cf6', purpleDim:'#8b5cf618',
  cyan:     '#06b6d4', cyanDim: '#06b6d418',
  text:     '#e2e8f0', textMd:  '#94a3b8', textSm:  '#64748b',
}
export const font     = "'IBM Plex Mono','Fira Code',monospace"
export const fontSans = "'DM Sans','Segoe UI',sans-serif"
export const scoreColor   = v => v >= 75 ? T.green : v >= 50 ? T.amber : T.red
export const burnoutColor = { low: T.green, medium: T.amber, high: T.red }
export const burnoutLabel = { low: 'Норма', medium: 'Риск', high: 'Опасно' }

// event type → { label, color }
export const EVENT_META = {
  commit:          { label: 'Коммит',             color: '#3b82f6' },
  pr_opened:       { label: 'PR открыт',          color: '#10b981' },
  pr_merged:       { label: 'PR влит',            color: '#8b5cf6' },
  pr_closed:       { label: 'PR закрыт',          color: '#64748b' },
  pr_review:       { label: 'Ревью',              color: '#f59e0b' },
  pr_comment:      { label: 'Комментарий PR',     color: '#f59e0b' },
  issue_resolved:  { label: 'Задача закрыта',     color: '#10b981' },
  issue_created:   { label: 'Задача создана',     color: '#06b6d4' },
  issue_updated:   { label: 'Задача обновлена',   color: '#64748b' },
  issue_reopened:  { label: 'Задача переоткрыта', color: '#ef4444' },
  jira_transition: { label: 'Смена статуса',      color: '#06b6d4' },
  release:         { label: 'Релиз',              color: '#a855f7' },
}
