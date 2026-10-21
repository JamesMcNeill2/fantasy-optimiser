// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ChoiceList, type Choice } from './ChoiceList'
import { setUpBrowserTests } from './testHelpers'

setUpBrowserTests()

const AVATAR = '/avatars/0a1b2c.jpg'

// One team's box. jsdom never loads images, so a test fires the image's error
// event itself when it needs a failed load.
function renderTeam(choice: Partial<Choice> = {}) {
  return render(<ChoiceList choices={[team(choice)]} {...listProps} />)
}

function team(choice: Partial<Choice>): Choice {
  return { value: 8, label: 'Hail Marys', image: AVATAR, ...choice }
}

const listProps = {
  size: 'regular' as const,
  linkTo: (value: number) => ({ league: 0, team: value }),
  onNavigate: () => {},
}

// The box's image, if it shows one. alt="" makes it decorative, so it has no
// role to find it by.
function avatarIn(container: HTMLElement): HTMLImageElement | null {
  return container.querySelector('img')
}

// What the browser does when an avatar can't be loaded.
function failToLoad(container: HTMLElement) {
  const avatar = avatarIn(container)
  if (avatar === null) throw new Error('No avatar to fail')
  fireEvent.error(avatar)
}

describe('ChoiceList: team avatars', () => {
  it("shows a team's avatar in place of its initials", () => {
    const { container } = renderTeam()

    expect(avatarIn(container)?.getAttribute('src')).toBe(AVATAR)
    expect(screen.queryByText('HM')).toBeNull()
  })

  it('keeps the avatar decorative, so the link is named by the team alone', () => {
    const { container } = renderTeam()

    expect(avatarIn(container)?.getAttribute('alt')).toBe('')
    expect(screen.getByRole('link', { name: 'Hail Marys' })).toBeTruthy()
  })

  it('shows the initials when a team has no avatar', () => {
    const { container } = renderTeam({ image: null })

    expect(avatarIn(container)).toBeNull()
    expect(screen.getByText('HM')).toBeTruthy()
  })

  it('falls back to the initials when the avatar fails to load', () => {
    const { container } = renderTeam()

    failToLoad(container)
    expect(avatarIn(container)).toBeNull()
    expect(screen.getByText('HM')).toBeTruthy()
  })

  it('tries a new avatar after an earlier one failed', () => {
    const { container, rerender } = renderTeam()
    failToLoad(container)

    const newAvatar = '/avatars/3d4e5f.jpg'
    rerender(<ChoiceList choices={[team({ image: newAvatar })]} {...listProps} />)
    expect(avatarIn(container)?.getAttribute('src')).toBe(newAvatar)
  })

  it('shows initials for choices with no image at all, like leagues', () => {
    render(
      <ChoiceList
        choices={[{ value: 0, label: 'Fourth Down Heroes' }]}
        {...listProps}
        size="large"
      />,
    )

    expect(screen.getByText('FDH')).toBeTruthy()
  })
})
