import { useId, type ReactNode } from 'react'
import type { RosterPlayer, RosterResponse } from './api'
import {
  changeVerdict,
  formatPoints,
  gainLabel,
  gameLabel,
  isGain,
  lineupChanges,
  playerName,
  pointsLabel,
  positionClass,
  slotLabel,
  slotsNeedingPickup,
  slotClass,
  opponentOf,
  rowState,
} from './lineup'
import './LineupView.css'
import { teamColours  } from './nflTeams'

interface LineupViewProps {
  roster: RosterResponse
}

export function LineupView({ roster }: LineupViewProps) {
  const { players, slots, lineup } = roster
  const byId = new Map(players.map((player) => [player.player_id, player]))

  const changes = lineupChanges(players, lineup)
  const hasChanges = changes.start.length > 0 || changes.bench.length > 0
  const starting = new Set(changes.start)
  const sitting = new Set(changes.bench)
  const needsPickup = slotsNeedingPickup(players, lineup)

  const gain = lineup.optimal_total - lineup.current_total
  const anyLocked = players.some((player) => player.locked)
  const reserve = players.filter((player) => player.reserve)

  return (
    <>
      <section className="summary" aria-label="Lineup summary">
        <div className="scores">
          <div className="score">
            <p className="score-label">Current</p>
            <p className="score-value display">{formatPoints(lineup.current_total)}</p>
          </div>
            <div className="score">
            <p className="score-label">Optimal</p>
            <p className="score-value display">{formatPoints(lineup.optimal_total)}</p>
          </div>
        </div>

        <p className={isGain(gain) ? 'gain-strip is-gain' : 'gain-strip'}>
          {hasChanges ? (
            <>
              <span className="gain-value display">{gainLabel(gain)}</span> with{' '}
              {changeVerdict(changes)}
            </>
          ) : (
            changeVerdict(changes)
          )}
        </p>

        {(hasChanges || needsPickup.size > 0 || anyLocked) && (
          <div className="summary-body">
            {hasChanges && (
              <ul role="list" className="moves">
                {changes.start.map((id) => (
                  <MoveRow key={id} action="start" player={byId.get(id)} />
                ))}
                {changes.bench.map((id) => (
                  <MoveRow key={id} action="bench" player={byId.get(id)} />
                ))}
              </ul>
            )}
            {needsPickup.size > 0 && (
              <p className="summary-note summary-warning">
                Highlighted slots cannot be filled from your roster this week. Pick up a player
                from waivers.
              </p>
            )}
            {anyLocked && (
              <p className="summary-note">
                Locked players current or final scores are used, Sleeper projected points are used for everyone else.
              </p>
            )}
          </div>
        )}
      </section>

      <PlayerTable title="Starters">
        {lineup.starter_ids.map((id, slot) => (
          <PlayerRow
            key={slot}
            slot={slots[slot]}
            player={id === null ? undefined : byId.get(id)}
            change={id !== null && starting.has(id) ? 'start' : undefined}
            needsPickup={needsPickup.has(slot)}
          />
        ))}
        </PlayerTable>

        <PlayerTable title="Bench">
          {lineup.bench_ids.map((id) => (
            <PlayerRow
              key={id}
              slot="BN"
              player={byId.get(id)}
              change={sitting.has(id) ? 'sit' : undefined}
            />
          ))}
        </PlayerTable>

        {reserve.length > 0 && (
          <PlayerTable title="Injured Reserve">
            {reserve.map((player) => (
              <PlayerRow key={player.player_id} slot="IR" player={player} />
            ))}
          </PlayerTable>
      )}
    </>
  )
}

// One line in the summary: who to start or bench, and their points.
function MoveRow({ action, player }: { action: 'start' | 'bench'; player: RosterPlayer | undefined }) {
  return (
    <li className="move">
      <span className={`move-action move-${action}`}>{action === 'start' ? 'Start' : 'Bench'}</span>
      {player === undefined ? (
        <span className="move-name">Unknown Player</span>
      ) : (
        <>
          <span className="move-name">
            <span className="player-name">{playerName(player)}</span>
            <PlayerDetails player={player} />
          </span>
          <span className="move-points">{pointsLabel(player)}</span>
        </>
      )}
    </li>
  )
}

// Position in its colour and the NFL team in theirs, e.g. "QB BUF".
function PlayerDetails({ player }: { player: RosterPlayer}) {
  return (
    <span className="player-details">
      {player.position !== null && (
        <span className={`pos-text ${positionClass(player.position)}`}>{player.position}</span>
      )}
      {player.team !== null && <TeamLabel team={player.team} />}
    </span>
  )
}

// An NFL team code on the team's colour, or plain text for an unknown code.
function TeamLabel({ team }: { team: string }) {
  const colours = teamColours(team)
  if (colours === null) return <span>{team}</span>
  return (
    <span className="team-label" style={{ background: colours.background, color: colours.text }}>
      {team}
    </span>
  )
}

// The game column: the opponent in their team's colour, or BYE, Cancelled or "-".
function GameCell({ player }: { player: RosterPlayer }) {
  const opponent = opponentOf(player)
  if (opponent === null) return <>{gameLabel(player)}</>
  return (
    <span className="game">
      v <TeamLabel team={opponent} />
    </span>
  )
}

// A titled table with the column headings every player list shares. The
// heading also names the table, so a screen reader's table list says
// "Starters" rather than just "table".
function PlayerTable({ title, children }: { title: string; children: ReactNode}) {
  const headingId = useId()
  return (
    <>
      <h3 id={headingId}>{title}</h3>
      <div className="table-wrap">
        <table className="players" aria-labelledby={headingId}>
          <thead>
            <tr>
              <th scope="col">Slot</th>
              <th scope="col">Player</th>
              <th scope="col">Game</th>
              <th scope="col" className="points">
                Points
              </th>
            </tr>
          </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  </>
  )
}

interface PlayerRowProps {
  slot: string
  player: RosterPlayer | undefined
  change?: 'start' | 'sit'
  needsPickup?: boolean
}

// One player, or an empty slot when player is undefined. slot is the raw slot
// type (QB, WRRB_FLEX, BN, IR), shown as a coloured cell filling the row's height.
function PlayerRow({slot, player, change, needsPickup = false }: PlayerRowProps) {
  const slotCell = (
    <th scope="row" className="slot-cell">
      <span className={`slot-chip ${slotClass(slot)}`}>{slotLabel(slot)}</span>
    </th>
  )

  if (player === undefined) {
    return (
      <tr className="needs-pickup">
        {slotCell}
        <td colSpan={3}>
          Empty <span className="tag tag-pickup">Needs Pickup</span>
        </td>
      </tr>
    )
  }

  const state = rowState(player)
  const rowClasses = [state !== null && `is-${state}`, needsPickup && 'needs-pickup']
    .filter((name) => name !== false)
    .join(' ')

  return (
    <tr className={rowClasses === '' ? undefined : rowClasses}>
      {slotCell}
      <td>
        <span className="player-name">{playerName(player)}</span>
        {change === 'start' && <span className="tag tag-start">Start</span>}
        {change === 'sit' && <span className="tag tag-sit">Bench</span>}
        {player.locked && <span className="tag tag-locked">Locked</span>}
        {needsPickup && <span className="tag tag-pickup">Needs Pickup</span>}
        <PlayerDetails player={player} />
      </td>
      <td>
        <GameCell player={player} />
        </td>
      <td className="points">{pointsLabel(player)}</td>
    </tr>
  )
}
