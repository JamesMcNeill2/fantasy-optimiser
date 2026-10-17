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
    league == undefined || team === undefined ? null : rosterPath(league.key, team.roster_id),
  )

  return (
    <main>
      <h1>Macs Fantasy Lineup Optimiser</h1>

      {league === undefined && (
        <>
          <RequestStatus state={leagues} loading="Loading leagues…" onRetry={retryLeagues} />
          {leagues.status === 'success' && (
            <ChoiceList
              title="Choose Your League"
              choices={leagues.data.map((item) => ({ value: item.key, label: item.name }))}
              onChoose={(key) => choose({ league: key, team: null })}
          />
          )}
        </>
      )}

      {league !== undefined && team === undefined && (
        <>
          <button
            type="button"
            className="back"
            onClick={() => choose({ league: null, team: null})}
          >
            ← Leagues
          </button>
          <p className="eyebrow">{league.name}</p>
          <RequestStatus state={teams} loading="Loading teams…" onRetry={retryTeams} />
          {teams.status === 'success' && (
            <ChoiceList
              title="Choose Your Team"
              choices={teams.data.map((item) => ({ value: item.roster_id, label: item.team_name }))}
              onChoose={(rosterId) => choose({ league: league.key, team: rosterId})}
            />
          )}
        </>
      )}

      {league !== undefined && team !== undefined && (
        <>
          <button
            type="button"
            className="back"
            onClick={() => choose({ league: league.key, team: null})}
          >
            ← Teams
          </button>
          <p className="eyebrow">{league.name}</p>
          <h2 className="team-name">{team.team_name}</h2>
          <RequestStatus state={roster} loading="Loading lineup…" onRetry={retryRoster} />
          {roster.status ==='success' && <LineupView roster={roster.data} />}
        </>
      )}
    </main>
  )
}

export default App
