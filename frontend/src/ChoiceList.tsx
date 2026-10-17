import './ChoiceList.css'

export interface Choice {
  value: number
  label: string
}

interface ChoiceListProps {
  title: string
  choices: Choice[]
  onChoose: (value: number) => void
}

// A heading and a grid of clickable boxes, one per choice.
export function ChoiceList({ title, choices, onChoose }: ChoiceListProps) {
  return (
    <section>
      <h2>{title}</h2>
      <ul className="choices">
        {choices.map((choice) => (
          <li key={choice.value}>
            <button type="button" className="choice" onClick={() => onChoose(choice.value)}>
              {choice.label}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
