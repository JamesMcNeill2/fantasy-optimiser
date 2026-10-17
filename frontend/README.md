# Frontend

React + TypeScript single-page app, built with Vite. It calls the api through
relative `/api/...` paths: CloudFront routes them when deployed, and Vite's
dev-server proxy does locally.

## Local development

Needs Node 24 (see `.nvmrc`) and the api running locally:

```powershell
# services/api
uv run --env-file ..\..\.env uvicorn app.main:app --reload

# frontend
npm install
npm run dev        # http://localhost:5173
```

To use a deployed api instead, set `API_PROXY_TARGET` (e.g.
`https://<distribution>.cloudfront.net`) before `npm run dev`.

## Checks

```powershell
npm run lint
npx vitest run
npm run build      # type-checks, then builds into dist/
npm run preview    # serves dist/ at http://localhost:4173, same proxy
```

## Layout

- `api.ts`: response types, paths, `getJson`, `ApiError`
- `useApi.ts`: loading / error / success hook
- `urlState.ts`: `?league=&team=` in the address bar
- `lineup.ts`: display rules (tested in `lineup.test.ts`)
- `errors.ts`: error messages and retry rules (tested in `errors.test.ts`)
- Components: `App`, `Picker`, `LineupView`, `RequestStatus`, `ErrorMessage`
