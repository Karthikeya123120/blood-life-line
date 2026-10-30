# LifeLine Blood Donor

A complete Flask + SQLite blood donor management website.

## Features
- User registration and login
- Blood donor registration
- Search available donors by blood group and city
- Blood request submission
- Admin dashboard
- Donor/request management
- JSON donor API
- Responsive Bootstrap UI
- Render deployment configuration

## Run locally

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Admin account
Email: admin@lifeline.com
Password: admin123

Change the admin password before using the project publicly.

## Render
Push the project to GitHub and create a Render Web Service.
Build command:
pip install -r requirements.txt

Start command:
gunicorn app:app

Note: SQLite on Render's ephemeral filesystem is suitable for a demo/project. For production, use PostgreSQL.
