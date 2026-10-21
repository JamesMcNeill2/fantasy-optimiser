// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { RosterPlayer, RosterResponse } from './api'
import { LineupView } from './LineupView'
import { setUpBrowserTests } from './testHelpers'

setUpBrowserTests()

// An unlocked player yet to play. Each player overrides only what it needs.
function player(overrides: Partial<RosterPlayer>): RosterPlayer {
  return {
    player_id: '1',
    starter_slot: null,
    reserve: false,
    first_name: 'Test',
    last_name: 'Player',
    shirt_number: null,
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

// A locked starter, an unlocked starter and a locked bench player. Already
// optimal, so no Start or Bench tags get in the way.
const ROSTER: RosterResponse = {
  league_name: 'Test League',
  team_name: 'Test Team',
  players: [
    player({
      player_id: '1',
      starter_slot: 0,
      first_name: 'Lou',
      last_name: 'Locked',
      position: 'QB',
      locked: true,
      game_status: 'in_game',
      actual_points: 12.4,
    }),
    player({
      player_id: '2',
      starter_slot: 1,
      first_name: 'Pat',
      last_name: 'Pending',
      position: 'RB',
      projected_points: 18,
    }),
    player({
      player_id: '3',
      first_name: 'Ben',
      last_name: 'Bolted',
      locked: true,
      game_status: 'complete',
      actual_points: 8,
    }),
  ],
  season: '2026',
  week: 7,
  slots: ['QB', 'RB'],
  lineup: { starter_ids: ['1', '2'], bench_ids: ['3'], optimal_total: 30.4, current_total: 30.4 },
}

// The table row holding a player's name.
function rowOf(name: string): HTMLElement {
  const row = screen.getByText(name).closest('tr')
  if (row === null) throw new Error(`No table row for ${name}`)
  return row
}

describe('LineupView: locked players', () => {
  it("puts a padlock straight after a locked player's name", () => {
    render(<LineupView roster={ROSTER} />)

    const icon = within(rowOf('Lou Locked')).getByRole('img', { name: 'Locked' })
    // Next to the name, where the other tags and future status icons go
    expect(screen.getByText('Lou Locked').nextElementSibling).toBe(icon)
  })

  it('marks locked players on the bench too, and nobody else', () => {
    render(<LineupView roster={ROSTER} />)

    expect(screen.getAllByRole('img', { name: 'Locked' })).toHaveLength(2)
    expect(within(rowOf('Ben Bolted')).getByRole('img', { name: 'Locked' })).toBeTruthy()
    expect(within(rowOf('Pat Pending')).queryByRole('img', { name: 'Locked' })).toBeNull()
  })

  it('no longer shows a Locked tag', () => {
    render(<LineupView roster={ROSTER} />)

    expect(screen.queryByText('Locked')).toBeNull()
  })
})
