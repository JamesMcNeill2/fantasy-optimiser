import { useEffect, useRef } from 'react'
import {
  leaguesPath,
  rosterPath,
  teamsPath,
  type League,
  type RosterResponse,
  type Team,
} from './api'
import { ChoiceList } from './ChoiceList'
import { LineupView } from './LineupView'
import { RequestStatus } from './RequestStatus'
import { useApi } from './useApi'
import { trustedId, useSelection } from './urlState'
import { weekLabel } from './lineup'
import { PageHeader } from './PageHeader'
import { SelectionLink } from './SelectionLink'

const APP_NAME = "Mac's Fantasy Lineup Optimiser"

function App() {
  const [selection, choose] = useSelection()

  // All three requests start from the URL at once, so a shared or refreshed
  // lineup link doesn't wait for each list in turn. An id is trusted until
  // its list arrives and proves it stale; then the page drops back a level.
  const [leagues, retryLeagues] = useApi<League[]>(leaguesPath)
  const leagueList = leagues.status === 'success' ? leagues.data : undefined
  const leagueKey = trustedId(selection.league, leagueList, (item) => item.key)

  const [teams, retryTeams] = useApi<Team[]>(leagueKey === null ? null : teamsPath(leagueKey))
  const teamList = teams.status === 'success' ? teams.data : undefined
  const rosterId =
    leagueKey === null ? null : trustedId(selection.team, teamList, (item) => item.roster_id)

  const [roster, retryRoster] = useApi<RosterResponse>(
    leagueKey === null || rosterId === null ? null : rosterPath(leagueKey, rosterId),
  )

  // Which page the URL asks for, and the names its header needs
  // (undefined until their lists arrive)
  const page = leagueKey === null ? 'leagues' : rosterId === null ? 'teams' : 'lineup'
  const league = leagueList?.find((item) => item.key === leagueKey)
  const team = teamList?.find((item) => item.roster_id === rosterId)

  const leaguesRequest = { state: leagues, onRetry: retryLeagues }
  const teamsRequest = { state: teams, onRetry: retryTeams }
  const rosterRequest = { state: roster, onRetry: retryRoster }

  // After a navigation (a click, Back or Forward), move focus to the new
  // page's heading. Not on first load: the selection the page opened with
  // is skipped.
  const headingRef = useRef<HTMLHeadingElement>(null)
  const previousSelection = useRef(selection)
  useEffect(() => {
    if (previousSelection.current === selection) return
    previousSelection.current = selection
    headingRef.current?.focus({ preventScroll: true })
  }, [selection])

  // The tab and history title: the page's own heading, then the app's name
  const heading = page === 'lineup' ? team?.team_name : page === 'teams' ? league?.name : undefined
  const pageTitle = heading === undefined ? APP_NAME : `${heading} · ${APP_NAME}`
  useEffect(() => {
    document.title = pageTitle
  }, [pageTitle])

  return (
    <>
      <header className="site-header">
        <h1>
          <SelectionLink to={{ league: null, team: null }} onNavigate={choose}>
            {APP_NAME}
          </SelectionLink>
        </h1>
      </header>

      <main>
        {page === 'leagues' && (
          <>
            <PageHeader title="Choose Your League" onNavigate={choose} headingRef={headingRef} />
            <RequestStatus requests={[leaguesRequest]} loading="Loading leagues…" />
            {leagueList !== undefined && (
              <ChoiceList
                choices={leagueList.map((item) => ({ value: item.key, label: item.name }))}
                size="large"
                linkTo={(key) => ({ league: key, team: null })}
                onNavigate={choose}
              />
            )}
          </>
        )}

        {page === 'teams' && (
          <>
            {league !== undefined && (
              <PageHeader
                title={league.name}
                subtitle="Choose Your Team"
                back={{ label: 'All Leagues', to: { league: null, team: null } }}
                onNavigate={choose}
                headingRef={headingRef}
              />
            )}
            <RequestStatus requests={[leaguesRequest, teamsRequest]} loading="Loading teams…" />
            {league !== undefined && teamList !== undefined && (
              <ChoiceList
                choices={teamList.map((item) => ({ value: item.roster_id, label: item.team_name }))}
                size="regular"
                linkTo={(rosterId) => ({ league: league.key, team: rosterId })}
                onNavigate={choose}
              />
            )}
          </>
        )}

        {page === 'lineup' && (
          <>
            {league !== undefined && team !== undefined && (
              <PageHeader
                title={team.team_name}
                subtitle={roster.status === 'success' ? weekLabel(roster.data) : undefined}
                back={{ label: league.name, to: { league: league.key, team: null } }}
                onNavigate={choose}
                headingRef={headingRef}
              />
            )}
            <RequestStatus
              requests={[leaguesRequest, teamsRequest, rosterRequest]}
              loading="Loading lineup…"
            />
            {league !== undefined && team !== undefined && roster.status === 'success' && (
              <LineupView roster={roster.data} />
            )}
          </>
        )}
      </main>
    </>
  )
}

export default App
