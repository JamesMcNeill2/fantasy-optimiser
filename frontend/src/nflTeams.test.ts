import { describe, expect, it } from 'vitest'
import { contrast, teamColours } from './nflTeams'

describe('teamColours', () => {
  it('puts white text on a dark team colour', () => {
    expect(teamColours('BUF')).toEqual({ background: '#00338d', text: '#ffffff' })
  })

  it('puts dark text on a light team colour', () => {
    expect(teamColours('PIT')).toEqual({ background: '#ffb612', text: '#10131f' })
  })

  it('returns null for an unknown team', () => {
    expect(teamColours('XYZ')).toBeNull()
  })
})

describe('contrast', () => {
  it('is 21 for black on white', () => {
    expect(contrast('#000000', '#ffffff')).toBeCloseTo(21)
  })

  it('is 1 for a colour against itself', () => {
    expect(contrast('#00338d', '#00338d')).toBe(1)
  })
})
