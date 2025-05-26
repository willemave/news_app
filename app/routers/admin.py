from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import CronLogs
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import sys
import os
from pathlib import Path

# Add the project root to sys.path to allow importing from cron directory
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import the necessary functions
from cron.daily_ingest import run_daily_ingest
from cron.process_articles import process_articles

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_class=HTMLResponse)
def admin_index(request: Request):
    """
    Main admin index page that provides links to all admin functions
    """
    return templates.TemplateResponse("admin_index.html", {
        "request": request
    })

@router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    logs = db.query(CronLogs).all()
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "logs": logs
    })

@router.post("/trigger")
def trigger_ingestion(db: Session = Depends(get_db)):
    """
    Manually trigger the daily ingestion script.
    This directly calls the run_daily_ingest function rather than using subprocess.
    """
    try:
        run_daily_ingest()
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    except Exception as e:
        return {"status": "error", "message": f"Error triggering ingestion: {str(e)}"}

@router.post("/process")
def trigger_processing(db: Session = Depends(get_db)):
    """
    Manually trigger the article processing script.
    This directly calls the process_articles function rather than using subprocess.
    """
    try:
        processed, approved, errors = process_articles()
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    except Exception as e:
        return {"status": "error", "message": f"Error triggering processing: {str(e)}"}
