from fastapi import APIRouter, Form, Request, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import SessionLocal
from app.models import Articles
from app.schemas import LinkCreate
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/add", response_class=HTMLResponse)
def add_url_form(request: Request):
    return templates.TemplateResponse("add_url.html", {"request": request})

@router.post("/add", response_class=HTMLResponse)
def add_url(request: Request, url: str = Form(...), title: str = Form(None), db: Session = Depends(get_db)):
    # Validate with Pydantic if desired
    # link_data = LinkCreate(url=url)  # Raises error if invalid
    new_article = Articles(url=url, title=title, status="new", scraped_date=datetime.datetime.utcnow())
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    return templates.TemplateResponse("add_url.html", {
        "request": request,
        "message": f"URL '{url}' added for processing."
    })

@router.get("/recent", response_class=HTMLResponse)
def recently_added(request: Request, db: Session = Depends(get_db), limit: int = 50):
    articles = db.query(Articles).order_by(Articles.id.desc()).limit(limit).all()
    return templates.TemplateResponse("recently_added.html", {
        "request": request,
        "articles": articles
    })
