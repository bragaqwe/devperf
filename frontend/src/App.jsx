import { useState, useEffect, useCallback } from 'react'
import { api } from './api'
import { T, font, fontSans } from './tokens'
import { Spinner } from './components/UI'
import DepartmentModal from './components/DepartmentModal'
import TeamModal       from './components/TeamModal'
import DeveloperModal  from './components/DeveloperModal'
import SyncModal       from './components/SyncModal'
import TeamsView       from './views/TeamsView'
import DevelopersView  from './views/DevelopersView'
import DeveloperDetail from './views/DeveloperDetail'
import LeaderboardView from './views/LeaderboardView'
import TeamReportView  from './views/TeamReport'

const NAV = [
  { id: 'teams',       label: 'Команды',       icon: '◈' },
  { id: 'developers',  label: 'Разработчики',  icon: '◎' },
  { id: 'leaderboard', label: 'Рейтинг',       icon: '◆' },
]

export default function App() {
  const [view,           setView]          = useState('teams')
  const [selectedDevId,  setSelectedDevId] = useState(null)
  const [selectedTeamId, setSelectedTeamId]= useState(null)
  const [departments,    setDepartments]   = useState([])
  const [teams,          setTeams]         = useState([])
  const [developers,     setDevelopers]    = useState([])
  const [loading,        setLoading]       = useState(true)

  const [deptModal, setDeptModal] = useState(null)   // null | 'new' | dept object
  const [teamModal, setTeamModal] = useState(null)
  const [devModal,  setDevModal]  = useState(null)
  const [syncModal, setSyncModal] = useState(null)

  const loadData = useCallback(async () => {
    try {
      const [d, t, devs] = await Promise.all([api.get('/departments'), api.get('/teams'), api.get('/developers')])
      setDepartments(d); setTeams(t); setDevelopers(devs)
    } catch (e) { console.error(e) }
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const devsByTeam = developers.reduce((acc, dev) => {
    ;(acc[dev.team_id] = acc[dev.team_id] || []).push(dev)
    return acc
  }, {})

  const handleDeleteDept = async dept => {
    if (!window.confirm(`Удалить департамент "${dept.name}"?`)) return
    await api.delete(`/departments/${dept.id}`); loadData()
  }
  const handleDeleteTeam = async team => {
    if (!window.confirm(`Удалить команду "${team.name}"?`)) return
    await api.delete(`/teams/${team.id}`); loadData()
  }
  const handleDeleteDev = async dev => {
    if (!window.confirm(`Удалить разработчика "${dev.display_name}"?`)) return
    await api.delete(`/developers/${dev.id}`)
    if (selectedDevId === dev.id) { setSelectedDevId(null); setView('developers') }
    loadData()
  }
  const handleSelectDev  = id  => { setSelectedDevId(id);  setView('developer') }
  const handleViewReport = id  => { setSelectedTeamId(id); setView('teamreport') }
  const navigate = id => { setView(id); setSelectedDevId(null); setSelectedTeamId(null) }

  const deptsWithTeams = departments

  return (
    <div style={{ minHeight: '100vh', background: T.bg, color: T.text, fontFamily: fontSans, fontSize: 14 }}>

      {/* Sidebar */}
      <aside style={{ position: 'fixed', top: 0, left: 0, bottom: 0, width: 224, background: T.surface, borderRight: `1px solid ${T.border}`, display: 'flex', flexDirection: 'column', zIndex: 100, overflowY: 'auto' }}>
        {/* Logo */}
        <div style={{ padding: '20px 20px 16px', borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>
          <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.03em', color: T.text, fontFamily: fontSans }}>
            <span style={{ color: T.accentLt }}>dev</span>perf
            <span style={{ color: T.textSm, fontSize: 10, fontWeight: 400, marginLeft: 6, fontFamily: font }}>v3</span>
          </div>
          <div style={{ fontSize: 9, color: T.textSm, marginTop: 3, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Система аналитики</div>
        </div>

        <nav style={{ padding: '12px 10px', flex: 1 }}>
          {/* Main nav */}
          {NAV.map(({ id, label, icon }) => {
            const active = view === id
            return (
              <button key={id} onClick={() => navigate(id)} style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '9px 12px', borderRadius: 8, border: 'none', cursor: 'pointer', textAlign: 'left', marginBottom: 2, background: active ? T.accentDim : 'transparent', color: active ? T.accentLt : T.textMd, fontSize: 13, fontWeight: active ? 600 : 400, fontFamily: fontSans }}>
                <span style={{ fontFamily: font, fontSize: 13 }}>{icon}</span>{label}
              </button>
            )
          })}

          {/* Team reports */}
          {teams.length > 0 && (
            <>
              <div style={{ margin: '14px 12px 6px', fontSize: 9, color: T.textSm, textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: font }}>Отчёты команд</div>
              {teams.map(team => {
                const active = view === 'teamreport' && selectedTeamId === team.id
                return (
                  <button key={team.id} onClick={() => handleViewReport(team.id)} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '7px 12px', borderRadius: 8, border: 'none', cursor: 'pointer', textAlign: 'left', marginBottom: 1, background: active ? T.accentDim : 'transparent', color: active ? T.accentLt : T.textSm, fontSize: 12, fontFamily: fontSans }}>
                    <span style={{ fontFamily: font, fontSize: 11 }}>◈</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{team.name}</span>
                  </button>
                )
              })}
            </>
          )}

          {/* Developers */}
          {developers.length > 0 && (
            <>
              <div style={{ margin: '14px 12px 6px', fontSize: 9, color: T.textSm, textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: font }}>Разработчики</div>
              {developers.map(dev => {
                const active = selectedDevId === dev.id && view === 'developer'
                return (
                  <button key={dev.id} onClick={() => handleSelectDev(dev.id)} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '7px 12px', borderRadius: 8, border: 'none', cursor: 'pointer', textAlign: 'left', marginBottom: 1, background: active ? T.accentDim : 'transparent', color: active ? T.accentLt : T.textSm, fontSize: 12, fontFamily: fontSans }}>
                    <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, background: 'linear-gradient(135deg,#2563eb88,#8b5cf688)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, fontWeight: 700, color: '#fff' }}>
                      {dev.display_name.charAt(0)}
                    </div>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{dev.display_name}</span>
                  </button>
                )
              })}
            </>
          )}
        </nav>

        {/* Footer */}
        <div style={{ padding: '10px 16px', borderTop: `1px solid ${T.border}`, fontSize: 11, color: T.textSm, fontFamily: font, flexShrink: 0 }}>
          {departments.length} депт · {teams.length} команд · {developers.length} разраб.
        </div>
      </aside>

      {/* Main content */}
      <main style={{ marginLeft: 224, padding: '28px 32px 64px', minHeight: '100vh' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
            <Spinner size={32} />
          </div>
        ) : (
          <>
            {view === 'teams' && (
              <TeamsView
                departments={departments} teams={teams} devsByTeam={devsByTeam}
                onEditTeam={t => setTeamModal(t)}
                onDeleteTeam={handleDeleteTeam}
                onAddTeam={() => setTeamModal('new')}
                onSelectDev={handleSelectDev}
                onAddDev={team => setDevModal({ dev: null, defaultTeamId: team.id })}
                onViewReport={handleViewReport}
                onEditDept={d => setDeptModal(d)}
                onDeleteDept={handleDeleteDept}
                onAddDept={() => setDeptModal('new')}
              />
            )}
            {view === 'developers' && (
              <DevelopersView
                developers={developers} teams={teams}
                onSelect={handleSelectDev}
                onEdit={dev => setDevModal({ dev, defaultTeamId: dev.team_id })}
                onDelete={handleDeleteDev}
                onSync={dev => setSyncModal(dev)}
                onAdd={() => setDevModal({ dev: null, defaultTeamId: teams[0]?.id })}
              />
            )}
            {view === 'developer' && selectedDevId && (
              <DeveloperDetail
                devId={selectedDevId} developers={developers} teams={teams}
                onEdit={dev => setDevModal({ dev, defaultTeamId: dev.team_id })}
                onSync={dev => setSyncModal(dev)}
              />
            )}
            {view === 'teamreport' && selectedTeamId && (
              <TeamReportView
                teamId={selectedTeamId} teams={teams} departments={departments}
                onSelectDev={handleSelectDev}
              />
            )}
            {view === 'leaderboard' && (
              <LeaderboardView teams={teams} departments={departments} />
            )}
          </>
        )}
      </main>

      {/* Modals */}
      {deptModal && <DepartmentModal dept={deptModal === 'new' ? null : deptModal} onClose={() => setDeptModal(null)} onSave={() => { setDeptModal(null); loadData() }} />}
      {teamModal && <TeamModal team={teamModal === 'new' ? null : teamModal} departments={departments} onClose={() => setTeamModal(null)} onSave={() => { setTeamModal(null); loadData() }} />}
      {devModal  && <DeveloperModal developer={devModal.dev} teams={teams} defaultTeamId={devModal.defaultTeamId} onClose={() => setDevModal(null)} onSave={() => { setDevModal(null); loadData() }} />}
      {syncModal && <SyncModal developer={syncModal} onClose={() => { setSyncModal(null); loadData() }} />}
    </div>
  )
}
