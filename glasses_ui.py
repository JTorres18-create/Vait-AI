"""Private Meta Ray-Ban Display web interface for VAIT 1.0.

Drop this file and glasses.html next to main.py. No extra pip packages.
Attach at the *bottom* of main.py, after the existing endpoints:

    from glasses_ui import build_glasses_router
    app.include_router(build_glasses_router(chat, ChatRequest))

Set VAIT_GLASSES_PIN in Railway Variables to a private, strong passcode
(8 or more characters), not in GitHub. VAIT_ACCESS_TOKEN must be configured.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

COOKIE_NAME = "vait_glasses_session"
COOKIE_LIFETIME_S = 60 * 60 * 24  # One day per unlock
LOGIN_WINDOW_S = 15 * 60
MAX_FAILED_ATTEMPTS = 10
_attempts = defaultdict(deque)


class LoginPayload(BaseModel):
    pin: str = Field(min_length=1, max_length=200)


class GlassesMessage(BaseModel):
    message: str = Field(min_length=1, max_length=1200)


def _get_keys() -> tuple[str, str]:
    api_token = os.environ.get("VAIT_ACCESS_TOKEN", "").strip()
    glasses_pin = os.environ.get("VAIT_GLASSES_PIN", "")
    if not api_token or len(glasses_pin) < 8:
        raise HTTPException(
            status_code=503,
            detail="Glasses login is not configured. Set a VAIT_GLASSES_PIN of at least 8 characters in Railway Variables.",
        )
    return api_token, glasses_pin


def _make_session(secret: str) -> str:
    exp = str(int(time.time()) + COOKIE_LIFETIME_S)
    payload = f"glasses:v1:{exp}"
    mac = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{mac}"


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    if "." not in token:
        return False
    exp, mac = token.split(".", 1)
    if not exp.isascii() or not exp.isdecimal() or len(exp) > 12:
        return False
    try:
        if int(exp) < time.time():
            return False
        secret, _ = _get_keys()
    except HTTPException:
        return False
    expected = hmac.new(
        secret.encode(), f"glasses:v1:{exp}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(mac, expected)


def _check_auth(request: Request) -> None:
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Please unlock VAIT first.")


def _throttle(ip: str) -> bool:
    """Best-effort one-process failed PIN limiter; use an edge WAF in public production."""
    now = time.monotonic()
    bucket = _attempts[ip]
    while bucket and now - bucket[0] > LOGIN_WINDOW_S:
        bucket.popleft()
    return len(bucket) >= MAX_FAILED_ATTEMPTS


def build_glasses_router(
    chat_handler: Callable, chat_request_class: type
) -> APIRouter:
    """Share the existing chat backend without publishing its API key in JS."""
    router = APIRouter()
    html_path = Path(__file__).with_name("glasses.html")

    @router.get("/glasses", include_in_schema=False)
    def glasses_home():
        return FileResponse(
            str(html_path),
            media_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; "
                    "img-src 'self' data:; form-action 'self'; base-uri 'none'; "
                    "frame-ancestors 'none'"
                ),
            },
        )

    @router.get("/glasses/api/status")
    def glasses_status(request: Request):
        return {"authenticated": _is_authenticated(request)}

    @router.post("/glasses/api/login")
    def glasses_login(request: Request, payload: LoginPayload, response: Response):
        _, configured_pin = _get_keys()
        ip = request.client.host if request.client else "unknown"
        if _throttle(ip):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        if not secrets.compare_digest(payload.pin, configured_pin):
            _attempts[ip].append(time.monotonic())
            raise HTTPException(status_code=401, detail="Incorrect passcode.")
        _attempts.pop(ip, None)
        secret, _ = _get_keys()
        response.set_cookie(
            key=COOKIE_NAME,
            value=_make_session(secret),
            max_age=COOKIE_LIFETIME_S,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/glasses",
        )
        return {"authenticated": True}

    @router.post("/glasses/api/chat")
    async def glasses_chat(request: Request, payload: GlassesMessage):
        _check_auth(request)
        chat_request = chat_request_class(message=payload.message, mode="auto")
        result = await run_in_threadpool(chat_handler, chat_request)
        return {"response": result.get("response", ""), "assistant": "Vait"}

    @router.post("/glasses/api/logout")
    def glasses_logout(request: Request, response: Response):
        _check_auth(request)
        response.delete_cookie(COOKIE_NAME, path="/glasses", samesite="strict", secure=True)
        return {"authenticated": False}

    return router
