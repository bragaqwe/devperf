import { T, font, fontSans } from '../tokens'
import { Card, Badge, Btn, Avatar, EmptyState } from '../components/UI'

export default function DevelopersView({ developers, teams, onSelect, onEdit, onDelete, onSync, onAdd }) {
  const teamMap = Object.fromEntries(teams.map(t => [t.id, t]))
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text, fontFamily: fontSans }}>Разработчики</h2>
          <div style={{ fontSize: 12, color: T.textSm, marginTop: 2 }}>{developers.length} зарегистрировано</div>
        </div>
        <Btn variant="primary" onClick={onAdd}>+ Добавить</Btn>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {developers.length === 0
          ? <Card><EmptyState icon="👤" text="Нет разработчиков." action={<Btn variant="primary" onClick={onAdd}>+ Добавить</Btn>} /></Card>
          : developers.map(dev => {
              const team = teamMap[dev.team_id]
              return (
                <Card key={dev.id} style={{ padding: '14px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <Avatar name={dev.display_name} size={40} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 15, fontWeight: 700, color: T.text, fontFamily: fontSans }}>{dev.display_name}</div>
                      <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                        {team && <Badge label={team.name} color={T.textMd} />}
                        {dev.github_login     ? <Badge label={`⌥ ${dev.github_login}`} color={T.purple} /> : <Badge label="Нет GitHub" color={T.textSm} />}
                        {dev.jira_account_id  ? <Badge label="✓ Jira"                  color={T.cyan}   /> : <Badge label="Нет Jira"   color={T.textSm} />}
                        {dev.email && <span style={{ fontSize: 11, color: T.textSm, fontFamily: font }}>{dev.email}</span>}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                      <Btn small onClick={() => onSelect(dev.id)}>Профиль</Btn>
                      <Btn small onClick={() => onSync(dev)}>↻ Синк</Btn>
                      <Btn small onClick={() => onEdit(dev)}>✎</Btn>
                      <Btn small variant="danger" onClick={() => onDelete(dev)}>✕</Btn>
                    </div>
                  </div>
                </Card>
              )
            })}
      </div>
    </div>
  )
}
