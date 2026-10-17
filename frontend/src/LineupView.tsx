import type { ReactNode } from 'react'
import type { RosterPlayer, RosterResponse } from './api'
import {
    formatPoints,
    gameLabel,
    lineupChanges,
    playerName,
    pointsLabel,
    slotLabel,
    slotsNeedingPickup,
    gainLabel,
    isGain,
    playerDetails,
} from './lineup'
import './LineupView.css'

interface LineupViewProps {
  roster: RosterResponse
}

export function LineupView({ roster }: LineupViewProps) {
  const { players, slots, lineup } = roster
  const byId = new Map(players.map((player) => [player.player_id, player]))

  const changes = lineupChanges(players, lineup)
  const starting = new Set(changes.start)
  const sitting = new Set(changes.bench)
  const needsPickup = slotsNeedingPickup(players, lineup)

  const gain = lineup.optimal_total - lineup.current_total
  const anyLocked = players.some((player) => player.locked)
  const reserve = players.filter((player) => player.reserve)

  return (
    <section>
      <p className="Note">
        Week {roster.week}, {roster.season}
      </p>

      <dl className="totals">
        <div>
          <dt>Current</dt>
          <dd>{formatPoints(lineup.current_total)}</dd>
        </div>
        <div>
          <dt>Optimal</dt>
          <dd>{formatPoints(lineup.optimal_total)}</dd>
        </div>
        <div className={isGain(gain) ?  'gain' : undefined}>
          <dt>Gain</dt>
          <dd>{gainLabel(gain)}</dd>
        </div>
      </dl>
      <p className="Note">
        {anyLocked
        ? 'Live totals: locked players count their points so far, everyone else their projection.'
          : 'Projected totals.'}
      </p>

      <h3>Changes</h3>
      {changes.start.length === 0 && changes.bench.length === 0 ? (
        <p>Your lineup is already optimal.</p>
      ) : (
        <ul className="changes">
          {changes.start.map((id) => (
            <li key={id}>
              <span className="tag tag-start">Start</span>
               {nameOf(byId.get(id))}
            </li>
          ))}
          {changes.bench.map((id) => (
            <li key={id}>
              <span className="tag tag-sit">Bench</span>
              {nameOf(byId.get(id))}
            </li>
          ))}
        </ul>
      )}
      {needsPickup.size > 0 && (
        <p className="note">
          Flagged slots can’t be filled from your roster this week: they need a waiver pickup.
        </p>
      )}

      <h3>Optimal Starters</h3>
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
    </section>
  )
}

function nameOf(player: RosterPlayer | undefined): string {
  return player === undefined ? 'Unknown Player' : playerName(player)
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
            <th scope="col">Pos</th>
            <th scope="col">Game</th>
            <th scope="col" className="Points">
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
        <td colSpan={4}>
          Empty <span className="tag tag-pickup">Needs Pickup</span>
        </td>
      </tr>
    )
  }

  return (
    <tr className={needsPickup ? 'needs-pickup' : undefined}>
      <th scope="row">{slot}</th>
      <td>
        {playerName(player)}
        {change === 'start' && <span className="tag tag-start">Start</span>}
        {change === 'sit' && <span className="tag tag-sit">Bench</span>}
        {player.locked && <span className="tag tag-locked">Locked</span>}
        {needsPickup && <span className="tag tag-pickup">Needs Pickup</span>}
      </td>
      <td>{player.position ?? '-'}</td>
      <td>{gameLabel(player)}</td>
      <td className="points">{pointsLabel(player)}</td>
    </tr>
  )
}
