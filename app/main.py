from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import create_db_and_tables
from app.routers.auth import router as auth_router
from app.routers.tasks import router as tasks_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.include_router(auth_router)
app.include_router(tasks_router)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/app", response_class=HTMLResponse)
def app_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})