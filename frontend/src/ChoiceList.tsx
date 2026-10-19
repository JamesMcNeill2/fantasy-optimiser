import './ChoiceList.css'
import { badgeIndexes, initials } from './teamBadge'
import { SelectionLink } from './SelectionLink'
import type { Selection } from './urlState'

export interface Choice {
  value: number
  label: string
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
            <span className={`badge badge-${colours[i]}`} aria-hidden="true">
              {initials(choice.label, initialCount)}
            </span>
            <span className="choice-label">{choice.label}</span>
          </SelectionLink>
        </li>
      ))}
    </ul>
  )
}
