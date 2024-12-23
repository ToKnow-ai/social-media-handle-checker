import json
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from utils import get_socials, get_logger, availability_response

app = FastAPI()

templates = Jinja2Templates(directory="templates")

socials = get_socials()

@app.get('/')
def index(request: Request):
    try:
        json_data = json.dumps([
            {  "id": i.get('id'), "name": i.get('name'), "img": i.get('img'), } 
            for i 
            in socials
        ])
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "json_data": json_data
        })
    except Exception as e:
        return str(e)

@app.get('/check/{platform}/{username}')
async def check_social_media_handle(platform: str, username: str):
    social = next(i for i in socials if i.get('id') == platform)
    if social is None:
        return { 
            "message": f'❌ The platform "{platform}" is not supported' 
        }
    return await _resolve(platform, username, **social)

async def _resolve(platform: str, username: str, *, validate, resolve, message = None, **_):
    if not validate(username):
        raise Exception(f'"{username}" is not a valid {platform} username')
    logs, logger = get_logger()
    response = await availability_response(
        resolve = resolve(username, logger),
        logger = logger,
        message = message(username) if message else None)
    return { **response, "logs": logs }