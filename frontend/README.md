# Frontend

The fantasy lineup optimiser's single-page app: React and TypeScript, built
with Vite. It has three views on one page (leagues, then a league's teams, then
a team's lineup), with the choice kept in the query string (`/?league=0&team=8`)
so a refresh or a shared link opens the same view.

The app calls the api through relative `/api/...` paths. When deployed,
CloudFront routes them to the api; locally, Vite's proxy does.

## Local development

Needs Node 24 (see `.nvmrc`; 24.15 or later for the jsdom tests) and the api
running locally:

```powershell
# terminal 1, from services/api
uv run --env-file ..\..\.env uvicorn app.main:app --reload

# terminal 2, from frontend
npm ci
npm run dev        # http://localhost:5173
```

To use a deployed environment instead, point the proxy at its CloudFront
domain (`terraform output -raw frontend_domain_name` from `infra/live`, with
that workspace selected):

```powershell
$env:API_PROXY_TARGET = "https://<frontend_domain_name>"; npm run dev    # deployed api and avatars
$env:SITE_PROXY_TARGET = "https://<frontend_domain_name>"; npm run dev   # local api, deployed avatars
Remove-Item Env:API_PROXY_TARGET, Env:SITE_PROXY_TARGET -ErrorAction Ignore   # back to local only
```

Set the variable in the terminal that runs npm, before starting it:
`vite.config.ts` reads it once at start-up, so restart the dev server after
changing it. A `$env:` variable lasts for the rest of that terminal session,
hence the `Remove-Item`. The same variables work for `npm run preview`.

Team avatars only exist in a deployed site bucket (the batch job copies them
there from Sleeper), so `/avatars/…` can only come from a deployed
environment: `SITE_PROXY_TARGET` sends just `/avatars/…` there and keeps
`/api` on the local api, while `API_PROXY_TARGET` sends both. Without either,
the dev server answers `/avatars/…` with `index.html`, so every team avatar
falls back to its initials badge. League avatars are built into the app, so
they always load.

The dev server runs the app in React's `StrictMode`, which runs effects twice,
so every request appears twice in the browser's Network tab. Use
`npm run build` then `npm run preview` to see real request behaviour.

## Checks

Run from `frontend`. CI runs the same ones on every pull request and before
every deploy, plus a check that the api types are up to date (see Api types).

```powershell
npm run check          # the next four in order; stops at the first failure
npm run format:check   # Prettier (npm run format fixes)
npm run lint           # ESLint
npx vitest run         # every test once (npm test watches)
npm run build          # type-checks src, tests included, then builds into dist/
npm run preview        # serves dist/ at http://localhost:4173, same proxy
```

## Api types

The response types are generated from the api's OpenAPI schema, not written
by hand. After changing a Pydantic response model in
`services/api/app/main.py`:

```powershell
npm run gen:api    # needs uv
npm run build      # lists every place the change affects
```

`gen:api` runs `services/api/export_openapi.py`, which writes `openapi.json`,
then openapi-typescript, which writes `src/api-schema.ts`. Commit both with the
model change: CI regenerates them and fails if they differ. Never edit either
by hand.

openapi-typescript 7 declares TypeScript 5 as a peer, so an `overrides` entry
in `package.json` points it at this project's TypeScript 6. Remove it once a
release accepts TypeScript 6 (`npm view openapi-typescript peerDependencies`).

## Formatting

Prettier, pinned to an exact version so local and CI output match: no
semicolons, single quotes, 100-character lines (`.prettierrc.json`).
`.prettierignore` skips the lock file and the two generated files. The NFL
colour table in `nflTeams.ts` keeps its grid with `// prettier-ignore`.

## Tests

Vitest, with test files next to the code they test.

- **Pure functions** run in Node: `lineup.test.ts` (display rules),
  `errors.test.ts`, `teamBadge.test.ts`, `nflTeams.test.ts` and
  `leagueAvatars.test.ts`.
- **Hooks and components** run in jsdom (a `// @vitest-environment jsdom`
  comment at the top of the file) with React Testing Library:
  `useApi.test.ts`, `urlState.test.ts`, one test file per component
  (`ChoiceList`, `PageHeader`, `LineupView`, `ErrorBoundary`) and
  `App.test.tsx` for the whole app.
- **`testHelpers.ts`** has the shared pieces: a fake `fetch` (`stubFetch`,
  `json`), `deferred` to control the order responses arrive in, `settle`, and
  `setUpBrowserTests` for clean-up between tests.

## How the page works

- **The URL decides the page.** `App` reads the league and team from the query
  string and starts every request they imply at once. An id is trusted until
  its list arrives (`trustedId`); a stale one drops the page back a level.
- **`RequestStatus` checks a page's requests in order**, parent lists first,
  so a stale link's 404 is never shown. Try Again re-runs every failed request.
- **Navigation is real links** (`SelectionLink`): a plain click is handled in
  the page with `pushState`, while Ctrl/Cmd-click and middle-click open a new
  tab. Back and Forward work through a `popstate` listener.
- **Accessibility:** focus moves to the new page's heading after each
  navigation (not on first load), each page sets `document.title`, loading
  lines are `role="status"`, and each table is named by its heading.
- **Avatars.** Team avatars arrive from the api as same-origin paths
  (`/avatars/<file>.jpg`), which CloudFront serves from the site bucket.
  League avatars are built in: `leagueAvatars.ts` maps a league key to an
  image in `src/assets/`. The key is the league's position in `LEAGUE_IDS`,
  so reordering that list moves the avatars with it. An image that fails to
  load gives way (`useImageFallback`): to the initials badge in a league or
  team box, or to no image in a page header. Images are decorative
  (`alt=""`), because the name is always beside them.
- **A rendering error shows a message, not a blank page.** `getJson` doesn't
  validate responses, so a shape the generated types didn't predict could
  throw while rendering. `ErrorBoundary` catches that; Back and Forward try
  the app again.

## Layout

All in `src/`:

| File                                    | What it does                                                                     |
| --------------------------------------- | -------------------------------------------------------------------------------- |
| `main.tsx`                              | Entry point: the font, global CSS, and `App` in `ErrorBoundary` and `StrictMode` |
| `appName.ts`                            | The app's name, for the site header, tab title and error page                    |
| `ErrorBoundary.tsx`                     | A message instead of a blank page if rendering throws                            |
| `App.tsx`                               | Picks the page from the URL, starts the requests, moves focus, sets the title    |
| `api.ts`                                | Response types (from `api-schema.ts`), paths, `getJson`, `ApiError`              |
| `api-schema.ts`                         | Generated by `gen:api`; never edit                                               |
| `useApi.ts`                             | Loading / error / success hook for one request                                   |
| `urlState.ts`                           | `useSelection`, `selectionUrl`, `trustedId`                                      |
| `errors.ts`                             | Error messages and retry rules                                                   |
| `lineup.ts`                             | Display rules for the lineup view                                                |
| `teamBadge.ts`                          | Initials and colours for the league and team badges                              |
| `leagueAvatars.ts`                      | Built-in league avatars, keyed by league key                                     |
| `useImageFallback.ts`                   | Lets an image give way if it fails to load                                       |
| `nflTeams.ts`                           | NFL team colours, with text chosen by WCAG contrast                              |
| `PageHeader.tsx`                        | Back link, heading, subtitle and optional image                                  |
| `ChoiceList.tsx`                        | The league and team boxes                                                        |
| `SelectionLink.tsx`                     | A real link to a league or team                                                  |
| `RequestStatus.tsx`, `ErrorMessage.tsx` | Loading and error lines, with Try Again                                          |
| `LineupView.tsx`                        | The summary card and the Starters / Bench / Injured Reserve tables               |
| `testHelpers.ts`                        | Shared test set-up (see Tests)                                                   |
| `*.css`                                 | `index.css` (colour tokens, reset, page column) and one file per component       |
| `assets/`                               | `league-0.jpg`, the built-in league avatar, named by league key                  |

## Deployment

CI checks and builds the app in its own job (in the shared `checks.yml`
workflow), with no AWS access, and passes `dist/` to the deploy job as an
artifact. After `terraform apply`, the deploy job syncs it to the site bucket:
`assets/` with `max-age=31536000, immutable`, everything else with
`no-cache`. Then it invalidates `/*` on the CloudFront distribution. Neither
sync touches `avatars/` (the first only covers `assets/`, the second excludes
`avatars/`), so `--delete` never removes the team avatars the batch job copied
in. Terraform owns the bucket, CI owns the app's files in it, and the batch job
owns `avatars/`.
