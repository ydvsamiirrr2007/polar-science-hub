"""Polar Science Knowledge Hub — Flask MVP.

Run locally with: python app.py
The database and upload directory are created automatically.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import io
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_from_directory, abort, redirect
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATABASE = BASE_DIR / "polar_hub.db"
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "webp", "gif", "mp4", "mov", "csv", "xlsx", "docx", "txt"
}
RESOURCE_TYPES = {"Research Paper", "Report", "Dataset", "Article", "Image", "Video", "Other"}
REGIONS = {"Arctic", "Antarctic", "Both Poles", "Southern Ocean", "Global", "Other"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30 MB per request
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def log_activity(conn: sqlite3.Connection, action: str, resource_id: int | None, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO activity (action, resource_id, detail, created_at) VALUES (?, ?, ?, ?)",
        (action, resource_id, detail[:250], now_iso()),
    )


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'Article',
                category TEXT NOT NULL DEFAULT 'General',
                region TEXT NOT NULL DEFAULT 'Global',
                year INTEGER,
                author TEXT DEFAULT '',
                url TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                content TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                file_name TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                downloads INTEGER NOT NULL DEFAULT 0,
                featured INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                resource_id INTEGER,
                detail TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(resource_id) REFERENCES resources(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_resources_category ON resources(category);
            CREATE INDEX IF NOT EXISTS idx_resources_region ON resources(region);
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        if count == 0:
            samples = [
                {
                    "title": "Sea Ice Today: Analysis Archive",
                    "type": "Report", "category": "Cryosphere", "region": "Both Poles", "year": 2026,
                    "author": "National Snow and Ice Data Center (NSIDC)",
                    "url": "https://nsidc.org/sea-ice-today/analyses",
                    "summary": "Monthly scientific analysis and visual resources describing Arctic and Antarctic sea-ice conditions.",
                    "content": "NSIDC's Sea Ice Today publishes sea-ice analysis and daily images. Its reports connect observed sea-ice conditions with climate and ocean context. Check the original source for the latest observations and methods.",
                    "tags": "sea ice, cryosphere, climate, satellite, Arctic, Antarctic", "featured": 1,
                },
                {
                    "title": "Arctic Sea Ice Minimum: 2026 Overview",
                    "type": "Article", "category": "Climate Change", "region": "Arctic", "year": 2026,
                    "author": "NSIDC News & Analysis",
                    "url": "https://nsidc.org/news-analyses/news-stories/arctic-sea-ice-has-reached-minimum-extent-2026-antarctic-sea-ice-maximum-most-likely-reached-well",
                    "summary": "An NSIDC news story reporting the provisional 2026 Arctic sea-ice minimum and placing it in the satellite record.",
                    "content": "The linked NSIDC report states that Arctic sea ice likely reached its 2026 minimum on September 12 at 4.60 million square kilometers, tied for tenth lowest with 2008, 2010 and 2025 in the satellite record. Treat the figures as reported by the source and revisit the original article for updates.",
                    "tags": "Arctic, sea ice, minimum extent, satellite record, climate", "featured": 1,
                },
                {
                    "title": "National Snow and Ice Data Center Data Portal",
                    "type": "Dataset", "category": "Data & Tools", "region": "Both Poles", "year": 2026,
                    "author": "NSIDC",
                    "url": "https://nsidc.org/data",
                    "summary": "A starting point for finding cryosphere datasets, documentation and related data products.",
                    "content": "Use the data portal to locate datasets and read their documentation, coverage, units, methods and access conditions before analysis. This hub stores a link to the portal; it does not copy or independently validate the underlying datasets.",
                    "tags": "dataset, data, sea ice, glaciers, snow, documentation", "featured": 0,
                },
                {
                    "title": "British Antarctic Survey: Polar Research",
                    "type": "Article", "category": "Expeditions", "region": "Antarctic", "year": 2026,
                    "author": "British Antarctic Survey",
                    "url": "https://www.bas.ac.uk/",
                    "summary": "Research, news and public information from a UK organisation working in polar environments.",
                    "content": "The British Antarctic Survey website is a gateway to polar science, fieldwork, research programmes and public-facing stories. Follow the source links for details about each programme or publication.",
                    "tags": "Antarctica, expedition, fieldwork, research, outreach", "featured": 0,
                },
                {
                    "title": "NASA Earth Observatory",
                    "type": "Image", "category": "Satellite Imagery", "region": "Global", "year": 2026,
                    "author": "NASA Earth Observatory",
                    "url": "https://earthobservatory.nasa.gov/",
                    "summary": "Earth-observation stories and imagery useful for communicating environmental changes from space.",
                    "content": "NASA Earth Observatory publishes image-led stories about Earth systems. For any visual used in public outreach, check the original page for caption, date, attribution and usage information.",
                    "tags": "NASA, satellite imagery, Earth observation, visualisation, climate", "featured": 0,
                },
                {
                    "title": "Polar Data Catalogue",
                    "type": "Dataset", "category": "Data & Tools", "region": "Arctic", "year": 2026,
                    "author": "Polar Data Catalogue",
                    "url": "https://www.polardata.ca/",
                    "summary": "A repository to discover research datasets associated with Canada's Arctic and Antarctic research communities.",
                    "content": "Use the catalogue to discover datasets and metadata. Always inspect each record's geographical coverage, collection date, licensing and citation instructions before reusing data.",
                    "tags": "polar data, metadata, repository, Arctic, research", "featured": 0,
                },
            ]
            for item in samples:
                conn.execute(
                    """INSERT INTO resources
                    (title, type, category, region, year, author, url, summary, content, tags, file_name, created_at, featured)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
                    (item["title"], item["type"], item["category"], item["region"], item["year"], item["author"],
                     item["url"], item["summary"], item["content"], item["tags"], now_iso(), item["featured"]),
                )
            log_activity(conn, "system", None, "Added starter resources for the first-run demo")


def serialize_resource(row: sqlite3.Row | dict[str, Any], include_content: bool = False) -> dict[str, Any]:
    data = dict(row)
    data["has_file"] = bool(data.get("file_name"))
    if not include_content:
        data.pop("content", None)
    data.pop("file_name", None)
    return data


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def tokenize(text: str) -> set[str]:
    stop_words = {
        "what", "when", "where", "which", "with", "from", "into", "about", "have", "that", "this",
        "there", "their", "does", "your", "tell", "show", "give", "explain", "please", "could", "would",
        "should", "are", "the", "and", "for", "how", "why", "can", "was", "were", "who", "its", "it", "is",
        "a", "an", "of", "to", "in", "on", "by", "or", "be", "as", "at", "do", "i", "we", "me", "us",
    }
    words = set(re.findall(r"[a-zA-Z0-9-]{3,}", text.lower()))
    return words - stop_words


def retrieve_resources(query: str, limit: int = 4) -> list[sqlite3.Row]:
    query_words = tokenize(query)
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM resources ORDER BY featured DESC, created_at DESC").fetchall()
    scored: list[tuple[int, sqlite3.Row]] = []
    for row in rows:
        searchable = " ".join(str(row[key] or "") for key in ("title", "category", "region", "summary", "content", "tags", "author"))
        words = tokenize(searchable)
        score = len(query_words & words)
        # Give title/category/tag matches extra weight.
        score += 2 * len(query_words & tokenize(row["title"] or ""))
        score += len(query_words & tokenize(row["tags"] or ""))
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def call_openai(instructions: str, input_text: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "instructions": instructions, "input": input_text, "max_output_tokens": 700},
            timeout=35,
        )
        response.raise_for_status()
        payload = response.json()
        texts: list[str] = []
        for output_item in payload.get("output", []):
            for content in output_item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    texts.append(content["text"])
        return "\n".join(texts).strip() or None
    except (requests.RequestException, ValueError, TypeError):
        app.logger.exception("OpenAI Responses API request failed")
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "app": "Polar Science Knowledge Hub"})


@app.get("/api/dashboard")
def dashboard():
    with get_db() as conn:
        total_resources = conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        total_views = conn.execute("SELECT COALESCE(SUM(views),0) FROM resources").fetchone()[0]
        total_downloads = conn.execute("SELECT COALESCE(SUM(downloads),0) FROM resources").fetchone()[0]
        category_rows = conn.execute(
            "SELECT category, COUNT(*) AS count FROM resources GROUP BY category ORDER BY count DESC, category ASC"
        ).fetchall()
        region_rows = conn.execute(
            "SELECT region, COUNT(*) AS count FROM resources GROUP BY region ORDER BY count DESC, region ASC"
        ).fetchall()
        recent = conn.execute("SELECT * FROM resources ORDER BY created_at DESC, id DESC LIMIT 5").fetchall()
        popular = conn.execute("SELECT * FROM resources ORDER BY views DESC, featured DESC LIMIT 3").fetchall()
    return jsonify({
        "total_resources": total_resources,
        "total_views": total_views,
        "total_downloads": total_downloads,
        "categories": [dict(row) for row in category_rows],
        "regions": [dict(row) for row in region_rows],
        "recent": [serialize_resource(row) for row in recent],
        "popular": [serialize_resource(row) for row in popular],
    })


@app.get("/api/resources")
def list_resources():
    query = request.args.get("q", "").strip()[:120]
    category = request.args.get("category", "").strip()[:80]
    region = request.args.get("region", "").strip()[:80]
    kind = request.args.get("type", "").strip()[:80]
    sql = "SELECT * FROM resources WHERE 1=1"
    params: list[Any] = []
    if query:
        needle = f"%{query}%"
        sql += " AND (title LIKE ? OR summary LIKE ? OR tags LIKE ? OR author LIKE ? OR content LIKE ?)"
        params.extend([needle] * 5)
    if category:
        sql += " AND category = ?"
        params.append(category)
    if region:
        sql += " AND region = ?"
        params.append(region)
    if kind:
        sql += " AND type = ?"
        params.append(kind)
    sql += " ORDER BY featured DESC, created_at DESC, id DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        category_rows = conn.execute("SELECT DISTINCT category FROM resources ORDER BY category").fetchall()
        type_rows = conn.execute("SELECT DISTINCT type FROM resources ORDER BY type").fetchall()
        region_rows = conn.execute("SELECT DISTINCT region FROM resources ORDER BY region").fetchall()
    return jsonify({
        "items": [serialize_resource(row) for row in rows],
        "filters": {
            "categories": [r[0] for r in category_rows],
            "types": [r[0] for r in type_rows],
            "regions": [r[0] for r in region_rows],
        },
        "count": len(rows),
    })


@app.get("/api/resources/<int:resource_id>")
def resource_detail(resource_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if not row:
            return jsonify({"error": "Resource not found"}), 404
        conn.execute("UPDATE resources SET views = views + 1 WHERE id = ?", (resource_id,))
        log_activity(conn, "view", resource_id, row["title"])
        updated = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    return jsonify(serialize_resource(updated, include_content=True))


@app.post("/api/resources")
def create_resource():
    form = request.form if request.form else (request.get_json(silent=True) or {})
    title = str(form.get("title", "")).strip()
    if not title:
        return jsonify({"error": "Please enter a resource title."}), 400
    if len(title) > 180:
        return jsonify({"error": "Title must be 180 characters or fewer."}), 400

    kind = str(form.get("type", "Article")).strip()
    if kind not in RESOURCE_TYPES:
        kind = "Other"
    category = str(form.get("category", "General")).strip()[:80] or "General"
    region = str(form.get("region", "Global")).strip()
    if region not in REGIONS:
        region = "Other"
    year_raw = str(form.get("year", "")).strip()
    try:
        year = int(year_raw) if year_raw else None
        if year is not None and not 1900 <= year <= 2100:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Year must be between 1900 and 2100."}), 400

    url = str(form.get("url", "")).strip()[:1000]
    if url and not (url.startswith("https://") or url.startswith("http://")):
        return jsonify({"error": "Link must start with http:// or https://."}), 400

    saved_filename = ""
    upload = request.files.get("file") if hasattr(request, "files") else None
    if upload and upload.filename:
        original_name = secure_filename(upload.filename)
        if not original_name or not allowed_file(original_name):
            return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."}), 400
        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        saved_filename = f"{stamp}_{original_name}"
        upload.save(UPLOAD_FOLDER / saved_filename)

    summary = str(form.get("summary", "")).strip()[:1500]
    content = str(form.get("content", "")).strip()[:12000]
    tags = str(form.get("tags", "")).strip()[:400]
    author = str(form.get("author", "")).strip()[:140]

    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO resources
            (title, type, category, region, year, author, url, summary, content, tags, file_name, created_at, featured)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (title, kind, category, region, year, author, url, summary, content, tags, saved_filename, now_iso()),
        )
        resource_id = cursor.lastrowid
        log_activity(conn, "created", resource_id, title)
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    return jsonify(serialize_resource(row)), 201


@app.get("/api/resources/<int:resource_id>/download")
def download_resource(resource_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if not row:
            abort(404)
        if row["file_name"]:
            conn.execute("UPDATE resources SET downloads = downloads + 1 WHERE id = ?", (resource_id,))
            log_activity(conn, "download", resource_id, row["title"])
            filename = row["file_name"]
        elif row["url"]:
            conn.execute("UPDATE resources SET downloads = downloads + 1 WHERE id = ?", (resource_id,))
            log_activity(conn, "open_link", resource_id, row["title"])
            return redirect(row["url"])
        else:
            return jsonify({"error": "This resource has no file or external link."}), 404
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True, download_name=filename.split("_", 1)[-1])


@app.post("/api/ask")
def ask_polar_assistant():
    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip()[:1200]
    if not question:
        return jsonify({"error": "Type a question first."}), 400
    matches = retrieve_resources(question, limit=4)
    sources = [
        {"id": row["id"], "title": row["title"], "url": row["url"], "summary": row["summary"], "category": row["category"]}
        for row in matches
    ]
    context = "\n\n".join(
        f"SOURCE {index + 1}\nTitle: {row['title']}\nCategory: {row['category']}\nRegion: {row['region']}\n"
        f"Summary: {row['summary']}\nNotes: {row['content']}\nURL: {row['url']}"
        for index, row in enumerate(matches)
    )
    ai_answer = None
    if matches:
        ai_answer = call_openai(
            "You are Polar Research Assistant inside a polar-science knowledge portal. Answer using only the supplied resource context. "
            "Do not invent facts or imply these snippets are exhaustive. Cite sources inline by their exact title in square brackets. "
            "If the context does not answer a question, say so and suggest what kind of source is needed. Use plain language.",
            f"QUESTION: {question}\n\nRESOURCE CONTEXT:\n{context}",
        )
    mode = "ai" if ai_answer else "local"
    if ai_answer:
        answer = ai_answer
    elif matches:
        bullets = "\n".join(f"• **{row['title']}** — {row['summary']}" for row in matches[:3])
        answer = (
            "I’m running in local retrieval mode, so this answer is based on matching resources in the hub rather than a generative AI model.\n\n"
            f"For **{question}**, these are the most relevant records I found:\n\n{bullets}\n\n"
            "Open the source records to read the original material. The hub has not independently verified the linked research."
        )
    else:
        answer = (
            "I couldn’t find a close match in the current repository, so I don’t want to guess. Try a broader query such as "
            "‘sea ice’, ‘Antarctic research’, ‘satellite imagery’, or add a relevant report in the Knowledge Library."
        )
    return jsonify({"answer": answer, "sources": sources, "mode": mode})


@app.post("/api/generate")
def generate_outreach_content():
    body = request.get_json(silent=True) or {}
    topic = str(body.get("topic", "")).strip()[:500]
    output_type = str(body.get("format", "social")).strip().lower()
    audience = str(body.get("audience", "general public")).strip()[:120]
    if not topic:
        return jsonify({"error": "Enter a topic to create outreach content."}), 400
    format_names = {
        "social": "a concise social media post with a title and a call to explore the source",
        "classroom": "a student-friendly explainer with a short definition, three learning points and one discussion question",
        "brief": "a short policy/research brief with key message, evidence needed and caveats",
        "newsletter": "a newsletter paragraph with a headline, plain-language explanation and source reminder",
    }
    chosen_format = format_names.get(output_type, format_names["social"])
    matches = retrieve_resources(topic, limit=3)
    context = "\n".join(f"{r['title']}: {r['summary']} Source: {r['url']}" for r in matches)
    generated = call_openai(
        "You create responsible science outreach. Do not invent study findings, statistics, quotes, or citations. "
        "If the supplied source context is insufficient, clearly label claims that need verification. Keep all claims understandable to the audience.",
        f"Create {chosen_format} for {audience}. Topic: {topic}\nAvailable source context:\n{context or 'No matching hub sources were found.'}\n"
        "Include a brief source-check reminder at the end.",
    )
    if generated:
        content = generated
        mode = "ai"
    else:
        related = matches[0]["title"] if matches else "a verified polar-science source"
        if output_type == "classroom":
            content = (
                f"# {topic}\n\n**In simple words:** {topic} is a topic to explore using reliable observations and scientific evidence.\n\n"
                f"**Learning points**\n1. Define the key terms connected to {topic}.\n2. Identify the location, time period and method behind the evidence.\n"
                f"3. Compare the findings with another credible source.\n\n**Discuss:** What additional data would help us understand {topic} better?\n\n"
                f"**Source-check:** Start with {related}; verify facts and dates against the original material before publishing."
            )
        elif output_type == "brief":
            content = (
                f"# Evidence brief: {topic}\n\n**Key message:** Explain the relevance of {topic} using evidence from a traceable polar-science source.\n\n"
                f"**Evidence to include:** Observation period, study area, measurement method, uncertainty and comparison baseline.\n\n"
                f"**Caveat:** No quantitative claim is included in this draft because it has not been verified here.\n\n"
                f"**Suggested starting point:** {related}."
            )
        elif output_type == "newsletter":
            content = (
                f"**Exploring {topic}**\n\nPolar research helps explain how Earth's high-latitude environments work and change. "
                f"This story will introduce {topic}, show why it matters, and guide readers to the underlying evidence. "
                f"Before sending, add a verified finding and link to the original source: {related}."
            )
        else:
            content = (
                f"❄️ **Let's explore: {topic}**\n\nWhat can polar science teach us about Earth's changing environments? "
                f"Start with a clear question, check the evidence, and follow the research back to its source.\n\n"
                f"🔎 Explore: {related}\n\n#PolarScience #EarthScience #ScienceCommunication\n\n"
                "*Draft for review: confirm all scientific claims and image credits before publishing.*"
            )
        mode = "template"
    return jsonify({"content": content, "mode": mode, "sources": [{"title": r["title"], "url": r["url"]} for r in matches]})


@app.get("/api/analytics")
def analytics_overview():
    """Return repository metadata aggregates for the Data Analytics workspace.

    These statistics describe the records stored in this portal. They are not
    scientific conclusions about Earth's polar regions.
    """
    with get_db() as conn:
        totals = conn.execute(
            """SELECT COUNT(*) AS total_resources,
                      COALESCE(SUM(views), 0) AS total_views,
                      COALESCE(SUM(downloads), 0) AS total_downloads,
                      COUNT(DISTINCT region) AS region_count,
                      COUNT(DISTINCT category) AS category_count,
                      SUM(CASE WHEN type = 'Dataset' THEN 1 ELSE 0 END) AS dataset_count,
                      SUM(CASE WHEN year IS NULL THEN 1 ELSE 0 END) AS missing_year_count,
                      SUM(CASE WHEN url IS NULL OR TRIM(url) = '' THEN 1 ELSE 0 END) AS missing_url_count,
                      AVG(year) AS average_publication_year
               FROM resources"""
        ).fetchone()
        by_type = conn.execute(
            "SELECT type AS label, COUNT(*) AS count FROM resources GROUP BY type ORDER BY count DESC, label"
        ).fetchall()
        by_region = conn.execute(
            "SELECT region AS label, COUNT(*) AS count FROM resources GROUP BY region ORDER BY count DESC, label"
        ).fetchall()
        by_category = conn.execute(
            "SELECT category AS label, COUNT(*) AS count FROM resources GROUP BY category ORDER BY count DESC, label LIMIT 10"
        ).fetchall()
        by_year = conn.execute(
            "SELECT year AS label, COUNT(*) AS count FROM resources WHERE year IS NOT NULL GROUP BY year ORDER BY year"
        ).fetchall()
        popular = conn.execute(
            "SELECT title, type, category, region, views, downloads FROM resources ORDER BY (views + downloads) DESC, title LIMIT 5"
        ).fetchall()
        activity = conn.execute(
            "SELECT action AS label, COUNT(*) AS count FROM activity GROUP BY action ORDER BY count DESC, label"
        ).fetchall()
        quality = conn.execute(
            """SELECT
                 SUM(CASE WHEN TRIM(COALESCE(title, '')) = '' THEN 1 ELSE 0 END) AS missing_title,
                 SUM(CASE WHEN TRIM(COALESCE(category, '')) = '' THEN 1 ELSE 0 END) AS missing_category,
                 SUM(CASE WHEN TRIM(COALESCE(region, '')) = '' THEN 1 ELSE 0 END) AS missing_region,
                 SUM(CASE WHEN year IS NOT NULL AND (year < 1900 OR year > 2100) THEN 1 ELSE 0 END) AS invalid_year
               FROM resources"""
        ).fetchone()

    total = dict(totals)
    avg_year = total.get("average_publication_year")
    total["average_publication_year"] = round(float(avg_year), 1) if avg_year is not None else None
    for key, value in list(total.items()):
        if value is None and key != "average_publication_year":
            total[key] = 0
    return jsonify({
        "totals": total,
        "by_type": [dict(row) for row in by_type],
        "by_region": [dict(row) for row in by_region],
        "by_category": [dict(row) for row in by_category],
        "by_year": [dict(row) for row in by_year],
        "popular": [dict(row) for row in popular],
        "activity": [dict(row) for row in activity],
        "quality": {key: int(value or 0) for key, value in dict(quality).items()},
    })


@app.post("/api/analytics/upload-csv")
def analyze_csv_dataset():
    """Profile an uploaded CSV in memory; uploaded analysis data is not retained."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a CSV file to analyse."}), 400
    if not upload.filename.lower().endswith(".csv"):
        return jsonify({"error": "Please upload a .csv file."}), 400

    raw = upload.stream.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        return jsonify({"error": "CSV files must be 10 MB or smaller."}), 413
    if not raw.strip():
        return jsonify({"error": "The CSV file is empty."}), 400

    try:
        # Limit the number of rows/columns to keep a public demo responsive.
        frame = pd.read_csv(io.BytesIO(raw), nrows=100001, low_memory=False)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        return jsonify({"error": f"Could not read this CSV. Check its encoding and delimiters. Details: {str(exc)[:180]}"}), 400
    except Exception as exc:
        app.logger.exception("CSV profiling failed while reading a file")
        return jsonify({"error": f"Could not analyse this file: {str(exc)[:180]}"}), 400

    if frame.empty:
        return jsonify({"error": "The CSV has column headers but no data rows."}), 400
    if len(frame) > 100000:
        return jsonify({"error": "This demo accepts up to 100,000 rows per CSV."}), 400
    if len(frame.columns) > 100:
        return jsonify({"error": "This demo accepts up to 100 columns per CSV."}), 400
    # Normalize header labels for display without mutating source data values.
    frame.columns = [str(column).strip() or f"Column {index + 1}" for index, column in enumerate(frame.columns)]
    row_count, column_count = frame.shape
    missing_by_column = frame.isna().sum()
    total_cells = row_count * column_count
    missing_cells = int(missing_by_column.sum())
    duplicate_rows = int(frame.duplicated().sum())
    numeric_columns = list(frame.select_dtypes(include="number").columns)
    categorical_columns = [column for column in frame.columns if column not in numeric_columns]

    column_profile = []
    for column in frame.columns:
        series = frame[column]
        examples = []
        for value in series.dropna().astype(str).head(3).tolist():
            examples.append(value[:100])
        column_profile.append({
            "name": str(column),
            "data_type": str(series.dtype),
            "missing_count": int(series.isna().sum()),
            "missing_percent": round(float(series.isna().mean() * 100), 1),
            "unique_values": int(series.nunique(dropna=True)),
            "examples": examples,
        })

    numeric_summary = []
    for column in numeric_columns[:15]:
        series = pd.to_numeric(frame[column], errors="coerce")
        numeric_summary.append({
            "column": str(column),
            "count": int(series.count()),
            "mean": _safe_stat(series.mean()),
            "median": _safe_stat(series.median()),
            "min": _safe_stat(series.min()),
            "max": _safe_stat(series.max()),
            "std_dev": _safe_stat(series.std()),
        })

    categorical_summary = []
    for column in categorical_columns[:10]:
        counts = frame[column].fillna("(missing)").astype(str).value_counts().head(5)
        categorical_summary.append({
            "column": str(column),
            "values": [{"value": str(value)[:100], "count": int(count)} for value, count in counts.items()],
        })

    preview = json.loads(frame.head(8).to_json(orient="records", date_format="iso"))
    insights = [f"Loaded {row_count:,} rows across {column_count} columns."]
    insights.append(f"{len(numeric_columns)} numeric column(s) and {len(categorical_columns)} non-numeric column(s) detected.")
    if missing_cells:
        insights.append(f"{missing_cells:,} missing cell(s) found ({(missing_cells / total_cells * 100):.1f}% of all cells). Inspect the column profile before modelling or charting.")
    else:
        insights.append("No missing cells were detected in this file.")
    if duplicate_rows:
        insights.append(f"{duplicate_rows:,} duplicate row(s) detected; review them before removing anything.")
    else:
        insights.append("No exact duplicate rows were detected.")
    if column_count > 0:
        highest_missing = missing_by_column.sort_values(ascending=False)
        if len(highest_missing) and int(highest_missing.iloc[0]) > 0:
            insights.append(f"Column with the most missing values: '{highest_missing.index[0]}' ({int(highest_missing.iloc[0])} missing).")

    return jsonify({
        "filename": secure_filename(upload.filename) or "uploaded.csv",
        "rows": int(row_count),
        "columns": int(column_count),
        "numeric_column_count": len(numeric_columns),
        "categorical_column_count": len(categorical_columns),
        "missing_cells": missing_cells,
        "missing_percent": round((missing_cells / total_cells * 100), 1) if total_cells else 0,
        "duplicate_rows": duplicate_rows,
        "column_profile": column_profile,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "preview": preview,
        "insights": insights,
        "retained": False,
    })


def _safe_stat(value: Any) -> float | None:
    """Return a finite, JSON-safe numeric statistic rounded for display."""
    if value is None or pd.isna(value):
        return None
    numeric = float(value)
    return round(numeric, 4) if math.isfinite(numeric) else None


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"error": "That file is too large. Maximum upload size is 30 MB."}), 413


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found."}), 404
    return "Page not found", 404


init_db()

if __name__ == "__main__":
    # Debug mode is convenient for a local hackathon prototype. Turn it off before deployment.
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
