# FinAlly Frontend

Next.js trading terminal, built as a static export (`out/`) and served by FastAPI
on the same origin as `/api/*`.

```bash
npm install
npm run dev      # http://localhost:3000, needs the backend for /api/*
npm run build    # static export into out/
npm test         # Vitest + React Testing Library
npm run lint
```

`npm run dev` serves the UI but not the API. To see live data, run the backend on
port 8001 and open the built export through it, or point a proxy at it.

## Layout

- `src/app/` - the single page, which loads `Terminal` browser-only
- `src/components/` - terminal panes: watchlist, charts, positions, trade bar, chat
- `src/hooks/` - `usePriceStream` (SSE), `usePortfolio`, `useWatchlist`, `useChat`
- `src/lib/` - API client, contract types, formatting, portfolio math

The API contract is frozen in `planning/TEAM.md` section 4. Prices arrive over
SSE from `/api/stream/prices`; sparkline and chart history accumulate in the
browser since page load and are deliberately not persisted.
