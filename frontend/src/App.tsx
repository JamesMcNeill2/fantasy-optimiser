import {
  leaguesPath,
  rosterPath,
  teamsPath,
  type League,
  type RosterResponse,
  type Team
} from './api'
import { ChoiceList } from './ChoiceList'
import { LineupView } from './LineupView'
import { RequestStatus } from './RequestStatus'
import { useApi } from './useApi'
import { useSelection } from './urlState'
import { weekLabel } from './lineup'
import { PageHeader } from './PageHeader'


function App() {
  const [selection, choose] = useSelection()

  const [leagues, retryLeagues] = useApi<League[]>(leaguesPath)
  // The chosen league, if it's in the list (a stale link might name another)
  const league =
    leagues.status === 'success'
      ? leagues.data.find((item) => item.key === selection.league)
      : undefined

  const [teams, retryTeams] = useApi<Team[]>(league === undefined ? null : teamsPath(league.key))

  // Likewise for the team
  const team =
    teams.status === 'success'
      ? teams.data.find((item) => item.roster_id === selection.team)
      : undefined

  const [roster, retryRoster] = useApi<RosterResponse>(
    league === undefined || team === undefined ? null : rosterPath(league.key, team.roster_id),
  )

  return (
    <main>
      <header className="site-header">
        <h1>
          <a
            href="/"
            onClick={(event) => {
              event.preventDefault()
              choose({ league: null, team: null })
            }}
          >
            Mac's Fantasy Lineup Optimiser
          </a>
        </h1>
      </header>

      {league === undefined && (
        <>
          <PageHeader title="Choose Your League" />
          <RequestStatus state={leagues} loading="Loading leagues…" onRetry={retryLeagues} />
          {leagues.status === 'success' && (
            <ChoiceList
              choices={leagues.data.map((item) => ({ value: item.key, label: item.name }))}
              size="large"
              onChoose={(key) => choose({ league: key, team: null })}
            />
          )}
        </>
      )}

      {league !== undefined && team === undefined && (
        <>
          <PageHeader
            title={league.name}
            subtitle="Choose Your Team"
            back={{ label : 'All Leagues', onClick: () => choose({ league: null, team: null}) }}
          />
          <RequestStatus state={teams} loading="Loading teams…" onRetry={retryTeams} />
          {teams.status === 'success' && (
            <ChoiceList
              choices={teams.data.map((item) => ({ value: item.roster_id, label: item.team_name }))}
              size="regular"
              onChoose={(rosterId) => choose({ league: league.key, team: rosterId})}
            />
          )}
        </>
      )}

      {league !== undefined && team !== undefined && (
        <>
          <PageHeader
            title={team.team_name}
            subtitle={roster.status === 'success' ? weekLabel(roster.data) : undefined}
            back={{ label: league.name, onClick: () => choose({ league: league.key, team: null }) }}
          />
          <RequestStatus state={roster} loading="Loading lineup…" onRetry={retryRoster} />
          {roster.status ==='success' && <LineupView roster={roster.data} />}
        </>
      )}
    </main>
  )
}

export default App
