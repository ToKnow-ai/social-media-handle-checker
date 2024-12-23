from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .utils import get_socials, get_logger, availability_response

app = FastAPI()

# Mount the entire static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

socials = get_socials()

@app.get('/')
async def index():
    try:
        return FileResponse('static/index.html')
    except Exception as e:
        return str(e)

@app.get('/check/{platform}/{username}')
async def check_social_media_handle(platform: str, username: str):
    social = next(i for i in socials if i.get('id') == platform)
    if social is None:
        return { 
            "message": f'❌ The platform "{platform}" is not supported' 
        }
    return await _resolve(username, **social)

async def _resolve(platform: str, username: str, *, validate, resolve, message = None):
    if not validate(username):
        raise Exception(f'"{username}" is not a valid {platform} handle/username')
    logs, logger = get_logger()
    response = await availability_response(
        resolve = resolve(username, logger),
        logger = logger,
        message = message(username) if message else None)
    return { **response, "logs": logs }