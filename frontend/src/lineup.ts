// Display rules for the lineup view. Pure functions: they only read their
// arguments and return a result, so they're easy to test.

import type { OptimalLineup, RosterPlayer } from './api'

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
  return points.toFixed(1)
}

export function playerName(player: RosterPlayer): string {
  const name = [player.first_name, player.last_name].filter((part) => part !== null).join(' ')
  return name === '' ? 'Unknown Player' : name
}

// The game column. "BYE" comes from game_status, never from a missing
// projection, which also means Out or on IR.
export function gameLabel(player: RosterPlayer): string {
  if (player.game_status === 'bye') return 'BYE'
  if (player.game_status === 'canceled') return 'Cancelled'
  return player.opponent === null ? '-': `v ${player.opponent}`
}

// The points column.
// Locked players show points so far; everyone else their projection,
// or the injury status (or "–") when there isn't one.
export function pointsLabel(player: RosterPlayer): string {
  if (player.locked) return formatPoints(player.actual_points ?? 0)
  if (player.game_status !== null && NO_POINTS_STATUSES.has(player.game_status)) return '-'
  if (player.projected_points !== null) return formatPoints(player.projected_points)
  return player.injury_status ?? '-'
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
// or its best available player scores 0. The fix is a waiver pickup.
export function slotsNeedingPickup(players: RosterPlayer[], lineup: OptimalLineup): Set<number>{
  const byId = new Map(players.map((player) => [player.player_id, player]))
  const flagged = new Set<number>()
  lineup.starter_ids.forEach((id, slot) => {
    const player = id === null ? undefined : byId.get(id)
    if (player === undefined || (!player.locked && selectionValue(player) <= 0)) {
      flagged.add(slot)
    }
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
