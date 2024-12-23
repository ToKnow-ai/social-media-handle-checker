import re
import inspect
import requests
import re
import asyncio
from typing import Any, Callable, Coroutine

def get_socials():
    return [
        {
        "id": "instagram",
        "name": "Instagram",
        "img": "https://cdn.jsdelivr.net/npm/simple-icons@v6/icons/instagram.svg",
        "validate": is_valid_instagram_username,
        "resolve": resolve_instagram_username,
        "message": lambda username: (
            f'username <b>"{username}"</b> is ✅ Available.'
            ' However, usernames from disabled or deleted accounts may also appear'
            ' available but you can\'t choose them, eg: usernames like <b>"we"</b>, <b>"us"</b>, and <b>"the"</b>.'
            ' Go to <a target="_blank" href="https://accountscenter.instagram.com/">accounts center</a>'
            " and try changing the username of an existing account and see if it it's available")
    },
    # {
    #     id: "x",
    #     name: "X (formerly Twitter)",
    #     img: "https://cdn.jsdelivr.net/npm/simple-icons@v6/icons/twitter.svg"
    # },
    # {
    #     id: "linkedin-user",
    #     name: "LinkedIn User",
    #     img: "https://cdn.jsdelivr.net/npm/simple-icons@v6/icons/linkedin.svg",
    #     message = (
    #                 f'username <b>"{username}"</b> is ✅ Available.'
    #                 ' However, usernames from private or deleted accounts will appear'
    #                 " available, login into LinkedIn and go to"
    #                 f" \"https://www.linkedin.com/in/{username}\" and see if it it's available"))
    # },
    # {
    #     id: "linkedin-page",
    #     name: "LinkedIn Company",
    #     img: "https://cdn.jsdelivr.net/npm/simple-icons@v6/icons/linkedin.svg"
    # }
    ]

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

def get_logger() -> tuple[list[dict[str, str]], Callable[[str, str], None]]:
    logs = []
    return logs, lambda key, value: logs.append({ "key": key, "value": value })

def get_json_value(page_source, key, value_pattern):
    pattern = rf'[\'"]?{key}[\'"]?\s*:\s*[\'"]?({value_pattern})[\'"]?'
    match = re.search(pattern, page_source, flags=re.IGNORECASE)
    return match.group(1) if match else None

async def availability_response(
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
        logger(f"{availability_response.__name__}:Exception", str(e))
        return { 'message': f"❌ {str(e)}" }
    
def resolve_instagram_username(
        username: str, logger: Callable[[str, str], None]) -> tuple[str, bool, str]:
    def resolve() -> bool:
        profile_uri = f"https://www.instagram.com/{username}/"
        profile_response = requests.get(profile_uri, allow_redirects = False)
        logger(
            "profile_response_status", 
             f"{profile_response.status_code} {profile_response.headers.get('Location')}" \
              if profile_response.status_code in [301, 302] \
              else profile_response.status_code)
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