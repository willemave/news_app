from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import List, Optional
from datetime import datetime, date
from app.database import SessionLocal, init_db
from app.models import Articles, Links
from app.schemas import Article
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_class=HTMLResponse)
def get_daily_articles(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 50,
    source: Optional[str] = None,
    date: Optional[str] = None
):
    """Get articles with optional source and date filtering."""
    
    # Get available dates for the dropdown
    available_dates_query = db.query(
        func.date(Articles.scraped_date).label('date')
    ).distinct().order_by(func.date(Articles.scraped_date).desc())
    
    available_dates = []
    for row in available_dates_query.all():
        if row.date:
            # Handle both string and date objects
            if isinstance(row.date, str):
                available_dates.append(row.date)
            else:
                available_dates.append(row.date.strftime('%Y-%m-%d'))
    
    # Query articles with their linked source information
    query = db.query(Articles).join(Links, Articles.link_id == Links.id)
    
    # Apply source filter
    if source:
        query = query.filter(Links.source == source)
    
    # Apply date filter
    if date:
        try:
            filter_date = datetime.strptime(date, '%Y-%m-%d').date()
            query = query.filter(func.date(Articles.scraped_date) == filter_date)
        except ValueError:
            # Invalid date format, ignore filter
            pass
    
    # Order by scraped date (newest first) and apply limit
    articles = query.order_by(Articles.scraped_date.desc()).limit(limit).all()
    
    return templates.TemplateResponse("articles.html", {
        "request": request,
        "articles": articles,
        "current_source": source,
        "current_date": date,
        "available_dates": available_dates
    })

@router.get("/detail/{article_id}", response_class=HTMLResponse)
def detailed_article(request: Request, article_id: int, db: Session = Depends(get_db)):
    article = db.query(Articles).join(Links, Articles.link_id == Links.id).filter(Articles.id == article_id).first()
    return templates.TemplateResponse("detailed_article.html", {
        "request": request,
        "article": article
    })
