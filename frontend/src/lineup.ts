// Display rules for the lineup view. Pure functions: they only read their
// arguments and return a result, so they're easy to test.

import type { OptimalLineup, RosterPlayer, RosterResponse } from './api'

// Sleeper's spelling is "canceled".
// These score nothing, matching the optimiser's NO_POINTS_STATUSES.
const NO_POINTS_STATUSES = new Set(['bye', 'canceled'])

// What a player is worth when choosing a lineup, as the optimiser's
// selection_value: no projection, a bye or a cancelled game count 0.
export function selectionValue(player: RosterPlayer): number {
  if (player.game_status !== null && NO_POINTS_STATUSES.has(player.game_status)) return 0
  return player.projected_points ?? 0
}

export function formatPoints(points: number): string {
  return points.toFixed(2)
}

// The gain as shown: a + for a real gain (e.g. +1.23), and no sign when it
// rounds to zero (0.00).
export function gainLabel(gain: number): string {
  const rounded = Math.round(gain * 100) / 100
  if (rounded === 0) return formatPoints(0)
  return rounded > 0 ? `+${formatPoints(rounded)}` : formatPoints(rounded)
}

// Whether the gain is worth highlighting: more than zero once rounded.
export function isGain(gain: number): boolean {
  return Math.round(gain * 100) > 0
}

export function playerName(player: RosterPlayer): string {
  const name = [player.first_name, player.last_name].filter((part) => part !== null).join(' ')
  return name === '' ? 'Unknown Player' : name
}

// The opposing team when there's a game to play, or null on a bye, for a
// cancelled game, or when the game is unknown.
export function opponentOf(player: RosterPlayer): string | null {
  if (player.game_status !== null && NO_POINTS_STATUSES.has(player.game_status)) return null
  return player.opponent
}

// The game column. "BYE" comes from game_status, never from a missing
// projection, which can mean other things (e.g. an injured player).
export function gameLabel(player: RosterPlayer): string {
  if (player.game_status === 'bye') return 'BYE'
  if (player.game_status === 'canceled') return 'Cancelled'
  const opponent = opponentOf(player)
  return opponent === null ? '-' : `v ${opponent}`
}

// The points column: locked players show points so far; everyone else their
// projection, or "-" when there isn't one.
export function pointsLabel(player: RosterPlayer): string {
  if (player.locked) return formatPoints(player.actual_points ?? 0)
  if (player.game_status !== null && NO_POINTS_STATUSES.has(player.game_status)) return '-'
  return player.projected_points === null ? '-' : formatPoints(player.projected_points)
}

export interface LineupChanges {
  start: string[] // player IDs to move into the lineup, in slot order
  bench: string[] // player IDs to take out, in slot order
}

// Who starts and who sits, compared by player rather than by slot, so a
// starter moved between equivalent slots (a WR into the flex) isn't a change.
export function lineupChanges(players: RosterPlayer[], lineup: OptimalLineup): LineupChanges {
  const currentStarters = players
    .filter((player) => player.starter_slot !== null)
    .sort((a, b) => (a.starter_slot ?? 0) - (b.starter_slot ?? 0))
    .map((player) => player.player_id)
  const optimalStarters = lineup.starter_ids.filter((id) => id !== null)

  const current = new Set(currentStarters)
  const optimal = new Set(optimalStarters)
  return {
    start: optimalStarters.filter((id) => !current.has(id)),
    bench: currentStarters.filter((id) => !optimal.has(id)),
  }
}

// Starting slots (by index) that no lineup change can fix: the slot is empty,
// or its unlocked starter scores 0. The fix is a waiver pickup. A starter
// missing from the player list isn't flagged: someone is in the slot, the
// page just can't show who.
export function slotsNeedingPickup(players: RosterPlayer[], lineup: OptimalLineup): Set<number> {
  const byId = new Map(players.map((player) => [player.player_id, player]))
  const flagged = new Set<number>()
  lineup.starter_ids.forEach((id, slot) => {
    if (id === null) {
      flagged.add(slot)
      return
    }
    const player = byId.get(id)
    if (player !== undefined && !player.locked && selectionValue(player) <= 0) flagged.add(slot)
  })
  return flagged
}

// Short names for the flex slots, as Sleeper shows them. Others are unchanged.
const SLOT_LABELS = new Map([
  ['WRRB_FLEX', 'W/R'],
  ['REC_FLEX', 'W/T'],
  ['FLEX', 'W/R/T'],
  ['SUPER_FLEX', 'SF'],
])

export function slotLabel(slot: string): string {
  return SLOT_LABELS.get(slot) ?? slot
}

// The summary's headline: how many swaps the lineup needs.
export function changeVerdict(changes: LineupChanges): string {
  const count = Math.max(changes.start.length, changes.bench.length)
  if (count === 0) return 'Your Lineup Is Optimal'
  return count === 1 ? '1 change' : `${count} changes`
}

const POSITIONS = new Set(['QB', 'RB', 'WR', 'TE', 'K', 'DEF'])

// The CSS class that colours a position chip; anything unusual gets a neutral one.
export function positionClass(position: string): string {
  return POSITIONS.has(position) ? `pos-${position.toLowerCase()}` : 'pos-other'
}

const FLEX_SLOTS = new Set(['WRRB_FLEX', 'REC_FLEX', 'FLEX', 'SUPER_FLEX'])

// The CSS class that colours a slot chip: a position's colour for a position
// slot, one shared colour for the flex slots, and quieter ones for BN and IR
export function slotClass(slot: string): string {
  if (POSITIONS.has(slot)) return positionClass(slot)
  if (FLEX_SLOTS.has(slot)) return 'slot-flex'
  if (slot === 'BN') return 'slot-bn'
  if (slot === 'IR') return 'slot-ir'
  return 'pos-other'
}

// The line under the team name on the lineup page, e.g. "Week 6".
export function weekLabel(roster: RosterResponse): string {
  return `Week ${roster.week}`
}

// How a player's whole table row is shaded: locked players and players on a
// bye can't help this week. Out and questionable can join this once there's
// a fresh injury source.
export type RowState = 'locked' | 'bye' | null

export function rowState(player: RosterPlayer): RowState {
  if (player.locked) return 'locked'
  if (player.game_status === 'bye') return 'bye'
  return null
}
