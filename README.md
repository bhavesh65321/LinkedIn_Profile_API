# LinkedIn Profile API

Browserless HTTPS API that accepts a LinkedIn profile URL and returns structured JSON  
(name, headline, location, about, experience, education, skills, certifications, languages, images, and extras).

Built by reverse-engineering LinkedIn’s internal **Voyager** REST/GraphQL endpoints — **no browser automation**.

---

## Features

- `POST /v1/profile` and `GET /v1/profile?url=...`
- Public endpoint (no API key)
- Session-cookie auth (`li_at` + `JSESSIONID`) kept in env vars only
- Multi-endpoint fetch strategy with graceful degradation when a decoration / queryId rotates
- OpenAPI docs at `/docs`
- Ready for **Render** (Docker)

---

## Approach

LinkedIn’s website talks to private Voyager APIs. With a logged-in session, the same calls work over plain HTTP:

1. Parse `/in/{publicIdentifier}` from the input URL  
2. Authenticate with cookies + CSRF (`csrf-token` = `JSESSIONID` value)  
3. Call Voyager (no Playwright/Puppeteer):
   - `GET /voyager/api/identity/profiles/{id}/profileView` — classic full profile payload  
   - `GET /voyager/api/identity/dash/profiles?q=memberIdentity&...` — modern dash decorations  
   - Section endpoints for skills / certifications / languages / network info  
   - Optional GraphQL `voyagerIdentityDashProfileCards.*` for about / card sections  
4. Normalize LinkedIn’s nested / `included[]` shapes into a stable response schema  

This mirrors what tools like [PhantomBuster’s Profile Scraper](https://phantombuster.com/automations/linkedin/5589386912058181/linkedin-profile-scraper) expose, but aims for fuller section coverage (full experience list, skills, images, etc.).

---

## Quick start (local)

### 1. Clone & install

```bash
git clone <your-repo-url>
cd LinkedIn_Profile_API
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
```

Fill in:

| Variable | Where to get it |
|---|---|
| `LI_AT` | Chrome → DevTools → Application → Cookies → `https://www.linkedin.com` → `li_at` |
| `JSESSIONID` | Same place → `JSESSIONID` (usually `ajax:…`; quotes optional) |

Never commit `.env`.

### 3. Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/health  
- Docs: http://localhost:8000/docs  

---

## API

### `GET /health`

Checks whether credentials are set and whether `GET /voyager/api/me` succeeds.

### `POST /v1/profile`

```bash
curl -s -X POST http://localhost:8000/v1/profile \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.linkedin.com/in/williamhgates/"}' | jq .
```

### `GET /v1/profile`

```bash
curl -s 'http://localhost:8000/v1/profile?url=https://www.linkedin.com/in/williamhgates/' | jq .
```

### Example response (truncated)

```json
{
  "url": "https://www.linkedin.com/in/williamhgates/",
  "public_identifier": "williamhgates",
  "profile_urn": "urn:li:fs_miniProfile:…",
  "first_name": "Bill",
  "last_name": "Gates",
  "full_name": "Bill Gates",
  "headline": "…",
  "location": "…",
  "about": "…",
  "profile_picture": "https://media.licdn.com/…",
  "background_image": "https://media.licdn.com/…",
  "follower_count": 0,
  "connection_count": null,
  "experience": [
    {
      "title": "…",
      "company": "…",
      "company_url": "https://www.linkedin.com/company/…",
      "location": "…",
      "description": "…",
      "start_date": { "year": 2020, "month": 1, "day": null },
      "end_date": null,
      "is_current": true
    }
  ],
  "education": [],
  "skills": [{ "name": "Leadership", "endorsements": 99 }],
  "certifications": [],
  "languages": [{ "name": "English", "proficiency": "Native Or Bilingual" }],
  "scraped_at": "2026-08-29T06:00:00+00:00"
}
```

### Error shape

```json
{
  "detail": {
    "error": "Invalid LinkedIn profile URL",
    "detail": null,
    "code": "invalid_url"
  }
}
```

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `invalid_url` | Bad / non-profile URL |
| 404 | `profile_not_found` | Profile missing or inaccessible |
| 429 | `linkedin_rate_limited` | LinkedIn throttled the session |
| 502 | `linkedin_auth_error` | Cookie expired / rejected |
| 503 | `credentials_missing` | `LI_AT` / `JSESSIONID` not set |

---

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

---

## Deploy on Render

1. Push this repo to GitHub (public).  
2. [Render](https://render.com) → **New** → **Web Service** → connect the repo.  
3. Runtime: **Docker** (uses `Dockerfile`), or Blueprint with `render.yaml`.  
4. Set env vars (Dashboard → Environment):
   - `LI_AT`
   - `JSESSIONID`  
5. Deploy. HTTPS URL is provided automatically.  

Health check path: `/health`.

After cookies expire, update env vars on Render and restart the service.

---

## Project layout

```
app/
  main.py                 # FastAPI entry
  config.py               # env settings
  schemas.py              # request/response models
  linkedin/
    client.py             # Voyager HTTP client
    parser.py             # URL → public identifier
    normalize.py          # raw Voyager → ProfileResponse
    exceptions.py
  routes/
    health.py
    profile.py
Dockerfile
render.yaml
.env.example
```

---

## Known limitations

- **Unofficial API** — Voyager `decorationId` / GraphQL `queryId` values can break when LinkedIn deploys. The client tries multiple known values and degrades gracefully.
- **Session cookies expire** — you must refresh `LI_AT` / `JSESSIONID` periodically.
- **Private / restricted profiles** — may return partial or empty sections.
- **Rate limits / bot detection** — aggressive traffic can yield `429` or auth challenges. This service does not use a browser to solve challenges.
- **ToS** — automating LinkedIn violates their Terms of Service; this project is for assessment / educational reverse-engineering only.
- **No email discovery** — unlike some commercial scrapers, we do not enrich professional emails.

---

## License

MIT (assessment / educational use). Use at your own risk regarding LinkedIn’s terms.
