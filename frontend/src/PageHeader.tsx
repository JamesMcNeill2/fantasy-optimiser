import './PageHeader.css'

interface PageHeaderProps {
    title: string
    subtitle?: string
    // The page one level up: its name, and how to get there
    back?: { label: string; onClick: () => void }
}

// The top of every page: an optional back link, the heading and a line under it.
export function PageHeader({ title, subtitle, back }: PageHeaderProps) {
  return (
    <header className="page-head">
      {back !== undefined && (
        <button
          type="button"
          className="back"
          onClick={back.onClick}
          aria-label={`Back to ${back.label}`}
        >
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
            <path
              d="M10 3 5 8l5 5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {back.label}
        </button>
      )}
      <h2>{title}</h2>
      {subtitle !== undefined && <p className="subtitle">{subtitle}</p>}
    </header>
  )
}
