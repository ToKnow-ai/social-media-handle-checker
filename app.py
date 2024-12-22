import sys
import os

# sys.path.append(os.path.abspath("../../../"))

import inspect
from typing import Callable, Literal
from quart import Quart, send_from_directory
from quart import Quart, Response, request
import requests
from bs4 import BeautifulSoup
import re
import asyncio
from typing import Any, Callable, Coroutine
# from python_utils.get_browser import get_browser_page_async
import re
from requests_tor import RequestsTor

app = Quart(__name__)


# Your custom JavaScript to inject
CUSTOM_SCRIPT = """
<script>
    // Add your custom logic here
    console.log('Custom script loaded in website B');
    // Example: Send message to parent window
    window.parent.postMessage('Hello from website B', '*');
</script>
"""

@app.route('/instagram/<path:path>', methods=['GET'])
async def proxy(path: str):
    # Construct the full URL for website B
    site_b_url = f"https://www.instagram.com/{path}/" # f"https://websiteB.com/{path}"  # Replace with actual domain
    
    try:
        # Forward the request to website B
        response = requests.get(
            site_b_url,
            # headers={k: v for k, v in request.headers if k.lower() != 'host'},
            # cookies=request.cookies,
            allow_redirects=False
        )  
        resp = Response(
            response.content,
            status=response.status_code
        )
        
        # Forward original headers while maintaining CORS
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(k, v) for k, v in response.headers.items()
                  if k.lower() not in excluded_headers]
        
        # Preserve CORS headers from original response
        cors_headers = ['access-control-allow-origin',
                       'access-control-allow-methods',
                       'access-control-allow-headers',
                       'access-control-allow-credentials']
        
        for header in headers:
            if header[0].lower() in cors_headers:
                resp.headers[header[0]] = header[1]
        
        return resp
    
    except requests.RequestException as e:
        return f"Error fetching content: {str(e)}", 500

@app.route('/')
async def index():
    """Route handler for the home page"""
    try:
        return await send_from_directory('.', 'index.html')
    except Exception as e:
        return str(e)

@app.route('/check/<platform>/<username>', methods=['GET'])
async def check_social_media_handle(platform: str, username: str):
    logs = []
    logger = lambda key, value: logs.append({ "key": key, "value": value })
    response = {}
    match platform.lower():
        case "instagram":
            response = await async_availability_status(
                resolve = resolve_instagram_username(username, logger),
                logger = logger,
                message = (
                    f'username <b>"{username}"</b> is ✅ Available.'
                    ' However, usernames from disabled or deleted accounts may also appear'
                    ' available but you can\'t choose them, eg: usernames like <b>"we"</b>, <b>"us"</b>, and <b>"the"</b>.'
                    ' Go to <a target="_blank" href="https://accountscenter.instagram.com/">accounts center</a>'
                    " and try changing the username of an existing account and see if it it's available"))
        case "linkedin-user":
            response = await async_availability_status(
                resolve = resolve_linkedin_username(username, "in", logger),
                logger = logger,
                message = (
                    f'username <b>"{username}"</b> is ✅ Available.'
                    ' However, usernames from private or deleted accounts will appear'
                    " available, login into LinkedIn and go to"
                    f" \"https://www.linkedin.com/in/{username}\" and see if it it's available"))
        case "linkedin-page":
            response = await async_availability_status(
                resolve = resolve_linkedin_username(username, "company", logger),
                logger = logger)
        case _:
            response = { 
                "message": f'❌ The platform "{platform}" is not supported' 
            }
    return {**response, "logs": logs}

def resolve_instagram_username(
        username: str, logger: Callable[[str, str], None]) -> tuple[str, bool, str]:
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
        - Can start or end with underscore
        """
        # Regex pattern for Instagram username validation
        pattern = r'^(?!.*\.\.)(?!.*\._)(?!.*_\.)[a-zA-Z0-9._][a-zA-Z0-9._]{0,28}[a-zA-Z0-9._]$'
        # Additional length check since regex alone might not handle it perfectly
        if len(username) < 1 or len(username) > 30:
            return False
        return re.match(pattern, username) is not None
    def resolve() -> bool:
        if not is_valid_instagram_username(username):
            raise Exception(f'"{username}" is not a valid instagram username')
        profile_uri = f"https:/www.instagram.com/{username}/"
        profile_response = requests.get(profile_uri, allow_redirects = False)
        profile_response_username = get_json_value(profile_response.text, "username", "\w+") or ""
        logger("profile_response_username", profile_response_username)
        _return_result = lambda is_available: (username, is_available, profile_uri)
        # if there is a username in the page, then this is likely an existing account
        if profile_response_username.lower().strip() == username.lower().strip():
            return _return_result(True)
        x_ig_app_id = get_json_value(profile_response.text, "X-IG-App-ID", "\d+")
        web_profile_response = requests.get(
           url=f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
           headers={
               "x-ig-app-id": x_ig_app_id,
           },
           allow_redirects = False)
        logger("web_profile_response.status_code", web_profile_response.status_code)
        # if status is 404, then the account doesnt exist!
        is_html = re.match(r'.*(\w+)/html', web_profile_response.headers.get("Content-Type"))
        if web_profile_response.status_code == 404 and is_html:
            return _return_result(False)
        # if status is 200, check status of the json
        is_json = re.match(r'.*(\w+)/json', web_profile_response.headers.get("Content-Type"))
        json_status = (web_profile_response.json() or {}).get('status') == 'ok' if is_json else False
        return _return_result(web_profile_response.status_code == 200 and json_status)
    return resolve

def resolve_linkedin_username(
        username: str, company_or_user: Literal["company", "in"], 
        logger: Callable[[str, str], None],) -> tuple[str, bool, str]:
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
        resolve: Callable[[str], Coroutine[Any, Any, bool]], 
        logger: Callable[[str, str], None],
        message: str = None):
    try:
        username_is_available_uri: tuple[str, bool, str] = await resolve()\
            if inspect.iscoroutinefunction(resolve) or inspect.isawaitable(resolve)\
            else await asyncio.to_thread(resolve)
        logger("username_is_available_uri", username_is_available_uri)
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
        logger(f"{async_availability_status.__name__}:Exception", str(e))
        return { 'message': f"❌ {str(e)}" }