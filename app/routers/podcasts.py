from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import Podcasts, PodcastStatus
from ..config import logger

router = APIRouter()

# Import templates from main to get the markdown filter
def get_templates():
    from app.main import templates
    return templates

@router.get("/", response_class=HTMLResponse)
def get_podcasts_page(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Number of podcasts to return"),
    status: Optional[str] = Query(None, description="Filter by podcast status"),
    feed_name: Optional[str] = Query(None, description="Filter by podcast feed name")
):
    """
    Get the podcasts HTML page with optional filtering and pagination.
    """
    try:
        query = db.query(Podcasts)
        
        # Apply filters
        if status:
            try:
                status_enum = PodcastStatus(status)
                query = query.filter(Podcasts.status == status_enum)
            except ValueError:
                pass  # Invalid status, ignore filter
        
        if feed_name:
            query = query.filter(Podcasts.podcast_feed_name.ilike(f"%{feed_name}%"))
        
        # Order by creation date (newest first)
        query = query.order_by(Podcasts.created_date.desc())
        
        # Apply limit
        podcasts = query.limit(limit).all()
        
        # Get unique feed names for filter dropdown
        feed_names = db.query(Podcasts.podcast_feed_name).distinct().all()
        feed_names = [name[0] for name in feed_names]
        
        return get_templates().TemplateResponse("podcasts.html", {
            "request": request,
            "podcasts": podcasts,
            "current_status": status,
            "current_feed": feed_name,
            "feed_names": feed_names
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
        
        return get_templates().TemplateResponse("podcast_detail.html", {
            "request": request,
            "podcast": podcast,
            "transcript": transcript_text
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in podcast detail page: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")