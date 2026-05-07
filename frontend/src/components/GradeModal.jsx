import { useState } from 'react'
import { api } from '../api'
import { T, font, fontSans } from '../tokens'
import { Modal, Btn, Select, Input } from './UI'

const GRADE_OPTIONS = [
  { value: 'junior', label: 'Junior' },
  { value: 'middle', label: 'Middle' },
  { value: 'senior', label: 'Senior' },
  { value: 'staff',  label: 'Staff' },
  { value: 'lead',   label: 'Lead' },
]

const GRADE_COLORS = {
  junior: '#64748b', middle: '#3b82f6', senior: '#8b5cf6', staff: '#f59e0b', lead: '#ef4444',
}

export default function GradeModal({ developer, currentGrade, onClose, onSave }) {
  const [grade,     setGrade]     = useState(currentGrade || '')
  const [changedBy, setChangedBy] = useState('')
  const [note,      setNote]      = useState('')
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')

  const save = async () => {
    if (!grade) return setError('Выберите грейд')
    setLoading(true); setError('')
    try {
      await api.post(`/developers/${developer.id}/grade`, {
        grade, changed_by: changedBy || null, note: note || null,
      })
      onSave()
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }

  const selectedColor = GRADE_COLORS[grade] || T.textSm

  return (
    <Modal title="Изменить грейд" onClose={onClose}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Новый грейд</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {GRADE_OPTIONS.map(opt => {
            const active = grade === opt.value
            const color  = GRADE_COLORS[opt.value]
            return (
              <button key={opt.value} onClick={() => setGrade(opt.value)}
                style={{ flex: 1, padding: '10px 8px', borderRadius: 8, border: active ? `2px solid ${color}` : `1px solid ${T.border}`, background: active ? color + '18' : T.surface, cursor: 'pointer', fontSize: 12, fontWeight: active ? 700 : 400, color: active ? color : T.textMd, fontFamily: fontSans, transition: 'all 0.15s' }}>
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>

      <Input label="Кто изменяет (имя тимлида)" value={changedBy} onChange={setChangedBy} placeholder="Иван Петров" />
      <Input label="Комментарий (необязательно)" value={note} onChange={setNote} placeholder="Причина изменения грейда..." />

      {error && <div style={{ color: '#ef4444', fontSize: 12, marginBottom: 12 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Btn onClick={onClose}>Отмена</Btn>
        <Btn variant="primary" onClick={save} loading={loading}>Сохранить</Btn>
      </div>
    </Modal>
  )
}
