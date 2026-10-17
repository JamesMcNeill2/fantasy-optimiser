import './ChoiceList.css'
import { badgeIndex, initials } from './teamBadge'

export interface Choice {
  value: number
  label: string
}

interface ChoiceListProps {
  title: string
  choices: Choice[]
  onChoose: (value: number) => void
  // tiles: a few large boxes (leagues). list: many smaller ones with badges (teams).
  layout: 'tiles' | 'list'

}

// A heading and a grid of clickable boxes, one per choice.
export function ChoiceList({ title, choices, onChoose, layout }: ChoiceListProps) {
  return (
    <section>
      <h2>{title}</h2>
      <ul className={`choices choices-${layout}`}>
        {choices.map((choice) => (
          <li key={choice.value}>
            <button type="button" className="choice" onClick={() => onChoose(choice.value)}>
              {layout === 'list' && (
                <span className={`badge badge-${badgeIndex(choice.label)}`} aria-hidden="true">
                  {initials(choice.label)}
                </span>
              )}
              <span className="choice-label">{choice.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
