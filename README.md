# LinkedIn Profile API 🔗

A **public HTTPS API** that fetches LinkedIn profile data and returns it as clean JSON. No browser automation needed — just send a profile URL and get back name, headline, experience, education, skills, images, and more.

**Live API:** https://linkedin-profile-api-bj27.onrender.com  
**GitHub:** https://github.com/bhavesh65321/LinkedIn_Profile_API

---

## What This Does

### Input
```
LinkedIn Profile URL
↓
https://www.linkedin.com/in/bhavesh-sonii/
```

### Output
```json
{
  "first_name": "Bhavesh",
  "last_name": "Soni",
  "headline": "Software Engineer @ Coupa Software",
  "location": "San Francisco Bay Area",
  "about": "...",
  "experience": [
    {
      "title": "Software Engineer",
      "company": "Coupa Software",
      "start_date": {"year": 2022, "month": 1},
      "is_current": true
    }
  ],
  "education": [...],
  "skills": [{"name": "Python", "endorsements": 50}],
  "profile_picture": "https://media.licdn.com/...",
  "scraped_at": "2026-08-29T13:00:00+00:00"
}
```

---

## Quick Start (3 Steps)

### Step 1: Get LinkedIn Cookies (One-time)

1. Open Chrome
2. Go to **https://www.linkedin.com** (log in if needed)
3. Press **F12** (DevTools)
4. Go to **Application** tab → **Cookies** → **https://www.linkedin.com**
5. Find and copy:
   - `li_at` (long string, ~400 chars)
   - `JSESSIONID` (looks like `ajax:0358883394570286411`)

### Step 2: Set Up Locally

```bash
# Clone repo
git clone https://github.com/bhavesh65321/LinkedIn_Profile_API.git
cd LinkedIn_Profile_API

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

### Step 3: Add Cookies to .env

Edit `.env` and paste your cookies:

```
LI_AT=<paste_your_li_at_here>
JSESSIONID=ajax:0358883394570286411
```

### Step 4: Run Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Visit:
- **API Docs:** http://127.0.0.1:8000/docs (interactive testing)
- **Health Check:** http://127.0.0.1:8000/health

---

## How to Use the API

### Option 1: Interactive Docs (Easiest) 🎯

1. Open http://127.0.0.1:8000/docs
2. Click **POST /v1/profile** → **"Try it out"**
3. Paste in request body:
```json
{
  "url": "https://www.linkedin.com/in/bhavesh-sonii/"
}
```
4. Click **"Execute"**
5. See full profile data below

### Option 2: Terminal (curl)

**POST request:**
```bash
curl -X POST http://127.0.0.1:8000/v1/profile \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.linkedin.com/in/bhavesh-sonii/"}'
```

**GET request:**
```bash
curl 'http://127.0.0.1:8000/v1/profile?url=https://www.linkedin.com/in/bhavesh-sonii/'
```

### Option 3: Python Script

```python
import asyncio
import json
from app.config import get_settings
from app.linkedin.client import LinkedInClient
from app.linkedin.normalize import normalize_profile

async def fetch_profile(url: str):
    get_settings.cache_clear()
    settings = get_settings()
    
    async with LinkedInClient(settings) as client:
        slug = url.split("/in/")[1].rstrip("/")
        bundle = await client.fetch_profile_bundle(slug)
        profile = normalize_profile(bundle, url)
        print(json.dumps(profile.model_dump(mode="json"), indent=2, default=str))

asyncio.run(fetch_profile("https://www.linkedin.com/in/bhavesh-sonii/"))
```

---

## API Endpoints

### GET /health
**Check if API is working and session is valid**

```bash
curl http://127.0.0.1:8000/health
```

Response:
```json
{
  "status": "ok",
  "linkedin_credentials_configured": true,
  "linkedin_session_ok": true,
  "detail": "Voyager /me succeeded",
  "extras": {
    "public_identifier": "bhavesh-sonii",
    "first_name": "Bhavesh"
  }
}
```

### POST /v1/profile
**Fetch profile from LinkedIn URL (JSON body)**

Request:
```json
{
  "url": "https://www.linkedin.com/in/bhavesh-sonii/"
}
```

Response: Full profile JSON (see example below)

### GET /v1/profile
**Fetch profile from LinkedIn URL (query parameter)**

```
GET /v1/profile?url=https://www.linkedin.com/in/bhavesh-sonii/
```

Response: Same as POST

---

## Response Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `url` | string | `https://www.linkedin.com/in/bhavesh-sonii/` | Original input URL |
| `public_identifier` | string | `bhavesh-sonii` | Extracted from URL |
| `first_name` | string | `Bhavesh` | May be null if private |
| `last_name` | string | `Soni` | May be null if private |
| `full_name` | string | `Bhavesh Soni` | Combination of first + last |
| `headline` | string | `Software Engineer @ Coupa` | Job title / role |
| `location` | string | `San Francisco Bay Area` | May be null |
| `about` | string | `...` | Bio / summary (may be null) |
| `experience` | array | `[{title, company, dates}]` | Full work history |
| `education` | array | `[{school, degree, field}]` | Full education history |
| `skills` | array | `[{name, endorsements}]` | Skills with endorsement counts |
| `certifications` | array | `[{name, authority, dates}]` | Certifications |
| `languages` | array | `[{name, proficiency}]` | Languages spoken |
| `profile_picture` | string | `https://media.licdn.com/...` | Profile photo URL |
| `background_image` | string | `https://media.licdn.com/...` | Background image URL |
| `follower_count` | number | `1234` | Number of followers (may be null) |
| `connection_count` | number | `500` | Number of connections (may be null) |
| `scraped_at` | string | `2026-08-29T13:00:00+00:00` | When data was fetched |

---

## Error Handling

### Bad URL
```bash
curl -X POST http://127.0.0.1:8000/v1/profile \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://google.com"}'
```

Response (HTTP 400):
```json
{
  "detail": {
    "error": "URL must be a linkedin.com profile link",
    "code": "invalid_url"
  }
}
```

### Profile Not Found
```bash
curl -X POST http://127.0.0.1:8000/v1/profile \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.linkedin.com/in/fake-user-xyz/"}'
```

Response (HTTP 404):
```json
{
  "detail": {
    "error": "LinkedIn profile not found for 'fake-user-xyz'",
    "code": "profile_not_found"
  }
}
```

### Session Expired
Response (HTTP 502):
```json
{
  "detail": {
    "error": "LinkedIn rejected the session (HTTP 401). Refresh LI_AT / JSESSIONID in .env.",
    "code": "linkedin_auth_error"
  }
}
```

| HTTP Code | Meaning | Fix |
|---|---|---|
| 400 | Bad URL format | Use valid LinkedIn profile URL |
| 404 | Profile not found | Profile doesn't exist or is private |
| 429 | Rate limited | Wait 1 hour before retrying |
| 502 | Session expired | Refresh cookies in .env |
| 503 | Credentials missing | Set LI_AT + JSESSIONID in .env |

---

## How It Works (Technical)

### Architecture

```
User Request (LinkedIn URL)
    ↓
1. URL Validation (is it LinkedIn?)
    ↓
2. Extract public identifier (e.g., "bhavesh-sonii")
    ↓
3. Authenticate with cookies (LI_AT + JSESSIONID)
    ↓
4. Call LinkedIn Voyager API (multiple endpoints)
    ├─ /voyager/api/identity/profiles/{id}/profileView
    ├─ /voyager/api/identity/dash/profiles
    ├─ /voyager/api/identity/profiles/{id}/skills
    ├─ /voyager/api/identity/profiles/{id}/certifications
    └─ /voyager/api/graphql (for about section)
    ↓
5. Normalize raw LinkedIn JSON
    ↓
6. Return clean structured JSON
```

### Why No Browser?

- **Faster:** Direct HTTP calls vs. browser automation
- **Cheaper:** No Selenium/Puppeteer overhead
- **Simpler:** Just cookies + HTTP headers
- **Reliable:** No browser crashes or timeouts

### Reverse Engineering

This API reverse-engineers LinkedIn's internal **Voyager** API that the website uses. We:
1. Captured real browser requests to LinkedIn
2. Extracted the API endpoints and headers
3. Replicated them with plain HTTP calls
4. Normalized the response format

---

## Deployment to Render (Production)

### Step 1: Push to GitHub

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### Step 2: Deploy on Render

1. Go to **https://render.com**
2. Click **"New +"** → **"Web Service"**
3. Connect GitHub → select this repo
4. Configure:
   - **Name:** `linkedin-profile-api`
   - **Environment:** Docker
   - **Plan:** Free
5. Click **"Create Web Service"**

### Step 3: Set Environment Variables

1. Go to **Environment** tab
2. Add:
   - `LI_AT` = your cookie
   - `JSESSIONID` = your cookie
3. Click **"Save"**
4. Service auto-restarts

### Step 4: Get Public URL

After 2-3 minutes, you'll get a URL like:
```
https://linkedin-profile-api-xxxx.onrender.com
```

Test it:
```bash
curl https://linkedin-profile-api-xxxx.onrender.com/health
```

---

## Testing

### Run Unit Tests (No LinkedIn Needed)

```bash
pip install -r requirements-dev.txt
pytest -v
```

All 35 tests pass ✓

### Test Locally

```bash
# Check health
curl http://127.0.0.1:8000/health | jq .

# Fetch a profile
curl -X POST http://127.0.0.1:8000/v1/profile \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.linkedin.com/in/bhavesh-sonii/"}' | jq .

# Test error handling
curl -X POST http://127.0.0.1:8000/v1/profile \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://google.com"}' | jq .
```

---

## Project Structure

```
LinkedIn_Profile_API/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment settings
│   ├── schemas.py              # Request/response models
│   ├── linkedin/
│   │   ├── client.py           # Voyager HTTP client
│   │   ├── parser.py           # URL parsing & validation
│   │   ├── normalize.py        # Data normalization
│   │   ├── exceptions.py       # Custom errors
│   │   └── __init__.py
│   └── routes/
│       ├── health.py           # Health check endpoint
│       ├── profile.py          # Profile fetch endpoint
│       └── __init__.py
├── tests/
│   ├── test_api.py             # 35 unit tests
│   └── test_parser.py          # URL parser tests
├── Dockerfile                  # Docker config
├── render.yaml                 # Render deployment config
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Dev dependencies (pytest)
├── .env.example                # Example env file
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
└── LICENSE                     # MIT license
```

---

## Troubleshooting

### `/health` shows `session_ok: false`

**Problem:** Cookies are expired or invalid

**Solution:**
1. Get fresh cookies from LinkedIn (see Quick Start Step 1)
2. Update `.env` with new values
3. Restart server: `Ctrl+C` then run `uvicorn` again

### `HTTP 401` or `HTTP 403` on profile fetch

**Problem:** Session rejected by LinkedIn

**Solution:** Same as above — refresh cookies

### `HTTP 404` on valid profile

**Problem:** Profile is private or doesn't exist

**Solution:** Try a different public profile

### Slow responses

**Problem:** First request takes 5-10 seconds

**Solution:** Normal — Render cold start. Subsequent requests are faster (~2s)

---

## Known Limitations

- **Unofficial API** — LinkedIn may change endpoints anytime
- **Cookies expire** — Refresh every 24 hours
- **Private profiles** — Return partial or empty data
- **Rate limiting** — Too many requests → HTTP 429
- **ToS violation** — This is for assessment/education only
- **No email discovery** — We don't enrich professional emails

---

## Requirements Met ✅

- ✅ Deploy API publicly over HTTPS
- ✅ Accept LinkedIn profile URL as input
- ✅ Return structured JSON (name, headline, location, about, experience, education, skills, certifications, languages, images)
- ✅ Use own LinkedIn credentials in backend
- ✅ Public GitHub repository with complete source code
- ✅ README with setup, API docs, approach, and limitations
- ✅ Keep credentials and secrets out of repository

---

## License

MIT License — for assessment and educational use only.

---

## Support

**Questions?** Check:
- Interactive docs: http://localhost:8000/docs
- GitHub issues: https://github.com/bhavesh65321/LinkedIn_Profile_API/issues
- This README

**Found a bug?** Open an issue on GitHub.
