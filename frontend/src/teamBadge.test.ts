import { describe, expect, it } from 'vitest'
import { BADGE_COLOURS, badgeIndex, initials } from './teamBadge'

describe('initials', () => {
  it('takes the first letter of the first two words', () => {
    expect(initials('Gridiron Gang')).toBe('GG')
  })

  it('takes two letters from a one-word name', () => {
    expect(initials('touchdown')).toBe('TO')
  })

  it('splits on underscores and hyphens', () => {
    expect(initials('the_dynasty-kings')).toBe('TD')
  })

  it('skips emoji and punctuation', () => {
    expect(initials('🏈 Gang')).toBe('GA')
  })

  it('falls back to a question mark', () => {
    expect(initials('🏈🏈')).toBe('?')
  })
})

describe('badgeIndex', () => {
  it('gives the same name the same colour every time', () => {
    expect(badgeIndex('Gridiron Gang')).toBe(badgeIndex('Gridiron Gang'))
  })

  it('stays within the badge colours', () => {
    for (const name of ['A', 'Gridiron Gang', 'the_dynasty-kings', '🏈 Gang', '']) {
      const index = badgeIndex(name)
      expect(index).toBeGreaterThanOrEqual(0)
      expect(index).toBeLessThan(BADGE_COLOURS)
    }
  })
})
