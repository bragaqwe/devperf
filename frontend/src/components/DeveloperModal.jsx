import { useState } from 'react'
import { api } from '../api'
import { T } from '../tokens'
import { Modal, Input, Select, Btn } from './UI'

export default function DeveloperModal({ developer, teams, defaultTeamId, onClose, onSave }) {
  const [name,    setName]    = useState(developer?.display_name    || '')
  const [teamId,  setTeamId]  = useState(developer?.team_id         ? String(developer.team_id) : defaultTeamId ? String(defaultTeamId) : '')
  const [ghLogin, setGhLogin] = useState(developer?.github_login    || '')
  const [jiraId,  setJiraId]  = useState(developer?.jira_account_id || '')
  const [email,   setEmail]   = useState(developer?.email           || '')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const teamOptions = [{ value: '', label: '— выберите —' }, ...teams.map(t => ({ value: String(t.id), label: t.name }))]

  const save = async () => {
    if (!name.trim()) return setError('Имя обязательно')
    if (!teamId)      return setError('Команда обязательна')
    setLoading(true); setError('')
    try {
      const body = { display_name: name, team_id: Number(teamId), github_login: ghLogin || null, jira_account_id: jiraId || null, email: email || null }
      onSave(await (developer ? api.put(`/developers/${developer.id}`, body) : api.post('/developers', body)))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  return (
    <Modal title={developer ? 'Редактировать разработчика' : 'Добавить разработчика'} onClose={onClose}>
      <Input label="Имя *" value={name} onChange={setName} placeholder="Иван Петров" />
      <Select label="Команда *" value={teamId} onChange={setTeamId} options={teamOptions} />
      <Input label="GitHub Login" value={ghLogin} onChange={setGhLogin} placeholder="ivan_dev" hint="Логин на github.com — фильтрует коммиты, PR и ревью" />
      <Input label="Jira Account ID" value={jiraId} onChange={setJiraId} placeholder="622fc77c1f014e0069cc3bd1" hint='curl -u email:token https://org.atlassian.net/rest/api/3/myself → поле "accountId"' />
      <Input label="Email" value={email} onChange={setEmail} placeholder="ivan@company.ru" type="email" />
      {error && <div style={{ color: T.red, fontSize: 12, marginBottom: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Btn onClick={onClose}>Отмена</Btn>
        <Btn variant="primary" onClick={save} loading={loading}>{developer ? 'Сохранить' : 'Добавить'}</Btn>
      </div>
    </Modal>
  )
}
