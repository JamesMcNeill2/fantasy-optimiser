import { describe, expect, it } from 'vitest'
import league0 from './assets/league-0.jpg'
import { leagueAvatar } from './leagueAvatars'

describe('leagueAvatar', () => {
  it("returns league 0's built-in image", () => {
    expect(leagueAvatar(0)).toBe(league0)
  })

  it('returns null for a league without one', () => {
    expect(leagueAvatar(1)).toBeNull()
  })

  it('returns null for a key that is not a league', () => {
    expect(leagueAvatar(-1)).toBeNull()
    expect(leagueAvatar(99)).toBeNull()
  })
})
