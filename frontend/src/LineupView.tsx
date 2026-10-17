import type { ReactNode } from 'react'
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
} from './lineup'
import './LineupView.css'

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
      <p className="meta">
        Week {roster.week}, {anyLocked ? 'live scores' : 'projected scores'}
      </p>

      <section className="summary" aria-label="Lineup summary">
        <div className="summary-head">
          <p className="verdict display">{changeVerdict(changes)}</p>
          <p className={isGain(gain) ? 'summary-gain display is-gain' : 'summary-gain display'}>
            {gainLabel(gain)}
          </p>
        </div>
      <p className="summary-totals">
        {hasChanges
          ? `${formatPoints(lineup.current_total)} now, ${formatPoints(lineup.optimal_total)} optimal`
          : `${formatPoints(lineup.optimal_total)} points`}
      </p>

      {hasChanges && (
        <ul className="moves">
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
          Locked players count the points scored so far, everyone else their projection.
        </p>
      )}
      </section>

      <h3>Starters</h3>
      <PlayerTable>
        {lineup.starter_ids.map((id, slot) => (
          <PlayerRow
            key={slot}
            slot={slotLabel(slots[slot])}
            player={id === null ? undefined : byId.get(id)}
            change={id !== null && starting.has(id) ? 'start' : undefined}
            needsPickup={needsPickup.has(slot)}
          />
        ))}
        </PlayerTable>

        <h3>Bench</h3>
        <PlayerTable>
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
        <>
          <h3>Injured Reserve</h3>
          <PlayerTable>
            {reserve.map((player) => (
              <PlayerRow key={player.player_id} slot="IR" player={player} />
            ))}
          </PlayerTable>
        </>
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
            <PositionChip position={player.position} />
            {playerName(player)}
          </span>
          <span className="move-points">{pointsLabel(player)}</span>
        </>
      )}
    </li>
  )
}

// A coloured position label, e.g. WR in blue. Nothing if the position is unknown.
function PositionChip({ position }: { position: string | null }) {
  if (position === null) return null
  return <span className={`chip ${positionClass(position)}`}>{position}</span>
}

// A table with the column headings every player list shares.
function PlayerTable({ children }: { children: ReactNode}) {
  return (
    <div className="table-wrap">
      <table className="players">
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
  )
}

interface PlayerRowProps {
  slot: string
  player: RosterPlayer | undefined
  change?: 'start' | 'sit'
  needsPickup?: boolean
}

// One player, or an empty slot when player is undefined.
function PlayerRow({slot, player, change, needsPickup = false }: PlayerRowProps) {
  if (player === undefined) {
    return (
      <tr className="needs-pickup">
        <th scope="row">{slot}</th>
        <td colSpan={3}>
          Empty <span className="tag tag-pickup">Needs Pickup</span>
        </td>
      </tr>
    )
  }

  return (
    <tr className={needsPickup ? 'needs-pickup' : undefined}>
      <th scope="row">{slot}</th>
      <td>
        <span className="player-name">{playerName(player)}</span>
        {change === 'start' && <span className="tag tag-start">Start</span>}
        {change === 'sit' && <span className="tag tag-sit">Bench</span>}
        {player.locked && <span className="tag tag-locked">Locked</span>}
        {needsPickup && <span className="tag tag-pickup">Needs Pickup</span>}
        <div className="player-details">
          <PositionChip position={player.position} />
          {player.team}
        </div>
      </td>
      <td>{gameLabel(player)}</td>
      <td className="points">{pointsLabel(player)}</td>
    </tr>
  )
}
