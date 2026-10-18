import './ChoiceList.css'
import { badgeIndexes, initials } from './teamBadge'

export interface Choice {
  value: number
  label: string
}

interface ChoiceListProps {
  choices: Choice[]
  onChoose: (value: number) => void
  // tiles: a few large boxes (leagues). list: many smaller ones with badges (teams).
  size: 'large' | 'regular'

}

// A heading and a grid of clickable boxes, one per choice.
export function ChoiceList({ choices, onChoose, size }: ChoiceListProps) {
  const colours = badgeIndexes(choices.map((choice) => choice.label))
  // League names suit three initials; team names, two
  const initialCount = size === 'large' ? 3 : 2
  return (
    <section>
      <ul className={`choices choices-${size}`}>
        {choices.map((choice, i) => (
          <li key={choice.value}>
            <button type="button" className="choice" onClick={() => onChoose(choice.value)}>
              <span className={`badge badge-${colours[i]}`} aria-hidden="true">
                {initials(choice.label, initialCount)}
              </span>
              <span className="choice-label">{choice.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
