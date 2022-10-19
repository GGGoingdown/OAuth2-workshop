# Application
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
async def login(request: Request):
    response = templates.TemplateResponse("login.html", {"request": request})
    response.delete_cookie(key="session_id")
    return response


@router.get("/notify")
async def notify_page(request: Request):
    response = templates.TemplateResponse("notify_index.html", {"request": request})
    response.set_cookie(key="session_id", value="hello")
    return response
