// The initials badge on each team's box.

// Up to `count` initials: the first letter or digit of each of the first
// `count` words, or the first `count` of a one-word name. Emoji and
// punctuation are skipped.
export function initials(name: string, count = 2): string {
  const words = name
    .split(/[\s_-]+/)
    .map((word) => word.match(/[\p{L}\p{N}]/gu) ?? [])
    .filter((chars) => chars.length > 0)
  if (words.length === 0) return '?'
  const letters =
    words.length === 1 ? words[0].slice(0, count) : words.slice(0, count).map((chars) => chars[0])
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

// Badge colours for a whole list of names, so boxes shown together don't
// share a colour. Each name starts from its own colour; if that's taken, it
// moves on to the next free one. Once all colours are used, they're reused.
export function badgeIndexes(names: string[]): number[] {
  const used = new Set<number>()
  return names.map((name) => {
    if (used.size === BADGE_COLOURS) used.clear()
    let index = badgeIndex(name)
    while (used.has(index)) index = (index + 1) % BADGE_COLOURS
    used.add(index)
    return index
  })
}
