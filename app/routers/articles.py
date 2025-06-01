from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import SessionLocal, init_db
from app.models import Articles
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
def get_daily_articles(request: Request, db: Session = Depends(get_db), limit: int = 25, source: str = None):
    # Query articles, optionally filter by source
    query = db.query(Articles)
    if source:
        query = query.filter(Articles.source == source)
    articles = query.limit(limit).all()
    return templates.TemplateResponse("articles.html", {
        "request": request,
        "articles": articles,
        "current_source": source
    })

@router.get("/detail/{article_id}", response_class=HTMLResponse)
def detailed_article(request: Request, article_id: int, db: Session = Depends(get_db)):
    article = db.query(Articles).filter(Articles.id == article_id).first()
    return templates.TemplateResponse("detailed_article.html", {
        "request": request,
        "article": article
    })
