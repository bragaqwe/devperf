import { T, font, fontSans } from '../tokens'
import { Card, Badge, Btn, Avatar, EmptyState } from '../components/UI'

export default function DepartmentsView({ departments, teams, onAdd, onEdit, onDelete, onViewTeam }) {
  const teamsByDept = teams.reduce((acc, t) => {
    const key = t.department_id ?? '__none__'
    ;(acc[key] = acc[key] || []).push(t)
    return acc
  }, {})

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text, fontFamily: fontSans }}>Департаменты</h2>
          <div style={{ fontSize: 12, color: T.textSm, marginTop: 2 }}>{departments.length} департаментов</div>
        </div>
        <Btn variant="primary" onClick={onAdd}>+ Создать</Btn>
      </div>

      {departments.length === 0 ? (
        <Card>
          <EmptyState icon="🏢" text="Пока нет ни одного департамента."
            action={<Btn variant="primary" onClick={onAdd}>+ Создать департамент</Btn>} />
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {departments.map(dept => {
            const deptTeams = teamsByDept[dept.id] || []
            return (
              <Card key={dept.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg,#2563eb,#8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>
                        🏢
                      </div>
                      <div>
                        <div style={{ fontSize: 16, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{dept.name}</div>
                        {dept.head_name && (
                          <div style={{ fontSize: 11, color: T.textSm, fontFamily: font, marginTop: 2 }}>
                            Руководитель: {dept.head_name}
                          </div>
                        )}
                      </div>
                    </div>
                    {dept.description && (
                      <div style={{ fontSize: 12, color: T.textMd, marginTop: 8, fontFamily: fontSans, maxWidth: 480 }}>
                        {dept.description}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Btn small onClick={() => onEdit(dept)}>Изменить</Btn>
                    <Btn small variant="danger" onClick={() => onDelete(dept)}>Удалить</Btn>
                  </div>
                </div>

                {/* Teams in this department */}
                <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 12 }}>
                  <div style={{ fontSize: 10, color: T.textSm, textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: font, marginBottom: 8 }}>
                    Команды ({deptTeams.length})
                  </div>
                  {deptTeams.length === 0 ? (
                    <div style={{ fontSize: 12, color: T.textSm }}>Нет команд в этом департаменте</div>
                  ) : (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {deptTeams.map(team => (
                        <div key={team.id}
                          onClick={() => onViewTeam(team.id)}
                          style={{ padding: '6px 12px', borderRadius: 8, background: T.surface, border: `1px solid ${T.border}`, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, transition: 'all 0.12s' }}
                          onMouseEnter={e => { e.currentTarget.style.borderColor = T.accentLt; e.currentTarget.style.background = T.cardHov }}
                          onMouseLeave={e => { e.currentTarget.style.borderColor = T.border;   e.currentTarget.style.background = T.surface }}
                        >
                          <span style={{ fontSize: 12, color: T.text, fontFamily: fontSans, fontWeight: 500 }}>{team.name}</span>
                          {team.jira_project_key && <Badge label={team.jira_project_key} color={T.cyan} size="xs" />}
                          {team.github_org       && <Badge label={team.github_org}       color={T.purple} size="xs" />}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
