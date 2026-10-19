import { describe, expect, it } from 'vitest'
import { BADGE_COLOURS, badgeIndex, initials, badgeIndexes } from './teamBadge'

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

  it('takes three initials when asked', () => {
    expect(initials('No Punt Intended', 3)).toBe('NPI')
    expect(initials('Any Given Sunday', 3)).toBe('AGS')
  })

  it('takes three letters from a one-word name when asked', () => {
    expect(initials('touchdown', 3)).toBe('TOU')
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

describe('badgeIndexes', () => {
  it('gives names that would share a colour different ones', () => {
    const [first, second] = badgeIndexes(['No Punt Intended', 'Any Given Sunday'])
    expect(first).not.toBe(second)
  })

  it('uses every colour once before reusing any', () => {
    const names = Array.from({ length: BADGE_COLOURS }, (_, i) => `Team ${i}`)
    expect(new Set(badgeIndexes(names)).size).toBe(BADGE_COLOURS)
  })

  it('gives the same list the same colours every time', () => {
    const names = ['Big boys', 'Bills Bills Bills', 'Christ no McCalfInjury']
    expect(badgeIndexes(names)).toEqual(badgeIndexes(names))
  })
})
