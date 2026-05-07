import { T, font, fontSans } from '../tokens'
import { Card, Badge, Btn, Avatar, EmptyState } from '../components/UI'

export default function TeamsView({ departments, teams, devsByTeam, onEditTeam, onDeleteTeam, onAddTeam, onSelectDev, onAddDev, onViewReport, onEditDept, onDeleteDept, onAddDept }) {
  const deptMap = Object.fromEntries(departments.map(d => [d.id, d]))

  const teamsByDept = departments.reduce((acc, d) => {
    acc[d.id] = teams.filter(t => t.department_id === d.id)
    return acc
  }, {})
  const unassigned = teams.filter(t => !t.department_id)

  const renderTeam = team => {
    const members = devsByTeam[team.id] || []
    return (
      <div key={team.id} style={{ marginBottom: 12, padding: '16px 18px', borderRadius: 10, background: T.surface, border: `1px solid ${T.border}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{team.name}</div>
            <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
              {team.jira_project_key && <Badge label={`Jira: ${team.jira_project_key}`} color={T.cyan} />}
              {team.github_org       && <Badge label={`GitHub: ${team.github_org}`}       color={T.purple} />}
              <Badge label={`${members.length} уч.`} color={T.textSm} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            <Btn small variant="success" onClick={() => onViewReport(team.id)}>📊 Отчёт</Btn>
            <Btn small onClick={() => onAddDev(team)}>+ Разработчик</Btn>
            <Btn small onClick={() => onEditTeam(team)}>✎</Btn>
            <Btn small variant="danger" onClick={() => onDeleteTeam(team)}>✕</Btn>
          </div>
        </div>
        {members.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(170px,1fr))', gap: 8 }}>
            {members.map(dev => (
              <div key={dev.id} onClick={() => onSelectDev(dev.id)}
                style={{ padding: '9px 11px', borderRadius: 8, border: `1px solid ${T.border}`, cursor: 'pointer', background: T.card, transition: 'all 0.15s' }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = T.accentLt; e.currentTarget.style.background = T.cardHov }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = T.border;   e.currentTarget.style.background = T.card }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                  <Avatar name={dev.display_name} size={22} />
                  <div style={{ fontSize: 12, fontWeight: 600, color: T.text, fontFamily: fontSans, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{dev.display_name}</div>
                </div>
                <div style={{ fontSize: 10, color: dev.github_login ? T.purple : T.textSm, fontFamily: font }}>{dev.github_login ? `⌥ ${dev.github_login}` : 'Нет GitHub'}</div>
                <div style={{ fontSize: 10, color: dev.jira_account_id ? T.cyan : T.textSm, fontFamily: font, marginTop: 2 }}>{dev.jira_account_id ? '✓ Jira' : 'Нет Jira'}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: T.textSm, textAlign: 'center', padding: '10px 0' }}>
            Нет разработчиков — <span style={{ color: T.accentLt, cursor: 'pointer' }} onClick={() => onAddDev(team)}>добавить</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text, fontFamily: fontSans }}>Команды</h2>
          <div style={{ fontSize: 12, color: T.textSm, marginTop: 2 }}>{departments.length} депт · {teams.length} команд</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn onClick={onAddDept}>+ Департамент</Btn>
          <Btn variant="primary" onClick={onAddTeam}>+ Команда</Btn>
        </div>
      </div>

      {departments.length === 0 && teams.length === 0 ? (
        <Card><EmptyState icon="🏗️" text="Нет данных. Создайте департамент и команды."
          action={<Btn variant="primary" onClick={onAddDept}>+ Создать департамент</Btn>} /></Card>
      ) : (
        <div>
          {departments.map(dept => (
            <div key={dept.id} style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, paddingBottom: 8, borderBottom: `1px solid ${T.border}` }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{dept.name}</div>
                  {dept.head_name && <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginTop: 2 }}>Руководитель: {dept.head_name}</div>}
                  {dept.description && <div style={{ fontSize: 11, color: T.textSm, marginTop: 2 }}>{dept.description}</div>}
                </div>
                <Btn small onClick={() => onEditDept(dept)}>✎</Btn>
                <Btn small variant="danger" onClick={() => onDeleteDept(dept)}>✕</Btn>
              </div>
              {teamsByDept[dept.id]?.length > 0
                ? teamsByDept[dept.id].map(renderTeam)
                : <div style={{ fontSize: 12, color: T.textSm, paddingLeft: 12, marginBottom: 12 }}>Нет команд в этом департаменте</div>
              }
            </div>
          ))}
          {unassigned.length > 0 && (
            <div>
              <div style={{ fontSize: 12, color: T.textSm, marginBottom: 10, fontFamily: font }}>БЕЗ ДЕПАРТАМЕНТА</div>
              {unassigned.map(renderTeam)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
