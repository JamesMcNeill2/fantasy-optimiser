// The initials badge on each team's box.

// Up to two initials: the first letter or digit of the first two words, or
// the first two of a one-word name. Emoji and punctuation are skipped.
export function initials(name: string): string {
  const words = name
    .split(/[\s_-]+/)
    .map((word) => word.match(/[\p{L}\p{N}]/gu) ?? [])
    .filter((chars) => chars.length > 0)
  if (words.length === 0) return '?'
  const letters = words.length === 1 ? words[0].slice(0, 2) : [words[0][0], words[1][0]]
  return letters.join('').toLocaleUpperCase()
}

export const BADGE_COLOURS = 8

// Which of the badge colours a name gets. The same name always gets the same
// colour, so a team looks the same on every visit.
export function badgeIndex(name: string): number {
  let hash = 0
  for (const char of name) {
    hash = (hash * 31 + (char.codePointAt(0) ?? 0)) % 1_000_003
  }
  return hash % BADGE_COLOURS
}
