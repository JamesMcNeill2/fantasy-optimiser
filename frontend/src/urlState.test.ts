import { describe, expect, it } from 'vitest'
import { trustedId } from './urlState'

const leagues = [{ key: 0 }, { key: 1 }]
const keyOf = (item: { key: number }) => item.key

describe('trustedId', () => {
  it('trusts the id while the list is loading', () => {
    expect(trustedId(9, undefined, keyOf)).toBe(9)
  })

  it('keeps an id that is in the list', () => {
    expect(trustedId(1, leagues, keyOf)).toBe(1)
  })

  it('drops an id the list proves stale', () => {
    expect(trustedId(9, leagues, keyOf)).toBeNull()
  })

  it('gives null when there is no id', () => {
    expect(trustedId(null, leagues, keyOf)).toBeNull()
    expect(trustedId(null, undefined, keyOf)).toBeNull()
  })
})
