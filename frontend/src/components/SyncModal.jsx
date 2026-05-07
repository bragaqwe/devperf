import { useState } from 'react'
import { api } from '../api'
import { T, font } from '../tokens'
import { Modal, Btn } from './UI'

export default function SyncModal({ developer, onClose }) {
  const [repos,    setRepos]    = useState('')
  const [daysBack, setDaysBack] = useState('30')
  const [loading,  setLoading]  = useState(false)
  const [log,      setLog]      = useState([])
  const [done,     setDone]     = useState(false)
  const push = m => setLog(p => [...p, m])

  const run = async () => {
    setLoading(true); setLog([])
    push(`⟳ Синхронизация ${developer.display_name}…`)
    try {
      const repoList = repos.split('\n').map(r => r.trim()).filter(Boolean)
      const res = await api.post(`/developers/${developer.id}/sync?days_back=${daysBack}`, repoList)
      res.message.split(' | ').forEach(m => push(`  ${m.startsWith('GitHub') ? '📦' : m.startsWith('Jira') ? '🎯' : '📊'} ${m}`))
      push('✅ Готово!'); setDone(true)
    } catch (e) { push(`❌ ${e.message}`) }
    setLoading(false)
  }

  const logBox = log.length > 0 && (
    <div style={{ marginBottom: 16, padding: '10px 12px', borderRadius: 8, background: T.bg, fontFamily: font, fontSize: 11, color: T.textMd, maxHeight: 140, overflowY: 'auto', lineHeight: 1.8 }}>
      {log.map((l, i) => <div key={i}>{l}</div>)}
    </div>
  )

  return (
    <Modal title={`Синхронизация: ${developer.display_name}`} onClose={onClose}>
      <div style={{ marginBottom: 16, padding: '12px 14px', borderRadius: 8, background: T.surface, border: `1px solid ${T.border}` }}>
        <div style={{ fontSize: 11, color: T.textSm, marginBottom: 8, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Интеграции</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', fontSize: 12, fontFamily: font }}>
          <span style={{ color: T.textSm }}>GitHub:</span>
          <span style={{ color: developer.github_login ? T.green : T.textSm }}>{developer.github_login ? `@${developer.github_login}` : '— не указан'}</span>
          <span style={{ color: T.textSm }}>Jira:</span>
          <span style={{ color: developer.jira_account_id ? T.cyan : T.textSm, wordBreak: 'break-all' }}>{developer.jira_account_id ? `${developer.jira_account_id.slice(0,24)}…` : '— не указан'}</span>
        </div>
      </div>
      {!done ? (
        <>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, color: T.textSm, marginBottom: 5, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.06em' }}>GitHub репозитории (по одному в строку)</label>
            <textarea value={repos} onChange={e => setRepos(e.target.value)} placeholder={'владелец/репозиторий\nвладелец/другой-репозиторий'} rows={3}
              style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 12, fontFamily: font, resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
              onFocus={e => e.target.style.borderColor = T.accentLt}
              onBlur={e  => e.target.style.borderColor = T.border} />
            <div style={{ fontSize: 10, color: T.textSm, marginTop: 3 }}>Оставьте пустым — будут использованы репозитории организации команды</div>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, color: T.textSm, marginBottom: 5, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Глубина (дней)</label>
            <input type="number" min="1" max="365" value={daysBack} onChange={e => setDaysBack(e.target.value)}
              style={{ width: 90, padding: '9px 12px', borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 13, fontFamily: font, outline: 'none' }} />
          </div>
          {logBox}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Btn onClick={onClose} disabled={loading}>Отмена</Btn>
            <Btn variant="primary" onClick={run} loading={loading} disabled={loading}>{loading ? 'Идёт синхронизация…' : '▶ Запустить'}</Btn>
          </div>
        </>
      ) : (
        <>{logBox}<div style={{ display: 'flex', justifyContent: 'flex-end' }}><Btn variant="primary" onClick={onClose}>Закрыть</Btn></div></>
      )}
    </Modal>
  )
}
