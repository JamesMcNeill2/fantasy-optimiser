import { describe, expect, it } from 'vitest'
import type { OptimalLineup, RosterPlayer } from './api'
import {
  gameLabel,
  lineupChanges,
  playerName,
  pointsLabel,
  selectionValue,
  slotsNeedingPickup,
  slotLabel,
  gainLabel,
  isGain,
  changeVerdict,
  positionClass,
  slotClass,
  weekLabel,
  opponentOf,
  rowState,
} from './lineup'

// A typical unlocked player. Each test overrides only the fields it cares about.
function player(overrides: Partial<RosterPlayer> = {}): RosterPlayer {
  return {
    player_id: '1',
    starter_slot: null,
    reserve: false,
    first_name: 'Test',
    last_name: 'Player',
    position: 'WR',
    team: 'KC',
    injury_status: null,
    projected_points: 10,
    opponent: 'LV',
    game_status: 'pre_game',
    locked: false,
    actual_points: null,
    ...overrides,
  }
}

function lineup(starter_ids: (string | null)[]): OptimalLineup {
  return { starter_ids, bench_ids: [], optimal_total: 0, current_total: 0 }
}

describe('selectionValue', () => {
  it('uses the projection', () => {
    expect(selectionValue(player({ projected_points: 12.5 }))).toBe(12.5)
  })

  it('counts a missing projection as 0', () => {
    expect(selectionValue(player({ projected_points: null }))).toBe(0)
  })

  it('counts a bye or cancelled game as 0, even with a projection', () => {
    expect(selectionValue(player({ game_status: 'bye' }))).toBe(0)
    expect(selectionValue(player({ game_status: 'canceled' }))).toBe(0)
  })
})

describe('playerName', () => {
  it('joins first and last names', () => {
    expect(playerName(player({ first_name: 'Kansas City', last_name: 'Chiefs' }))).toBe(
      'Kansas City Chiefs',
    )
  })

  it('falls back when there are no names', () => {
    expect(playerName(player({ first_name: null, last_name: null }))).toBe('Unknown Player')
  })
})

describe('gameLabel', () => {
  it('shows the opponent', () => {
    expect(gameLabel(player({ opponent: 'LV' }))).toBe('v LV')
  })

  it('labels a bye from game_status', () => {
    expect(gameLabel(player({ game_status: 'bye', opponent: null }))).toBe('BYE')
  })

  it('does not call a missing projection a bye', () => {
    expect(gameLabel(player({ projected_points: null }))).toBe('v LV')
  })

  it('labels a cancelled game', () => {
    expect(gameLabel(player({ game_status: 'canceled' }))).toBe('Cancelled')
  })

  it('shows a dash when the game is unknown', () => {
    expect(gameLabel(player({ game_status: null, opponent: null }))).toBe('-')
  })
})

describe('pointsLabel', () => {
  it('shows the projection to two decimal places', () => {
    expect(pointsLabel(player({ projected_points: 12.456 }))).toBe('12.46')
  })

  it('shows a dash when there is no projection', () => {
    expect(pointsLabel(player({ projected_points: null }))).toBe('-')
  })

  it('shows a dash on a bye, even with a stale projection', () => {
    expect(pointsLabel(player({ game_status: 'bye', projected_points: 8 }))).toBe('-')
  })

  it('shows points so far for a locked player', () => {
    expect(pointsLabel(player({ locked: true, game_status: 'in_game', actual_points: 7.2 }))).toBe(
      '7.20',
    )
  })

  it('counts a locked player with no points yet as 0', () => {
    expect(pointsLabel(player({ locked: true, game_status: 'in_game' }))).toBe('0.00')
  })
})

describe('lineupChanges', () => {
  it('ignores a starter moved between equivalent slots', () => {
    // Player 2 is in the WR slot and 3 in the flex; the optimiser swaps them
    const players = [
      player({ player_id: '2', starter_slot: 0 }),
      player({ player_id: '3', starter_slot: 1 }),
    ]
    expect(lineupChanges(players, lineup(['3', '2']))).toEqual({ start: [], bench: [] })
  })

  it('lists who comes in and who goes out', () => {
    const players = [
      player({ player_id: '2', starter_slot: 0 }),
      player({ player_id: '3', starter_slot: 1 }),
      player({ player_id: '4' }),
    ]
    expect(lineupChanges(players, lineup(['2', '4']))).toEqual({ start: ['4'], bench: ['3'] })
  })

  it('benches a starter whose slot the optimiser leaves empty', () => {
    const players = [player({ player_id: '2', starter_slot: 0 })]
    expect(lineupChanges(players, lineup([null]))).toEqual({ start: [], bench: ['2'] })
  })
})

describe('slotsNeedingPickup', () => {
  it('flags an empty slot', () => {
    expect(slotsNeedingPickup([], lineup([null]))).toEqual(new Set([0]))
  })

  it('flags a slot whose best option is on a bye', () => {
    const players = [player({ player_id: '2', game_status: 'bye', opponent: null })]
    expect(slotsNeedingPickup(players, lineup(['2']))).toEqual(new Set([0]))
  })

  it('does not flag a locked starter with no points yet', () => {
    const players = [player({ player_id: '2', locked: true, game_status: 'in_game' })]
    expect(slotsNeedingPickup(players, lineup(['2']))).toEqual(new Set())
  })

  it('does not flag a slot with a projected starter', () => {
    const players = [player({ player_id: '2' })]
    expect(slotsNeedingPickup(players, lineup(['2']))).toEqual(new Set())
  })
})

describe('slotLabel', () => {
  it('shortens the flex slots', () => {
    expect(slotLabel('WRRB_FLEX')).toBe('W/R')
  })

  it('leaves other slots unchanged', () => {
    expect(slotLabel('QB')).toBe('QB')
  })
})

describe('gainLabel', () => {
  it('shows a gain with a plus sign', () => {
    expect(gainLabel(3.456)).toBe('+3.46')
  })

  it('shows no sign when there is no gain', () => {
    expect(gainLabel(0)).toBe('0.00')
  })

  it('treats a gain that rounds to zero as none', () => {
    expect(gainLabel(0.004)).toBe('0.00')
    expect(gainLabel(-0.001)).toBe('0.00')
  })
})

describe('isGain', () => {
  it('is true for a gain', () => {
    expect(isGain(0.01)).toBe(true)
  })

  it('is false for no gain, even with rounding noise', () => {
    expect(isGain(0)).toBe(false)
    expect(isGain(1e-14)).toBe(false)
  })
})

describe('changeVerdict', () => {
  it('says when there is nothing to change', () => {
    expect(changeVerdict({ start: [], bench: [] })).toBe('Your lineup is optimal')
  })

  it('counts one swap as one change', () => {
    expect(changeVerdict({ start: ['4'], bench: ['3'] })).toBe('1 change')
  })

  it('counts a benching into an empty slot as a change', () => {
    expect(changeVerdict({ start: [], bench: ['2'] })).toBe('1 change')
  })

  it('counts several swaps', () => {
    expect(changeVerdict({ start: ['4', '5'], bench: ['2', '3'] })).toBe('2 changes')
  })
})

describe('positionClass', () => {
  it('colours the usual positions', () => {
    expect(positionClass('WR')).toBe('pos-wr')
    expect(positionClass('DEF')).toBe('pos-def')
  })

  it('gives anything else a neutral colour', () => {
    expect(positionClass('LB')).toBe('pos-other')
  })
})

describe('slotClass', () => {
  it('colours a position slot like the position', () => {
    expect(slotClass('QB')).toBe('pos-qb')
  })

  it('gives every flex slot the same colour', () => {
    expect(slotClass('WRRB_FLEX')).toBe('slot-flex')
    expect(slotClass('SUPER_FLEX')).toBe('slot-flex')
  })

  it('has its own classes for the bench and IR', () => {
    expect(slotClass('BN')).toBe('slot-bn')
    expect(slotClass('IR')).toBe('slot-ir')
  })
})

describe('weekLabel', () => {
  it('shows the week', () => {
    const roster = { players: [player()], season: '2026', week: 6, slots: [], lineup: lineup([]) }
    expect(weekLabel(roster)).toBe('Week 6')
  })
})

describe('opponentOf', () => {
  it('gives the opponent for a game still to play', () => {
    expect(opponentOf(player({ opponent: 'LV' }))).toBe('LV')
  })

  it('gives null on a bye or for a cancelled game', () => {
    expect(opponentOf(player({ game_status: 'bye', opponent: null }))).toBeNull()
    expect(opponentOf(player({ game_status: 'canceled' }))).toBeNull()
  })
})

describe('rowState', () => {
  it('shades a locked player', () => {
    expect(rowState(player({ locked: true, game_status: 'in_game' }))).toBe('locked')
  })

  it('shades a player on a bye', () => {
    expect(rowState(player({ game_status: 'bye', opponent: null }))).toBe('bye')
  })

  it('leaves everyone else alone', () => {
    expect(rowState(player())).toBeNull()
  })
})
