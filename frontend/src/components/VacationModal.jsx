import { useState } from 'react'
import { api } from '../api'
import { T, font, fontSans } from '../tokens'
import { Modal, Btn, Input } from './UI'

export default function VacationModal({ devId, onClose, onSave }) {
  const [startedAt, setStartedAt] = useState('')
  const [endedAt,   setEndedAt]   = useState('')
  const [note,      setNote]      = useState('')
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')

  const save = async () => {
    if (!startedAt || !endedAt) return setError('Укажите даты начала и конца отпуска')
    if (new Date(endedAt) <= new Date(startedAt)) return setError('Дата конца должна быть позже начала')
    setLoading(true); setError('')
    try {
      await api.post(`/developers/${devId}/vacations`, {
        started_at: new Date(startedAt).toISOString(),
        ended_at:   new Date(endedAt).toISOString(),
        source: 'manual',
        note: note || null,
      })
      onSave()
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }

  return (
    <Modal title="Добавить отпуск" onClose={onClose}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Начало</div>
          <input type="date" value={startedAt} onChange={e => setStartedAt(e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 13, fontFamily: fontSans, boxSizing: 'border-box' }} />
        </div>
        <div>
          <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Конец</div>
          <input type="date" value={endedAt} onChange={e => setEndedAt(e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 13, fontFamily: fontSans, boxSizing: 'border-box' }} />
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <Input label="Комментарий (необязательно)" value={note} onChange={setNote} placeholder="Плановый отпуск, больничный..." />
      </div>

      {error && <div style={{ color: '#ef4444', fontSize: 12, marginBottom: 12, marginTop: 4 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
        <Btn onClick={onClose}>Отмена</Btn>
        <Btn variant="primary" onClick={save} loading={loading}>Добавить</Btn>
      </div>
    </Modal>
  )
}
