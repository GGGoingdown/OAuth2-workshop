# Application
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory="app/templates")


@router.get("/index")
def canopy_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
