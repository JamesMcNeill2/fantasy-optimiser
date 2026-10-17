import './Picker.css'

export interface PickerOption {
  value: number
  label: string
}

interface PickerProps {
  label: string
  placeholder: string
  options: PickerOption[]
  value: number | null
  onChange: (value: number | null) => void
}

// A labelled dropdown. The placeholder option stands for "nothing picked" (null).
export function Picker({ label, placeholder, options, value, onChange }: PickerProps) {
  return (
    <label className="picker">
      <span>{label}</span>
      <select
        value={value ?? ''}
        onChange={(event) =>{
          const picked = event.target.value
          onChange(picked === '' ? null : Number(picked))
        }}
      >
        <option value="">{placeholder}</option>
        {options.map((option)=> (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}
