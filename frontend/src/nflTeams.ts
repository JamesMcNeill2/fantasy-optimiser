// NFL team colours, for the small team label under each player.

// Each team's primary colour, keyed by Sleeper's team code.
// prettier-ignore
const TEAM_COLOURS = new Map([
  ['ARI', '#97233f'], ['ATL', '#a71930'], ['BAL', '#241773'], ['BUF', '#00338d'],
  ['CAR', '#0085ca'], ['CHI', '#0b162a'], ['CIN', '#fb4f14'], ['CLE', '#311d00'],
  ['DAL', '#003594'], ['DEN', '#fb4f14'], ['DET', '#0076b6'], ['GB', '#203731'],
  ['HOU', '#03202f'], ['IND', '#002c5f'], ['JAX', '#006778'], ['KC', '#e31837'],
  ['LAC', '#0080c6'], ['LAR', '#003594'], ['LV', '#000000'], ['MIA', '#008e97'],
  ['MIN', '#4f2683'], ['NE', '#002244'], ['NO', '#d3bc8d'], ['NYG', '#0b2265'],
  ['NYJ', '#125740'], ['PHI', '#004c54'], ['PIT', '#ffb612'], ['SEA', '#002244'],
  ['SF', '#aa0000'], ['TB', '#d50a0a'], ['TEN', '#0c2340'], ['WAS', '#5a1414'],
])

const LIGHT_TEXT = '#ffffff'
const DARK_TEXT = '#10131f'

export interface TeamColours {
  background: string
  text: string
}

// A team's colour, with whichever of white or dark text reads better on it.
// Null for a code that isn't in the list.
export function teamColours(team: string): TeamColours | null {
  const background = TEAM_COLOURS.get(team)
  if (background === undefined) return null
  const text =
    contrast(background, LIGHT_TEXT) >= contrast(background, DARK_TEXT) ? LIGHT_TEXT : DARK_TEXT
  return { background, text }
}

// The WCAG contrast ratio between two #rrggbb colours: 1 (none) to 21 (black on white).
export function contrast(a: string, b: string): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}

// How bright a #rrggbb colour looks, from 0 (black) to 1 (white), per WCAG.
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}
