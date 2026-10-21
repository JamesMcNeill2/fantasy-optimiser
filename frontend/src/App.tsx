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
import { APP_NAME } from './appName'

function App() {
  const [selection, choose] = useSelection()

  // All three requests start from the URL at once. The lineup page needs only
  // the roster, which carries the league and team names for its header; the
  // lists are there for going back a level, and to catch a stale id. An id is
  // trusted until its list arrives and proves it stale; then the page drops
  // back a level.
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
  const rosterData = roster.status === 'success' ? roster.data : undefined

  // Which page the URL asks for, and the league its team picker is for
  // (undefined until the leagues list arrives)
  const page = leagueKey === null ? 'leagues' : rosterId === null ? 'teams' : 'lineup'
  const league = leagueList?.find((item) => item.key === leagueKey)

  // The teams page's header waits for the team list as well as the league's
  // name (or for the list's error, so the header still sits above it). It then
  // arrives with the boxes, instead of appearing above "Loading teams…" and
  // pushing it down.
  const teamsHeaderShown = league !== undefined && teams.status !== 'loading'

  // Whether the page's heading is on screen yet: the lineup page's arrives
  // with the roster
  const headingShown =
    page === 'leagues' || (page === 'teams' ? teamsHeaderShown : rosterData !== undefined)

  const leaguesRequest = { state: leagues, onRetry: retryLeagues }
  const teamsRequest = { state: teams, onRetry: retryTeams }
  const rosterRequest = { state: roster, onRetry: retryRoster }

  // After a navigation (a click, Back or Forward), move focus to the new
  // page's heading, as soon as it's on screen: the lineup's heading arrives
  // with the roster. Not on first load: the selection the page opened with
  // is skipped.
  const headingRef = useRef<HTMLHeadingElement>(null)
  const previousSelection = useRef(selection)
  const focusPending = useRef(false)
  useEffect(() => {
    if (previousSelection.current !== selection) {
      previousSelection.current = selection
      focusPending.current = true
    }
    if (focusPending.current && headingRef.current !== null) {
      focusPending.current = false
      headingRef.current.focus({ preventScroll: true })
    }
  }, [selection, headingShown])

  // The tab and history title: the page's own heading, then the app's name
  const heading =
    page === 'lineup' ? rosterData?.team_name : page === 'teams' ? league?.name : undefined
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
            {league !== undefined && teamsHeaderShown && (
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
                linkTo={(id) => ({ league: league.key, team: id })}
                onNavigate={choose}
              />
            )}
          </>
        )}

        {page === 'lineup' && (
          <>
            {rosterData !== undefined && (
              <PageHeader
                title={rosterData.team_name}
                subtitle={weekLabel(rosterData)}
                back={{ label: rosterData.league_name, to: { league: leagueKey, team: null } }}
                onNavigate={choose}
                headingRef={headingRef}
              />
            )}
            {/* While the roster loads, only it counts. If it fails, the lists
                come first, so a stale id's 404 waits for the list that corrects
                it; a failed list alone never hides a lineup that arrived. */}
            <RequestStatus
              requests={
                roster.status === 'error'
                  ? [leaguesRequest, teamsRequest, rosterRequest]
                  : [rosterRequest]
              }
              loading="Loading lineup…"
            />
            {rosterData !== undefined && <LineupView roster={rosterData} />}
          </>
        )}
      </main>
    </>
  )
}

export default App
