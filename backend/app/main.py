from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import jwt

from app.config import settings
from app.database import init_db
from app.routers import auth, agents, groups, messages, workflows, sessions, files, offline, audit, social, templates, scheduled_tasks, tasks, resources, reviews, hub, parliament, mcp_router
from app.websocket.manager import ws_manager
from app.websocket.agent_handler import handle_agent_websocket
from app.tunnel import TunnelManager
from app.mcp.server import init_mcp_server
from app.mcp.registry import global_registry
from app.mcp.client import global_mcp_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Ensure uploads directory exists
    _uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(_uploads_dir, exist_ok=True)

    tunnel_manager = None
    if settings.TUNNEL_ENABLED:
        tunnel_manager = TunnelManager(local_port=8000)
        await tunnel_manager.start()
        public_url = tunnel_manager.get_public_url()
        if public_url:
            settings.PUBLIC_URL = public_url

    print("aibond server started")
    print(f"DEBUG mode: {settings.DEBUG}")

    # 初始化 MCP Server（注入 registry 和 client）
    init_mcp_server(global_registry, global_mcp_client)
    print("MCP server initialized")

    if settings.PUBLIC_URL:
        # Convert https to wss for WebSocket connections
        wss_url = settings.PUBLIC_URL.replace("https://", "wss://")
        print(f"aibond server started, public URL: {wss_url}")
    else:
        print("aibond server started, public URL: (tunnel not available, local only)")
    if not settings._env_secret:
        print("WARNING: SECRET_KEY not set in environment. Using random key (sessions will not survive restart).")
    yield
    # Shutdown
    if tunnel_manager is not None:
        tunnel_manager.stop()
    print("aibond server stopped")

app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Human-AI Collaboration Platform",
    version="1.1.0",
    lifespan=lifespan,
)

# Security headers middleware
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; "
        "img-src 'self' data:"
    )
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response

# CORS - strict origin validation
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

# Global exception handler (don't leak internal errors)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    if settings.DEBUG:
        raise exc
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Static files - SDK packages download
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Routers
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(groups.router)
app.include_router(messages.router)
app.include_router(workflows.router)
app.include_router(sessions.router)
app.include_router(files.router)
app.include_router(offline.router)
app.include_router(audit.router)
app.include_router(social.router)
app.include_router(templates.router)
app.include_router(scheduled_tasks.router)
app.include_router(tasks.router)
app.include_router(resources.router)
app.include_router(reviews.router)
app.include_router(hub.router)
app.include_router(parliament.router)
app.include_router(mcp_router.router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "aibond"}

@app.get("/api/sdk/download")
async def download_sdk():
    """Download the aibond-agent SDK wheel package."""
    whl_path = os.path.join(_static_dir, "packages", "aibond_agent-0.1.0-py3-none-any.whl")
    if not os.path.isfile(whl_path):
        return JSONResponse(status_code=404, content={"detail": "SDK package not found"})
    return FileResponse(
        path=whl_path,
        filename="aibond_agent-0.1.0-py3-none-any.whl",
        media_type="application/octet-stream",
    )

@app.get("/api/sdk/info")
async def sdk_info():
    """Return SDK installation info and current server URL."""
    server_url = settings.PUBLIC_URL.replace("https://", "wss://") if settings.PUBLIC_URL else "ws://localhost:8000"
    http_url = settings.PUBLIC_URL if settings.PUBLIC_URL else "http://localhost:8000"
    return {
        "package": "aibond_agent-0.1.0-py3-none-any.whl",
        "download_url": f"{http_url}/api/sdk/download",
        "install_command": f"pip install {http_url}/api/sdk/download",
        "server_url": server_url,
        "http_server_url": http_url,
    }

@app.websocket("/ws/user/{user_id}")
async def user_websocket(websocket: WebSocket, user_id: str, token: str = Query(...)):
    # Validate JWT token during handshake
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        token_user_id = payload.get("sub")
        if not token_user_id or token_user_id != user_id:
            await websocket.close(code=4001, reason="Invalid token: user_id mismatch")
            return
    except jwt.ExpiredSignatureError:
        await websocket.close(code=4001, reason="Token expired")
        return
    except jwt.InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect_user(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")
            if msg_type == "heartbeat":
                await websocket.send_json({"type": "heartbeat_ack"})
            elif msg_type == "register":
                # Agent self-registration via user websocket (if needed)
                pass
            elif msg_type == "message":
                await ws_manager.broadcast_to_group(
                    data.get("target_user_ids", []),
                    data.get("target_agent_ids", []),
                    {"type": "message", "data": data}
                )
    except WebSocketDisconnect:
        ws_manager.disconnect_user(user_id, websocket)

@app.websocket("/ws/agent/{agent_id}")
async def agent_websocket(websocket: WebSocket, agent_id: str, api_key: str = Query(...)):
    await handle_agent_websocket(websocket, agent_id, api_key)
