import { useState } from 'react'

// For an img that should give way if it fails to load. Returns the path to
// show (null once that path has failed) and the handler for the img's
// onError. It remembers which path failed, not just that one did, so a new
// path still gets its own try.
export function useImageFallback(
  src: string | null,
): [showSrc: string | null, onError: () => void] {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  return [src === failedSrc ? null : src, () => setFailedSrc(src)]
}
