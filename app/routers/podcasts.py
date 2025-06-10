from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from ..database import get_db
from ..models import Podcasts, PodcastStatus
from ..config import logger
from ..templates import templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def get_podcasts_page(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Number of podcasts to return"),
    download_date: Optional[str] = Query(None, description="Filter by download date")
):
    """
    Get the podcasts HTML page with optional filtering and pagination.
    """
    try:
        query = db.query(Podcasts)
        
        # Apply date filter
        if download_date:
            try:
                # Parse the date string and filter by that specific date
                filter_date = datetime.strptime(download_date, "%Y-%m-%d").date()
                query = query.filter(
                    db.func.date(Podcasts.download_date) == filter_date
                )
            except ValueError:
                pass  # Invalid date format, ignore filter
        
        # Order by creation date (newest first)
        query = query.order_by(Podcasts.created_date.desc())
        
        # Apply limit
        podcasts = query.limit(limit).all()
        
        # Get unique download dates for filter dropdown
        download_dates_query = db.query(
            db.func.date(Podcasts.download_date).label('date')
        ).filter(
            Podcasts.download_date.isnot(None)
        ).distinct().order_by(db.func.date(Podcasts.download_date).desc())
        
        download_dates = [row.date.strftime('%Y-%m-%d') for row in download_dates_query.all() if row.date]
        
        return templates.TemplateResponse("podcasts.html", {
            "request": request,
            "podcasts": podcasts,
            "current_download_date": download_date,
            "download_dates": download_dates
        })
        
    except Exception as e:
        logger.error(f"Error in podcasts page: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/detail/{podcast_id}", response_class=HTMLResponse)
def get_podcast_detail_page(
    request: Request, 
    podcast_id: int, 
    db: Session = Depends(get_db)
):
    """
    Get the podcast detail HTML page.
    """
    try:
        podcast = db.query(Podcasts).filter(Podcasts.id == podcast_id).first()
        
        if not podcast:
            raise HTTPException(status_code=404, detail="Podcast not found")
        
        # Read transcript if available
        transcript_text = None
        if podcast.transcribed_text_path:
            try:
                with open(podcast.transcribed_text_path, 'r', encoding='utf-8') as f:
                    transcript_text = f.read()
            except FileNotFoundError:
                pass
        
        return templates.TemplateResponse("podcast_detail.html", {
            "request": request,
            "podcast": podcast,
            "transcript": transcript_text
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in podcast detail page: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")