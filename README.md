# Paperless Pal 2.0 — One-Day Hackathon MVP

A small Flask project designed to be installed and demoed in one day.

## Features
- Responsive dashboard
- Upload text-based PDFs and TXT files (max 10 MB)
- Extract text from PDFs
- Create a basic summary using the first few sentences
- Detect common date formats
- Save document history in SQLite
- View extracted text, copy it, download originals, delete records

## Windows + VS Code setup
1. Install Python 3.11+ from https://www.python.org/downloads/ and tick **Add Python to PATH**.
2. Install VS Code from https://code.visualstudio.com/ and the Python extension.
3. Extract the ZIP, then open the extracted `Paperless_Pal_2_One_Day` folder in VS Code.
4. Open **Terminal → New Terminal** and run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python app.py
   ```

   If PowerShell blocks activation, select **Command Prompt** as the VS Code terminal and run:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate.bat
   pip install -r requirements.txt
   python app.py
   ```

5. Open http://127.0.0.1:5000 in your browser.

## Demo checklist
1. Make a small text-based PDF with a paragraph and a date such as `12/11/2026`.
2. Upload it and show the summary, detected dates, and extracted text.
3. Copy text, download the file, then delete the record.
4. Explain the next steps: real AI summaries, document Q&A, scanned-PDF OCR, user login, and calendar reminders.

## Limitations
- This is an MVP, not a production-ready secure document service.
- Summary is rule-based (first four sentences), not AI-generated.
- Date detection is a simple pattern match; verify dates manually.
- Scanned/image-only PDFs may not contain selectable text and may return an empty result.
- Files and database are stored locally in this folder. Use sample documents for public demos.
- Do not expose Flask debug mode to the internet.
