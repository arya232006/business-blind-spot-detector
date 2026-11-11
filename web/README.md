# Blind Spot Detector — Next.js frontend

A Next.js 16 (App Router) + TypeScript + Tailwind + Recharts dashboard for the Business Blind Spot Detector.
It is a **client-side app**: every page fetches from the FastAPI backend **in the browser**, so it can be hosted anywhere
(Vercel, Netlify, any static host) while the backend runs wherever you like — by default on your own machine.

## Run locally

```bash
# 1. backend (project root)           -> http://localhost:8000
uvicorn backend.main:app --port 8000
# 2. frontend (this folder)           -> http://localhost:3000
cd web && npm install && npm run dev
```

The backend URL defaults to `http://localhost:8000` (`NEXT_PUBLIC_API_URL`). It can also be changed **at runtime** in the
sidebar under **⚙ Backend settings** (stored in the browser), so a deployed frontend can be pointed at any backend without a redeploy.

## Deploy on Vercel

1. Import the GitHub repo in Vercel and set **Root Directory = `web`** (framework is auto-detected).
2. Optionally set `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
3. **Allow the deployed origin on the backend** — the API has no authentication, so CORS is an explicit allow-list (no wildcards):

   ```bash
   CORS_ORIGINS="http://localhost:3000,https://YOUR-APP.vercel.app" uvicorn backend.main:app --port 8000
   ```

### Important: what "backend on my machine" means for a hosted site
A page hosted on Vercel calls the backend **from the visitor's browser**. So `http://localhost:8000` works only for the person
whose machine runs the backend (you, in your own browser). Other visitors would hit *their own* localhost and see "Backend unreachable".
To let others use it, host the backend publicly (Render, Railway, Fly.io, a VPS, or a Cloudflare/ngrok tunnel), add HTTPS, put
authentication in front of it, and set the URL in **Backend settings**. Browsers also restrict `https` pages calling `http://localhost`
(Chrome allows it with the Private Network Access preflight the backend already answers; Safari may block it — use Chrome/Edge/Firefox
or an https tunnel).

## Structure

```
app/            pages: / (overview) customers company blind-spots trends recommendations data methodology
components/     Shell (sidebar, filters, backend settings) · Gate · ui (primitives) · charts (Recharts)
lib/            api.ts (typed client) · store.tsx (state) · derive.ts (filters/stats) · types.ts · constants.ts
```
