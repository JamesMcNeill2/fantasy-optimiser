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

// A locked starter, an unlocked starter, a locked bench player and a bench
// player on a bye. Already optimal, so no Start or Bench tags get in the way.
const ROSTER: RosterResponse = {
  league_name: 'Test League',
  team_name: 'Test Team',
  players: [
    player({
      player_id: '1',
      starter_slot: 0,
      first_name: 'Lou',
      last_name: 'Locked',
      shirt_number: 0,
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
    player({
      player_id: '4',
      first_name: 'Bo',
      last_name: 'Byeweek',
      position: 'TE',
      opponent: null,
      game_status: 'bye',
      projected_points: null,
    }),
  ],
  season: '2026',
  week: 7,
  slots: ['QB', 'RB'],
  lineup: {
    starter_ids: ['1', '2'],
    bench_ids: ['3', '4'],
    optimal_total: 30.4,
    current_total: 30.4,
  },
}

// The table row holding a player's name.
function rowOf(name: string): HTMLTableRowElement {
  const row = screen.getByText(name).closest<HTMLTableRowElement>('tr')
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

describe('LineupView: byes', () => {
  it('shows a bye as a violet label in the Fixture column', () => {
    render(<LineupView roster={ROSTER} />)

    const label = within(rowOf('Bo Byeweek')).getByText('BYE')
    // Slot, Player, Fixture, Points: the Fixture cell is the third
    expect(rowOf('Bo Byeweek').cells[2].contains(label)).toBe(true)
    expect(label.classList.contains('bye-label')).toBe(true)
    // Not a team-label: bye rows grey those out, and this one stays violet
    expect(label.classList.contains('team-label')).toBe(false)
  })
})

describe('LineupView: columns', () => {
  it('heads the opponent column Fixture in every table', () => {
    render(<LineupView roster={ROSTER} />)

    // Starters and Bench (no one is on injured reserve)
    expect(screen.getAllByRole('columnheader', { name: 'Fixture' })).toHaveLength(2)
    expect(screen.queryByRole('columnheader', { name: 'Game' })).toBeNull()
  })
})

// The details line under a player's name.
function detailsOf(name: string): HTMLElement {
  const details = rowOf(name).querySelector<HTMLElement>('.player-details')
  if (details === null) throw new Error(`No details line for ${name}`)
  return details
}

describe('LineupView: player details', () => {
  it('shows the shirt number, position and team with a dot between each', () => {
    render(<LineupView roster={ROSTER} />)

    // #0 is a real shirt number, not a missing one
    expect(detailsOf('Lou Locked').textContent).toBe('QB·KC·#0')
  })

  it('leaves out a missing shirt number along with its dot', () => {
    render(<LineupView roster={ROSTER} />)

    expect(detailsOf('Pat Pending').textContent).toBe('RB·KC')
  })

  it('hides the dots from screen readers', () => {
    render(<LineupView roster={ROSTER} />)

    const dots = [...detailsOf('Lou Locked').children].filter((child) => child.textContent === '·')
    expect(dots).toHaveLength(2)
    for (const dot of dots) expect(dot.getAttribute('aria-hidden')).toBe('true')
  })
})
