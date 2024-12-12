import sys
import os

sys.path.append(os.path.abspath("../../../"))

import inspect
from typing import Callable, Literal
from quart import Quart, send_from_directory
import requests
import re
import asyncio
from typing import Any, Callable, Coroutine
from python_utils.get_browser import get_browser_page_async
import re

app = Quart(__name__)

@app.route('/')
async def index():
    """Route handler for the home page"""
    try:
        return await send_from_directory('.', 'index.html')
    except Exception as e:
        return str(e)

@app.route('/check/<platform>/<username>', methods=['GET'])
async def check_social_media_handle(platform: str, username: str):
    match platform.lower():
        case "instagram":
            return await async_availability_status(
                resolve_instagram_username(username))
        case "linkedin-user":
            return await async_availability_status(
                resolve_linkedin_username(username, "in"))
        case "linkedin-page":
            return await async_availability_status(
                resolve_linkedin_username(username, "company"))
    return { 
        "message": f'❌ The platform "{platform}" is not supported' 
    }

def resolve_instagram_username(username: str) -> tuple[str, bool, str] :
    def get_json_value(page_source, key, value_pattern):
        pattern = rf'[\'"]?{key}[\'"]?\s*:\s*[\'"]?({value_pattern})[\'"]?'
        match = re.search(pattern, page_source, flags=re.IGNORECASE)
        return match.group(1) if match else None
    def is_valid_instagram_username(username):
        """
        Validates an Instagram username based on their username rules:
        - 1 to 30 characters long
        - Can contain letters (a-z), numbers (0-9), and periods/underscores
        - Cannot start or end with a period
        - Cannot have consecutive periods
        - Cannot have periods next to underscores
        """
        # Regex pattern for Instagram username validation
        pattern = r'^(?!.*\.\.)(?!.*\._)(?!.*_\.)(?![\.])[a-zA-Z0-9](?!.*\.$)[a-zA-Z0-9._]{0,28}[a-zA-Z0-9]$'
        return re.match(pattern, username) is not None
    def resolve() -> bool:
        restricted_usernames = ["username"]
        if username.lower() in restricted_usernames:
            raise Exception(f'"{username}" is not allowed')
        if not is_valid_instagram_username(username):
            raise Exception(f'"{username}" is not a valid instagram username')
        response = requests.get("https://www.instagram.com/")
        x_ig_app_id = get_json_value(response.text, "X-IG-App-ID", "\d+")
        user_data_response = requests.get(
           url=f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
           headers={
               "x-ig-app-id": x_ig_app_id,
           })
        return (
            username,
            user_data_response.ok and user_data_response.json().get('status') == 'ok', 
            f"https://www.instagram.com/{username}/")
    return resolve

def resolve_linkedin_username(username: str, company_or_user: Literal["company", "in"]) -> tuple[str, bool, str]:
    async def resolve() -> tuple[str, bool, str]:
        # can replace "www." with "de.", ".ke", ".ug", etc
        # inkedin private user => kamau
        uri: str = f"https://www.linkedin.com/{company_or_user}/{username}"
        page, close = await get_browser_page_async()
        response = None
        async def capture_response(resp):
            nonlocal response
            if uri in resp.url:
                response = resp
        page.on("response", capture_response)
        await page.goto("https://www.linkedin.com/")
        await page.evaluate(f"""
            fetch("{uri}", {{ "mode": "no-cors", "credentials": "include" }})
        """)
        await close()
        return (username, response.ok, uri)
    return resolve

async def async_availability_status(
        resolve: Callable[[str], Coroutine[Any, Any, bool]], message: str = None):
    try:
        username_is_available_uri: tuple[str, bool, str] = await resolve()\
            if inspect.iscoroutinefunction(resolve) or inspect.isawaitable(resolve)\
            else await asyncio.to_thread(resolve)
        username, is_available, uri = username_is_available_uri
        if is_available == True:
            return {
                'available': False,
                'message': f"{username}: ❌ Taken",
                'url': uri
            }
        if message:
            return {
                'available': True,
                'message': message,
                'url': uri
            }
        else:
            return {
                'available': True,
                'message': f"{username}: ✅ Available",
                'url': uri
            }
    except Exception as e:
        return {
            'message': f"❌ {str(e)}"
        }