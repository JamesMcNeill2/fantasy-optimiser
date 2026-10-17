import { useState } from 'react'
import {
  leaguesPath,
  rosterPath,
  teamsPath,
  type League,
  type RosterResponse,
  type Team
} from './api'
import { RequestStatus } from './RequestStatus'
import { Picker } from './Picker'
import { useApi } from './useApi'
import { readSelection, writeSelection, type Selection } from './urlState'
import { LineupView } from './LineupView'

function App() {
  const [selection, setSelection] = useState(readSelection)

  const [leagues, retryLeagues] = useApi<League[]>(leaguesPath)
  // Only use the league from the URL if it's in the list
  const leagueKey =
    leagues.status === 'success' && leagues.data.some((league) => league.key === selection.league)
      ? selection.league
      : null

  const [teams, retryTeams] = useApi<Team[]>(leagueKey === null ? null : teamsPath(leagueKey))
  // Likewise for the team
  const rosterId =
    teams.status === 'success' && teams.data.some((team) => team.roster_id === selection.team)
      ? selection.team
      : null

  const [roster, retryRoster] = useApi<RosterResponse>(
    leagueKey === null || rosterId === null ? null : rosterPath(leagueKey, rosterId),
  )

  function choose(next: Selection) {
    setSelection(next)
    writeSelection(next)
  }

  return (
    <main>
      <h1>Macs Fantasy Lineup Optimiser</h1>

      <div className="pickers">
        <RequestStatus state={leagues} loading="Loading leagues…" onRetry={retryLeagues} />
        {leagues.status === 'success' && (
          <Picker
            label="League"
            placeholder="Choose A League"
            options={leagues.data.map((league) => ({ value: league.key, label: league.name }))}
            value={leagueKey}
            onChange={(league) => choose({ league, team: null })}
          />
        )}

        <RequestStatus state={teams} loading="Loading teams…" onRetry={retryTeams} />
        {teams.status === 'success' && (
          <Picker
            label="Team"
            placeholder="Choose A Team"
            options={teams.data.map((team) => ({value: team.roster_id, label: team.team_name }))}
            value={rosterId}
            onChange={(team) => choose({league: leagueKey, team})}
          />
        )}
      </div>

      <RequestStatus state={roster} loading="Loading roster…" onRetry={retryRoster} />
      {roster.status ==='success' && <LineupView roster={roster.data} />}
    </main>
  )
}

export default App
