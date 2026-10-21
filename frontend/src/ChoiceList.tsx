import './ChoiceList.css'
import { badgeIndexes, initials } from './teamBadge'
import { SelectionLink } from './SelectionLink'
import type { Selection } from './urlState'
import { useImageFallback } from './useImageFallback'

export interface Choice {
  value: number
  label: string
  // A same-origin image path for the badge (a team's avatar), if it has one
  image?: string | null
}

interface ChoiceListProps {
  choices: Choice[]
  // large: a few big boxes (leagues). regular: many smaller ones (teams)
  size: 'large' | 'regular'
  // Where each box links to, and how to go there
  linkTo: (value: number) => Selection
  onNavigate: (next: Selection) => void
}

// A grid of boxes, one per choice, each linking to it.
export function ChoiceList({ choices, size, linkTo, onNavigate }: ChoiceListProps) {
  const colours = badgeIndexes(choices.map((choice) => choice.label))
  // League names suit three initials; team names, two
  const initialCount = size === 'large' ? 3 : 2
  return (
    <ul role="list" className={`choices choices-${size}`}>
      {choices.map((choice, i) => (
        <li key={choice.value}>
          <SelectionLink className="choice" to={linkTo(choice.value)} onNavigate={onNavigate}>
            <Badge
              image={choice.image ?? null}
              initials={initials(choice.label, initialCount)}
              colour={colours[i]}
            />
            <span className="choice-label">{choice.label}</span>
          </SelectionLink>
        </li>
      ))}
    </ul>
  )
}

interface BadgeProps {
  image: string | null
  initials: string
  colour: number
}

// The image when there is one, or the coloured initials, which also replace
// an image that fails to load. Decorative either way: the name beside it is
// the link's text.
function Badge({ image, initials, colour }: BadgeProps) {
  const [shownImage, onImageError] = useImageFallback(image)

  if (shownImage !== null) {
    return <img className="badge badge-image" src={shownImage} alt="" onError={onImageError} />
  }
  return (
    <span className={`badge badge-${colour}`} aria-hidden="true">
      {initials}
    </span>
  )
}
