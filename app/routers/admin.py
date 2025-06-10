from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import CronLogs, Links, FailureLogs
from app.templates import templates
from fastapi.responses import HTMLResponse, RedirectResponse
import sys
from pathlib import Path

# Add the project root to sys.path to allow importing from cron directory
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import the necessary functions

router = APIRouter()

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
    links = db.query(Links).all()
    failures = db.query(FailureLogs).all()
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "logs": logs,
        "links": links,
        "failures": failures
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

@router.post("/run_scrapers")
def run_scrapers_now():
    """
    Manually trigger the scrapers to run immediately.
    This runs both HackerNews and Reddit scrapers.
    """
    try:
        # Import the run_all function from the scheduled job script
        import sys
        from pathlib import Path
        
        # Add scripts directory to path
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        sys.path.insert(0, str(scripts_dir))
        
        from run_scrapers_job import run_all
        
        # Run the scrapers
        run_all()
        
        return {"status": "ok", "message": "Scrapers executed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Error running scrapers: {str(e)}"}

