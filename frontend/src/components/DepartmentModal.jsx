import { useState } from 'react'
import { api } from '../api'
import { T } from '../tokens'
import { Modal, Input, Btn } from './UI'

export default function DepartmentModal({ dept, onClose, onSave }) {
  const [name,  setName]  = useState(dept?.name        || '')
  const [desc,  setDesc]  = useState(dept?.description || '')
  const [head,  setHead]  = useState(dept?.head_name   || '')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const save = async () => {
    if (!name.trim()) return setError('Название обязательно')
    setLoading(true); setError('')
    try {
      const body = { name, description: desc || null, head_name: head || null }
      onSave(await (dept ? api.put(`/departments/${dept.id}`, body) : api.post('/departments', body)))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  return (
    <Modal title={dept ? 'Редактировать департамент' : 'Новый департамент'} onClose={onClose}>
      <Input label="Название *" value={name} onChange={setName} placeholder="Разработка" />
      <Input label="Описание" value={desc} onChange={setDesc} placeholder="Продуктовая разработка" />
      <Input label="Руководитель" value={head} onChange={setHead} placeholder="Иван Петров" />
      {error && <div style={{ color: T.red, fontSize: 12, marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Btn onClick={onClose}>Отмена</Btn>
        <Btn variant="primary" onClick={save} loading={loading}>{dept ? 'Сохранить' : 'Создать'}</Btn>
      </div>
    </Modal>
  )
}
