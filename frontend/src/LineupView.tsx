import { Fragment, useId, type ReactNode } from 'react'
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
  benchOrder,
  shirtNumberLabel,
} from './lineup'
import './LineupView.css'
import { teamColours } from './nflTeams'

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
  const bench = benchOrder(players, lineup.bench_ids)

  return (
    <>
      <section className="summary" aria-label="Lineup Summary">
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
                Highlighted slots cannot be filled from your roster this week. Pick up a player from
                waivers.
              </p>
            )}
            {anyLocked && (
              <p className="summary-note">
                Totals use live or final points for locked players. Sleeper's projections are used
                for players yet to start.
              </p>
            )}
          </div>
        )}
      </section>

      <PlayerTable title="Starters">
        {lineup.starter_ids.map((id, slot) =>
          id === null ? (
            <EmptyRow key={slot} slot={slots[slot]} />
          ) : (
            <PlayerRow
              key={slot}
              slot={slots[slot]}
              player={byId.get(id)}
              change={starting.has(id) ? 'start' : undefined}
              needsPickup={needsPickup.has(slot)}
            />
          ),
        )}
      </PlayerTable>

      <PlayerTable title="Bench">
        {bench.map((id) => (
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

// One line in the summary: who to start or sit, and their points.
function MoveRow({
  action,
  player,
}: {
  action: 'start' | 'bench'
  player: RosterPlayer | undefined
}) {
  return (
    <li className="move">
      <span className={`move-action move-${action}`}>{action === 'start' ? 'Start' : 'Sit'}</span>
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

// Shirt number, position in its colour and the NFL team in theirs, with a dot
// between each, e.g. "QB · BUF · #17". Anything missing is left out along with
// its dot. The dots are decoration, hidden from screen readers.
function PlayerDetails({ player }: { player: RosterPlayer }) {
  const shirtNumber = shirtNumberLabel(player)
  const details: { key: string; content: ReactNode }[] = []
  if (player.position !== null) {
    details.push({
      key: 'position',
      content: (
        <span className={`pos-text ${positionClass(player.position)}`}>{player.position}</span>
      ),
    })
  }
  if (player.team !== null) {
    details.push({ key: 'team', content: <TeamLabel team={player.team} /> })
  }
  if (shirtNumber !== null) {
    details.push({ key: 'number', content: <span className="shirt-number">{shirtNumber}</span> })
  }

  return (
    <span className="player-details">
      {details.map(({ key, content }, index) => (
        <Fragment key={key}>
          {index > 0 && (
            <span className="detail-separator" aria-hidden="true">
              ·
            </span>
          )}
          {content}
        </Fragment>
      ))}
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

// The fixture column: the opponent in their team's colour, BYE as a violet
// label to match the row, or Cancelled or "-".
function GameCell({ player }: { player: RosterPlayer }) {
  if (player.game_status === 'bye') return <span className="bye-label">{gameLabel(player)}</span>
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
function PlayerTable({ title, children }: { title: string; children: ReactNode }) {
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
              <th scope="col">Fixture</th>
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

// The slot type (QB, WRRB_FLEX, BN, IR) as a coloured chip filling the cell's height.
function SlotCell({ slot }: { slot: string }) {
  return (
    <th scope="row" className="slot-cell">
      <span className={`slot-chip ${slotClass(slot)}`}>{slotLabel(slot)}</span>
    </th>
  )
}

// A starting slot nobody on the roster can fill.
function EmptyRow({ slot }: { slot: string }) {
  return (
    <tr className="needs-pickup">
      <SlotCell slot={slot} />
      <td colSpan={3}>
        Empty <span className="tag tag-pickup">Waiver</span>
      </td>
    </tr>
  )
}

// One player. player is undefined when the lineup names an id that isn't in
// the roster's player list; the summary shows that as Unknown Player too.
function PlayerRow({ slot, player, change, needsPickup = false }: PlayerRowProps) {
  const changeTag = (
    <>
      {change === 'start' && <span className="tag tag-start">Start</span>}
      {change === 'sit' && <span className="tag tag-sit">Sit</span>}
    </>
  )

  if (player === undefined) {
    return (
      <tr>
        <SlotCell slot={slot} />
        <td colSpan={3}>
          <span className="player-name">Unknown Player</span>
          {changeTag}
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
      <SlotCell slot={slot} />
      <td>
        <span className="player-name">{playerName(player)}</span>
        {player.locked && <LockIcon />}
        {changeTag}
        {needsPickup && <span className="tag tag-pickup">Waiver</span>}
        <PlayerDetails player={player} />
      </td>
      <td>
        <GameCell player={player} />
      </td>
      <td className="points">{pointsLabel(player)}</td>
    </tr>
  )
}

// A padlock straight after a locked player's name. The accessible name gives
// screen readers the same cue the icon gives everyone else; questionable and
// out will sit here too, once there's a fresh injury source.
function LockIcon() {
  return (
    <svg className="status-icon" viewBox="0 0 16 16" role="img" aria-label="Locked">
      <path d="M5 7.5V5a3 3 0 0 1 6 0v2.5" fill="none" stroke="currentColor" strokeWidth="2" />
      <rect x="2.5" y="7" width="11" height="8" rx="1.5" fill="currentColor" />
    </svg>
  )
}
