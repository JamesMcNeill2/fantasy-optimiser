// League avatars, built into the site. Keyed by league key, the league's
// position in LEAGUE_IDS: reordering that secret moves the avatars with it.
import league0 from './assets/league-0.jpg'

const LEAGUE_AVATARS: ReadonlyMap<number, string> = new Map([[0, league0]])

// A same-origin image path for a league's avatar, or null if it has none.
export function leagueAvatar(key: number): string | null {
  return LEAGUE_AVATARS.get(key) ?? null
}
