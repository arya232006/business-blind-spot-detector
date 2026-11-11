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

### Sharing your machine's backend with everyone (the intended setup)
A page hosted on Vercel calls the backend **from each visitor's browser**, so `http://localhost:8000` only works for you. To let
anyone use the site while your machine is on, give the backend a public URL with a tunnel:

```bash
brew install cloudflared            # once (free, no account)
scripts/share.sh                    # starts the backend + a public https://<random>.trycloudflare.com tunnel
```

The tunnel address changes every time you restart it, so the hosted site finds it through a tiny public **registry** file
(`{"url": "https://…"}`) that `share.sh` rewrites on every start (and blanks on Ctrl+C, so visitors see "backend offline"):

1. Create the registry once (a public GitHub Gist with a file named `backend.json`):
   `echo '{"url": ""}' > backend.json && gh gist create backend.json --public`
2. Set `NEXT_PUBLIC_REGISTRY_URL` on Vercel to the gist's **raw** URL: `https://gist.githubusercontent.com/<user>/<gist-id>/raw/backend.json`
3. Run the share script with the gist id: `BBSD_GIST_ID=<gist-id> scripts/share.sh`

(Alternative without a registry: a stable tunnel hostname — ngrok free static domain or a Cloudflare named tunnel on your own domain —
then just set `NEXT_PUBLIC_API_URL` on Vercel.)

**Security:** the API has no login. While shared, anyone with the URL can upload and analyse data and read what is stored in the local
database, and can use CPU on your machine. `share.sh` therefore starts the backend with `PUBLIC_MODE=true` (deleting companies and
changing the default scoring config are disabled) — but share only demo data, or point `DATABASE_URL` at a throw-away database.
Backend lookups order on a hosted site: URL typed in *Backend settings* → registry → `NEXT_PUBLIC_API_URL` → `http://localhost:8000`.
On `localhost` the registry is ignored, so local development always talks to your local backend.

## Structure

```
app/            pages: / (overview) customers company blind-spots trends recommendations data methodology
components/     Shell (sidebar, filters, backend settings) · Gate · ui (primitives) · charts (Recharts)
lib/            api.ts (typed client) · store.tsx (state) · derive.ts (filters/stats) · types.ts · constants.ts
```
