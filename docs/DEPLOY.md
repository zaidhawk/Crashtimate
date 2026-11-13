# Deploying Crashtimate

The API runs as a Docker container (Render here; Fly.io works the same way) and the web app
runs on Vercel. Neither has been deployed yet: these are the steps.

## 1. API on Render

1. In Render choose **New > Blueprint** and pick this repository. It reads `render.yaml`.
2. Fill in the two values it asks for:
   - `ANTHROPIC_API_KEY`: from https://platform.claude.com
   - `CRASHTIMATE_CORS_ORIGINS`: a JSON list with the web app's address, for example
     `["https://crashtimate.vercel.app"]`. You can set a placeholder now and correct it
     after step 2.
3. Wait for the deploy, then open `https://<your-service>.onrender.com/api/health`.
   It should answer `{"status":"ok","detector":"claude"}`.

The blueprint mounts a 1 GB disk at `/data` for the SQLite file, which needs a paid
instance. On the free plan remove the `disk` block: everything works, but cached analyses
and saved estimates are lost on each deploy.

## 2. Web app on Vercel

1. Import the repository in Vercel and set **Root Directory** to `frontend`.
2. Add the environment variable `NEXT_PUBLIC_API_URL` with the API's address from step 1
   (no trailing slash).
3. Deploy, then put the Vercel address into `CRASHTIMATE_CORS_ORIGINS` on Render.

## Settings that matter in production

| Setting | Why |
|---|---|
| `CRASHTIMATE_PROXY_HOPS=1` | Render and Fly.io put a proxy in front of the app. Without this every visitor shares one rate limit. |
| `CRASHTIMATE_DAILY_ANALYSIS_LIMIT` | Caps paid photo analyses per day, so a busy day can't run up a bill. |
| `CRASHTIMATE_RATE_LIMIT_PER_HOUR` | Photo analyses one visitor may request per hour. |
| `CRASHTIMATE_RETENTION_DAYS` | How long photos and saved estimates are kept. |

The app runs as one process, because rate-limit counts are held in memory and SQLite is a
single file. That is plenty for a demo. Growing past it would mean Redis for the counts and
Postgres for the data.

## Run it all locally with Docker

```bash
docker compose up --build
```

Then open http://localhost:3000. It starts in demo mode; see the comment at the top of
`docker-compose.yml` for real photo analysis.
