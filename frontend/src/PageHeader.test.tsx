// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageHeader } from './PageHeader'
import { setUpBrowserTests } from './testHelpers'

setUpBrowserTests()

const AVATAR = '/avatars/0a1b2c.jpg'

// A lineup page's header. jsdom never loads images, so a test fires the
// image's error event itself when it needs a failed load.
const lineupHeader = {
  title: 'Hail Marys',
  subtitle: 'Week 7',
  back: { label: 'Fourth Down Heroes', to: { league: 0, team: null } },
  onNavigate: () => {},
}

// The header's image, if it shows one. alt="" makes it decorative, so it has
// no role to find it by.
function imageIn(container: HTMLElement): HTMLImageElement | null {
  return container.querySelector('img')
}

describe('PageHeader: image', () => {
  it('shows the image beside the heading, decorative', () => {
    const { container } = render(<PageHeader {...lineupHeader} image={AVATAR} />)

    expect(imageIn(container)?.getAttribute('src')).toBe(AVATAR)
    expect(imageIn(container)?.getAttribute('alt')).toBe('')
    expect(screen.getByRole('heading', { name: 'Hail Marys' })).toBeTruthy()
  })

  it('shows no image when there is none', () => {
    const { container } = render(<PageHeader {...lineupHeader} image={null} />)

    expect(imageIn(container)).toBeNull()
  })

  it('leaves the image out if it fails to load', () => {
    const { container } = render(<PageHeader {...lineupHeader} image={AVATAR} />)

    const image = imageIn(container)
    if (image === null) throw new Error('No image to fail')
    fireEvent.error(image)
    expect(imageIn(container)).toBeNull()
    expect(screen.getByRole('heading', { name: 'Hail Marys' })).toBeTruthy()
  })

  it('tries a new image after an earlier one failed', () => {
    const { container, rerender } = render(<PageHeader {...lineupHeader} image={AVATAR} />)
    const image = imageIn(container)
    if (image === null) throw new Error('No image to fail')
    fireEvent.error(image)

    const newAvatar = '/avatars/3d4e5f.jpeg'
    rerender(<PageHeader {...lineupHeader} image={newAvatar} />)
    expect(imageIn(container)?.getAttribute('src')).toBe(newAvatar)
  })
})
