from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.templates import templates

router = APIRouter(prefix="/admin")

# Get logs directory
LOGS_DIR = Path("logs")


@router.get("/logs", response_class=HTMLResponse)
async def list_logs(request: Request):
    """List all log files."""
    if not LOGS_DIR.exists():
        log_files = []
    else:
        log_files = []
        for file_path in LOGS_DIR.glob("*.log"):
            stat = file_path.stat()
            log_files.append(
                {
                    "filename": file_path.name,
                    "size": f"{stat.st_size / 1024:.1f} KB",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        # Sort by modified time, newest first
        log_files.sort(key=lambda x: x["modified"], reverse=True)

    return templates.TemplateResponse(
        "logs_list.html", {"request": request, "log_files": log_files}
    )


@router.get("/logs/{filename}", response_class=HTMLResponse)
async def view_log(request: Request, filename: str):
    """View specific log file content."""
    file_path = LOGS_DIR / filename

    # Security check - ensure file is in logs directory
    if not file_path.exists() or not str(file_path).startswith(str(LOGS_DIR)):
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

    return templates.TemplateResponse(
        "log_detail.html", {"request": request, "filename": filename, "content": content}
    )


@router.get("/logs/{filename}/download")
async def download_log(filename: str):
    """Download a log file."""
    file_path = LOGS_DIR / filename

    # Security check
    if not file_path.exists() or not str(file_path).startswith(str(LOGS_DIR)):
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(path=str(file_path), filename=filename, media_type="text/plain")
