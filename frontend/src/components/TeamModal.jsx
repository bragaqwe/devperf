import { useState } from 'react'
import { api } from '../api'
import { T } from '../tokens'
import { Modal, Input, Select, Btn } from './UI'

export default function TeamModal({ team, departments, onClose, onSave }) {
  const [name,    setName]    = useState(team?.name             || '')
  const [jiraKey, setJiraKey] = useState(team?.jira_project_key || '')
  const [ghOrg,   setGhOrg]   = useState(team?.github_org       || '')
  const [deptId,  setDeptId]  = useState(team?.department_id    ? String(team.department_id) : '')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const deptOptions = [{ value: '', label: '— не выбрано —' }, ...departments.map(d => ({ value: String(d.id), label: d.name }))]

  const save = async () => {
    if (!name.trim()) return setError('Название обязательно')
    setLoading(true); setError('')
    try {
      const body = { name, jira_project_key: jiraKey || null, github_org: ghOrg || null, department_id: deptId ? Number(deptId) : null }
      onSave(await (team ? api.put(`/teams/${team.id}`, body) : api.post('/teams', body)))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  return (
    <Modal title={team ? 'Редактировать команду' : 'Новая команда'} onClose={onClose}>
      <Input label="Название *" value={name} onChange={setName} placeholder="Core Platform" />
      <Select label="Департамент" value={deptId} onChange={setDeptId} options={deptOptions} />
      <Input label="Jira Project Key" value={jiraKey} onChange={setJiraKey} placeholder="SCRUM" hint="Префикс перед номером задачи — SCRUM-123 → SCRUM" />
      <Input label="GitHub Organization" value={ghOrg} onChange={setGhOrg} placeholder="my-org" hint="Автоматически находит репозитории при синхронизации" />
      {error && <div style={{ color: T.red, fontSize: 12, marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Btn onClick={onClose}>Отмена</Btn>
        <Btn variant="primary" onClick={save} loading={loading}>{team ? 'Сохранить' : 'Создать'}</Btn>
      </div>
    </Modal>
  )
}
