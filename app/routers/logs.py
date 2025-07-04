import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.templates import templates

router = APIRouter(prefix="/admin")

# Get logs directory
LOGS_DIR = Path("logs")
ERRORS_DIR = LOGS_DIR / "errors"


@router.get("/logs", response_class=HTMLResponse)
async def list_logs(request: Request):
    """List all log files with recent error logs."""
    log_files = []
    recent_errors = []
    
    # Get all log files from errors directory
    if ERRORS_DIR.exists():
        for file_path in ERRORS_DIR.glob("*.log"):
            stat = file_path.stat()
            log_files.append(
                {
                    "filename": f"errors/{file_path.name}",
                    "size": f"{stat.st_size / 1024:.1f} KB",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "modified_timestamp": stat.st_mtime,
                }
            )
        
        # Get all JSONL error files
        for file_path in ERRORS_DIR.glob("*.jsonl"):
            stat = file_path.stat()
            log_files.append(
                {
                    "filename": f"errors/{file_path.name}",
                    "size": f"{stat.st_size / 1024:.1f} KB",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "modified_timestamp": stat.st_mtime,
                }
            )
    
    # Also check root logs directory for any remaining log files
    if LOGS_DIR.exists():
        for file_path in LOGS_DIR.glob("*.log"):
            if file_path.is_file():  # Skip directories
                stat = file_path.stat()
                log_files.append(
                    {
                        "filename": file_path.name,
                        "size": f"{stat.st_size / 1024:.1f} KB",
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "modified_timestamp": stat.st_mtime,
                    }
                )

    # Sort by modified time, newest first
    log_files.sort(key=lambda x: x["modified_timestamp"], reverse=True)
    
    # Remove timestamp from final output
    for log in log_files:
        log.pop("modified_timestamp", None)
    
    # Get recent errors from the most recent error files
    recent_errors = _get_recent_errors(limit=10)

    return templates.TemplateResponse(
        "logs_list.html", {"request": request, "log_files": log_files, "recent_errors": recent_errors}
    )


@router.get("/logs/{filename:path}", response_class=HTMLResponse)
async def view_log(request: Request, filename: str):
    """View specific log file content."""
    file_path = LOGS_DIR / filename

    # Security check - ensure file is in logs directory
    if not file_path.exists() or not str(file_path.resolve()).startswith(str(LOGS_DIR.resolve())):
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        # Handle JSONL files differently
        if file_path.suffix == ".jsonl":
            content = _format_jsonl_content(file_path)
        else:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

    return templates.TemplateResponse(
        "log_detail.html", {"request": request, "filename": filename, "content": content}
    )


@router.get("/logs/{filename:path}/download")
async def download_log(filename: str):
    """Download a log file."""
    file_path = LOGS_DIR / filename

    # Security check
    if not file_path.exists() or not str(file_path.resolve()).startswith(str(LOGS_DIR.resolve())):
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(path=str(file_path), filename=file_path.name, media_type="text/plain")


def _get_recent_errors(limit: int = 10) -> list[dict[str, Any]]:
    """Get the most recent errors from error log files."""
    errors = []
    
    if not ERRORS_DIR.exists():
        return errors
    
    # Get all JSONL error files
    error_files = list(ERRORS_DIR.glob("*.jsonl"))
    
    # Sort by modification time, newest first
    error_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Read errors from files until we have enough
    for file_path in error_files:
        if len(errors) >= limit:
            break
            
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    if len(errors) >= limit:
                        break
                    try:
                        error_data = json.loads(line.strip())
                        # Format the error for display
                        errors.append({
                            "timestamp": error_data.get("timestamp", "Unknown"),
                            "level": error_data.get("level", "ERROR"),
                            "source": error_data.get("source", file_path.stem),
                            "message": error_data.get("message", "No message"),
                            "file": file_path.name,
                        })
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    
    # Also check for regular .log files
    log_files = list(ERRORS_DIR.glob("*.log"))
    log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    for file_path in log_files:
        if len(errors) >= limit:
            break
            
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()
                # Get last few lines (reverse order)
                for line in reversed(lines[-5:]):
                    if len(errors) >= limit:
                        break
                    if line.strip():
                        errors.append({
                            "timestamp": "See file",
                            "level": "ERROR",
                            "source": file_path.stem,
                            "message": line.strip()[:200] + ("..." if len(line.strip()) > 200 else ""),
                            "file": file_path.name,
                        })
        except Exception:
            continue
    
    return errors


def _format_jsonl_content(file_path: Path) -> str:
    """Format JSONL file content for display."""
    formatted_lines = []
    
    try:
        with open(file_path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                try:
                    data = json.loads(line.strip())
                    # Pretty format the JSON
                    formatted = json.dumps(data, indent=2, ensure_ascii=False)
                    formatted_lines.append(f"=== Entry {i} ===")
                    formatted_lines.append(formatted)
                    formatted_lines.append("")  # Empty line for separation
                except json.JSONDecodeError:
                    formatted_lines.append(f"=== Entry {i} (Invalid JSON) ===")
                    formatted_lines.append(line.strip())
                    formatted_lines.append("")
    except Exception as e:
        return f"Error reading JSONL file: {str(e)}"
    
    return "\n".join(formatted_lines)
