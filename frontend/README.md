# MarketPulse Dashboard

React + Vite + TypeScript dashboard for the MarketPulse FastAPI service.

## Install

From this directory:

```sh
npm install
```

## Configure

Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` to the FastAPI origin.
The local development default is `http://127.0.0.1:8000`. The API must be
running and configured with access to the curated BigQuery tables.

## Develop

```sh
npm run dev
```

Vite serves the dashboard at `http://localhost:5173`.

## Verify

```sh
npm test
npm run build
```

## Project structure

- `src/api.ts` — typed fetch client for the FastAPI endpoints
- `src/App.tsx` — dashboard data loading, filters, KPIs, and page layout
- `src/components/` — charts, tables, filters, KPI cards, and product details
- `src/format.ts` — shared date and numeric formatting
- `src/styles.css` — responsive dashboard styling
- `src/App.test.tsx` — render test with mocked API responses

The browser calls FastAPI only; it never accesses BigQuery directly.
