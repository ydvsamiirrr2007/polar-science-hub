# Polar Atlas — Polar Science Knowledge Hub

A responsive hackathon MVP for **Integrated Polar Science Outreach, Knowledge Repository and Media Dissemination Portal**.

The goal is to make polar-science resources easier to discover, understand and turn into outreach drafts.

## What is included

- **Overview dashboard:** resource, view and download counters; topic distribution; recent records.
- **Data Analytics workspace:** SQL-backed repository summaries, Chart.js visualisations by type/region/year/topic, metadata quality checks, most-engaged resource records.
- **CSV profiler:** upload a CSV (up to 10 MB / 100,000 rows), inspect column types, missing values, duplicates, descriptive statistics and an eight-row preview. The uploaded CSV is analysed in memory and is not retained.
- **Synthetic example CSV:** download `static/polar_research_sample.csv` to test the analysis workflow; it is clearly labelled as demo data, not real scientific observations.
- **Knowledge library:** search by text and filter by topic, region and resource type.
- **Resource management:** add a source URL, abstract/notes, tags and optionally attach a file (up to 30 MB).
- **Research assistant:** retrieves records from the local repository. With an optional OpenAI API key, it can compose an answer grounded in the selected record notes. Without a key, local retrieval works and does not pretend to be a generative model.
- **Media studio:** make starter drafts for social posts, classroom explainers, research briefs and newsletters. AI-assisted draft generation is optional.
- **SQLite database:** created automatically the first time you launch the app; no external database required.
- **Responsive layout:** desktop and mobile views.

## Tech stack

- Python + Flask (backend/API)
- SQLite (local database and SQL aggregations)
- Pandas (CSV profiling and descriptive statistics)
- Chart.js (interactive browser charts, loaded from a CDN)
- HTML, CSS and vanilla JavaScript (frontend)
- Optional OpenAI Responses API integration for grounded answer/draft generation

## Requirements

- Python 3.10 or later
- Internet access only if you want the optional AI API or to open external source links

## Run on Windows

1. Extract the ZIP file.
2. Open the extracted `polar-science-hub` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run the commands below with `python -m pip` directly or activate through Command Prompt using `.venv\Scripts\activate.bat`.

5. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open **http://127.0.0.1:5000** in a browser.

## Run on macOS / Linux

```bash
cd polar-science-hub
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**.

## Optional AI setup

The project is usable without an API key. To enable the generative answer and outreach features:

1. Copy `.env.example` to a new file named `.env` in this folder.
2. Add your own API key to `OPENAI_API_KEY`.
3. Set `OPENAI_MODEL` to a text model enabled for your API project.
4. Restart `python app.py`.

Example `.env` (do not share this file or commit it to GitHub):

```env
OPENAI_API_KEY=put_your_key_here
OPENAI_MODEL=gpt-4.1-mini
PORT=5000
```

Keep the key on the server. Do not add an API key to `static/app.js`, HTML, or any client-side file. API use may incur charges depending on your account.

## First-run data

The app seeds a small set of starting links on first launch. They include source gateways such as the National Snow and Ice Data Center, British Antarctic Survey, NASA Earth Observatory and Polar Data Catalogue. The records are demo metadata—not a full scientific dataset. Open the original source, check the publication date and citation instructions, and validate claims before using them in a submission.

Uploaded files are saved in `uploads/`. The database is `polar_hub.db`. Both are created locally. The `.gitignore` excludes both by default, so remove those ignore rules only if you intentionally want to version test data.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Check server status |
| GET | `/api/dashboard` | Dashboard metrics and recent resources |
| GET | `/api/resources` | List resources; supports `q`, `category`, `region`, `type` filters |
| POST | `/api/resources` | Add a resource (`multipart/form-data` for file uploads) |
| GET | `/api/resources/<id>` | Resource details and view tracking |
| GET | `/api/resources/<id>/download` | Download an attached file or open its source URL |
| POST | `/api/ask` | Search resources and return a grounded answer/local matching result |
| POST | `/api/generate` | Create an outreach content draft |

## Suggested presentation flow for a hackathon

1. Start on the overview and show the seed collection and topic distribution.
2. Search the library for `sea ice` and open the NSIDC resource.
3. Add a new research record with a source URL, notes and tags.
4. Ask the research assistant a question that matches a stored resource.
5. Generate a classroom explainer or social post in the media studio.
6. Explain the responsible-science safeguard: source links remain visible and draft output must be checked against the original source.

## Important limitations / before deployment

This is a local prototype, not a production multi-user service. It currently does not include login/roles, cloud storage, full-text parsing for uploaded PDFs, semantic vector search, admin approval workflows, or production security hardening. Flask debug mode is enabled for local development. Turn debug off and add authentication, CSRF protections, upload scanning, rate limiting, proper secret management and deployment configuration before public hosting.

## Deploy a public shareable link (Render)

This project includes `render.yaml` for deploying as a Render web service.

1. Create a new GitHub repository and upload the project files (the contents of this folder, not the ZIP file itself).
2. Do not upload `.env`, `.venv`, `polar_hub.db`, or real/private uploaded files.
3. Sign in at https://render.com and choose **New + → Blueprint**, then connect the GitHub repository containing `render.yaml`.
4. Review the detected `polar-science-hub` service and deploy it. Render should provide a public `https://...onrender.com` URL after deployment succeeds.
5. Open the public URL, then share it with your teammate.

**Demo limitations:** The free Render service uses an ephemeral filesystem. The SQLite database and uploaded files can be reset on restarts, spin-downs, or redeploys. Free instances can sleep after 15 minutes of inactivity and may take around a minute to wake. Do not use this configuration for important or private data. For persistent shared data, switch to a managed database and appropriate file storage before production use.

The deployment starts with Gunicorn and checks `/api/health`. The optional AI key can be added in the Render service's environment settings as `OPENAI_API_KEY`; do not commit API keys into GitHub.


## Data Analytics demo

1. Open the **Data analytics** page from the left navigation.
2. Review charts for the current library. They describe repository metadata (what is stored), not scientific evidence about polar environments.
3. Click **Download sample CSV** and upload the downloaded file under **Analyse your own CSV**.
4. Review the data profile, missing-value counts, duplicate rows, numeric summary statistics, categorical frequencies and preview. The uploaded CSV is processed in memory and not retained by the app.

The sample is synthetic and for testing only. Do not cite its figures as actual Arctic or Antarctic observations.
