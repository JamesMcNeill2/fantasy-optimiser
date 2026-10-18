import './PageHeader.css'
import { SelectionLink } from './SelectionLink'
import type { Selection } from './urlState'
import type { Ref } from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  // The page one level up: its name, and where it is
  back?: { label: string; to: Selection }
  onNavigate: (next: Selection) => void
  // Lets the app move focus here after a navigation
  headingRef?: Ref<HTMLHeadingElement>
}

// The top of every page: an optional back link, the heading and a line under it.
export function PageHeader({ title, subtitle, back, onNavigate, headingRef }: PageHeaderProps) {
  return (
    <header className="page-head">
      {back !== undefined && (
        <SelectionLink
          className="back"
          to={back.to}
          onNavigate={onNavigate}
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
        </SelectionLink>
      )}
      <h2 ref={headingRef} tabIndex={-1}>
        {title}
      </h2>
      {subtitle !== undefined && <p className="subtitle">{subtitle}</p>}
    </header>
  )
}
