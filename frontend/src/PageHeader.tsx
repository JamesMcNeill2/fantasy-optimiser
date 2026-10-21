import type { Ref } from 'react'
import './PageHeader.css'
import { SelectionLink } from './SelectionLink'
import type { Selection } from './urlState'
import { useImageFallback } from './useImageFallback'

interface PageHeaderProps {
  title: string
  subtitle?: string
  // The page one level up: its name, and where it is
  back?: { label: string; to: Selection }
  onNavigate: (next: Selection) => void
  // Lets the app move focus here after a navigation
  headingRef?: Ref<HTMLHeadingElement>
  // A same-origin image to show beside the heading (a team's avatar), if any
  image?: string | null
}

// The top of every page: an optional back link, the heading and a line under
// it, with an optional image beside the heading. The image is decorative (the
// heading names the page), and is simply left out if it fails to load.
export function PageHeader({
  title,
  subtitle,
  back,
  onNavigate,
  headingRef,
  image = null,
}: PageHeaderProps) {
  const [shownImage, onImageError] = useImageFallback(image)

  return (
    <header className={shownImage === null ? 'page-head' : 'page-head with-image'}>
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
      {shownImage !== null && (
        <img className="page-image" src={shownImage} alt="" onError={onImageError} />
      )}
      <h2 ref={headingRef} tabIndex={-1}>
        {title}
      </h2>
      {subtitle !== undefined && <p className="subtitle">{subtitle}</p>}
    </header>
  )
}
