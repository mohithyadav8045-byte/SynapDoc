
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory
)
from werkzeug.utils import secure_filename
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
DB_PATH = BASE / "paperless_pal.db"

UPLOADS.mkdir(exist_ok=True)

ALLOWED = {"pdf", "txt"}

app = Flask(__name__)
app.secret_key = "paperless-pal-demo-key-change-before-deployment"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# DATABASE

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                summary TEXT NOT NULL,
                dates TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
        """)


# EXTRACT TEXT

def extract_text(path, extension):
    if extension == "pdf":
        reader = PdfReader(str(path))
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        ).strip()

    return Path(path).read_text(
        encoding="utf-8",
        errors="replace"
    ).strip()


# BASIC SUMMARY

def summarize(text):
    cleaned = re.sub(r"\s+", " ", text).strip()

    if not cleaned:
        return "No selectable text found in this document."

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return " ".join(sentences[:4])[:1000]


# DATE DETECTION

def detect_dates(text):
    pattern = (
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
        r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2},?\s+\d{4})\b"
    )
    return list(dict.fromkeys(
        re.findall(pattern, text, re.I)
    ))[:15]


# SEARCH DOCUMENTS

STOP_WORDS = {
    "show", "me", "only", "find", "search", "get",
    "give", "want", "need", "the", "a", "an", "in",
    "on", "of", "for", "from", "is", "are", "please",
    "tell", "what", "all", "my", "document", "documents"
}


def search_documents(query):
    # Convert the question into useful search keywords.
    words = re.findall(r"[a-zA-Z0-9]+", query.lower())
    keywords = list(dict.fromkeys(
        word for word in words
        if word not in STOP_WORDS and len(word) > 1
    ))

    if not keywords:
        return []

    with connect() as con:
        documents = con.execute(
            "SELECT id, original_name, extracted_text "
            "FROM documents ORDER BY id DESC"
        ).fetchall()

    results = []

    for doc in documents:
        text = doc["extracted_text"] or ""

        # Search individual paragraphs first.
        chunks = [
            re.sub(r"\s+", " ", chunk).strip()
            for chunk in re.split(r"\n+", text)
            if chunk.strip()
        ]

        # If the PDF has no useful paragraph breaks,
        # fall back to sentence-based searching.
        if len(chunks) <= 1 and text.strip():
            chunks = re.split(r"(?<=[.!?])\s+", text)
            chunks = [
                re.sub(r"\s+", " ", chunk).strip()
                for chunk in chunks if chunk.strip()
            ]

        matches = []
        seen = set()

        for chunk in chunks:
            lower_chunk = chunk.lower()

            matched = [
                word for word in keywords
                if re.search(
                    r"(?<!\w)" + re.escape(word) + r"(?!\w)",
                    lower_chunk
                )
            ]

            if matched:
                score = len(matched)

                # Prefer passages that match more keywords.
                matches.append({
                    "text": chunk[:1200],
                    "score": score
                })

        # Keep the strongest matching passages.
        matches.sort(key=lambda item: item["score"], reverse=True)

        if matches:
            results.append({
                "id": doc["id"],
                "name": doc["original_name"],
                "matches": matches[:10]
            })

    return results


# HOME PAGE

@app.route("/")
def home():
    with connect() as con:
        documents = con.execute(
            "SELECT * FROM documents ORDER BY id DESC"
        ).fetchall()

    return render_template(
        "index.html",
        documents=documents,
        query="",
        results=[],
        searched=False
    )


# SEARCH PAGE

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    if len(query) > 200:
        flash("Please keep your search under 200 characters.", "error")
        query = query[:200]

    results = search_documents(query) if query else []

    with connect() as con:
        documents = con.execute(
            "SELECT * FROM documents ORDER BY id DESC"
        ).fetchall()

    return render_template(
        "index.html",
        documents=documents,
        query=query,
        results=results,
        searched=bool(query)
    )


# UPLOAD DOCUMENT

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("document")

    if not file or not file.filename:
        flash("Please choose a PDF or TXT file.", "error")
        return redirect(url_for("home"))

    filename = secure_filename(file.filename)

    if not filename or "." not in filename:
        flash("Invalid filename.", "error")
        return redirect(url_for("home"))

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED:
        flash("Only PDF and TXT files are supported.", "error")
        return redirect(url_for("home"))

    stored_name = (
        datetime.now().strftime("%Y%m%d%H%M%S%f")
        + "_" + filename
    )
    path = UPLOADS / stored_name
    file.save(path)

    try:
        text = extract_text(path, extension)
    except Exception:
        path.unlink(missing_ok=True)
        app.logger.exception("Document extraction failed")
        flash("Could not read the file. Try another PDF or TXT.", "error")
        return redirect(url_for("home"))

    with connect() as con:
        cursor = con.execute(
            """
            INSERT INTO documents (
                original_name, stored_name, extracted_text,
                summary, dates, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                stored_name,
                text,
                summarize(text),
                "\n".join(detect_dates(text)),
                datetime.now().strftime("%d %b %Y, %I:%M %p")
            )
        )
        doc_id = cursor.lastrowid

    flash("Document uploaded successfully!", "success")
    return redirect(url_for("detail", doc_id=doc_id))


# DOCUMENT DETAILS

@app.route("/document/<int:doc_id>")
def detail(doc_id):
    with connect() as con:
        doc = con.execute(
            "SELECT * FROM documents WHERE id = ?",
            (doc_id,)
        ).fetchone()

    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("home"))

    return render_template("document.html", doc=doc)


# DELETE DOCUMENT

@app.route("/document/<int:doc_id>/delete", methods=["POST"])
def delete(doc_id):
    with connect() as con:
        doc = con.execute(
            "SELECT * FROM documents WHERE id = ?",
            (doc_id,)
        ).fetchone()

        if doc:
            (UPLOADS / doc["stored_name"]).unlink(missing_ok=True)
            con.execute(
                "DELETE FROM documents WHERE id = ?",
                (doc_id,)
            )
            flash("Document deleted.", "success")
        else:
            flash("Document not found.", "error")

    return redirect(url_for("home"))


# DOWNLOAD DOCUMENT

@app.route("/document/<int:doc_id>/download")
def download(doc_id):
    with connect() as con:
        doc = con.execute(
            "SELECT * FROM documents WHERE id = ?",
            (doc_id,)
        ).fetchone()

    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("home"))

    return send_from_directory(
        UPLOADS,
        doc["stored_name"],
        as_attachment=True,
        download_name=doc["original_name"]
    )


# FILE SIZE ERROR

@app.errorhandler(413)
def too_large(error):
    flash("File too large. Maximum size is 10 MB.", "error")
    return redirect(url_for("home"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
