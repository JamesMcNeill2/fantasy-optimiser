// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { setUpBrowserTests } from './testHelpers'
import { trustedId, useSelection } from './urlState'

setUpBrowserTests()

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

describe('useSelection', () => {
  it('reads the league and team from the address bar', () => {
    window.history.replaceState(null, '', '/?league=1&team=4')
    const { result } = renderHook(() => useSelection())
    expect(result.current[0]).toEqual({ league: 1, team: 4 })
  })

  it('ignores a team without a league, and anything that is not a whole number', () => {
    window.history.replaceState(null, '', '/?team=4')
    expect(renderHook(() => useSelection()).result.current[0]).toEqual({ league: null, team: null })

    window.history.replaceState(null, '', '/?league=abc&team=4')
    expect(renderHook(() => useSelection()).result.current[0]).toEqual({ league: null, team: null })
  })

  it('adds a history entry for each choice, and Back restores the one before', async () => {
    const { result } = renderHook(() => useSelection())
    act(() => result.current[1]({ league: 0, team: null }))
    act(() => result.current[1]({ league: 0, team: 8 }))
    expect(window.location.search).toBe('?league=0&team=8')

    window.history.back()
    await waitFor(() => expect(result.current[0]).toEqual({ league: 0, team: null }))
    expect(window.location.search).toBe('?league=0')
  })

  it('adds no history entry when the choice is the page already shown', () => {
    window.history.replaceState(null, '', '/?league=0')
    const { result } = renderHook(() => useSelection())
    const pushState = vi.spyOn(window.history, 'pushState')

    act(() => result.current[1]({ league: 0, team: null }))
    expect(pushState).not.toHaveBeenCalled()
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0)
  })
})
