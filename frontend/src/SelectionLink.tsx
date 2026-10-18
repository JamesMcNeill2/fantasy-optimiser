import type { ComponentProps } from 'react'
import { selectionUrl, type Selection } from './urlState'

interface SelectionLinkProps extends Omit<ComponentProps<'a'>, 'href' | 'onClick'> {
  to: Selection
  onNavigate: (next: Selection) => void
}

// A real link to a selection. A plain click is handled in the page;
// modified clicks (new tab, new window) are left to the browser.
export function SelectionLink({ to, onNavigate, ...rest }: SelectionLinkProps) {
  return (
    <a
      {...rest}
      href={selectionUrl(to)}
      onClick={(event) => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey){
          return
        }
        event.preventDefault()
        onNavigate(to)
      }}
    />
  )
}
