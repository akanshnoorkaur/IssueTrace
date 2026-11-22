from __future__ import annotations
"""
IssueLens — Main FastAPI Application

Entry point for the backend server.
Configures middleware, database, and routes.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, HTMLResponse

from app.config import get_settings
from app.database import init_database
from app.api.routes import router

INDEX_HTML = Path(__file__).parent.parent.parent / "index.html"


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events.
    
    - On startup: Initialize database, check service availability
    - On shutdown: Clean up resources
    """
    settings = get_settings()
    
    # Initialize database
    await init_database()
    
    # Log service status (but NEVER log actual secrets)
    logger.info("=" * 60)
    logger.info("IssueLens starting up")
    logger.info("Environment: %s", settings.app_env)
    logger.info("AI available: %s", settings.is_ai_available)
    logger.info("GitHub authenticated: %s", settings.is_github_authenticated)
    
    if not settings.is_ai_available:
        logger.warning(
            "⚠️  GEMINI_API_KEY not configured. AI features are DISABLED. "
            "Set GEMINI_API_KEY in your .env file to enable AI-powered analysis."
        )
    
    if not settings.is_github_authenticated:
        logger.info(
            "GitHub token not configured. Using unauthenticated access "
            "(60 requests/hour). Set GITHUB_TOKEN in .env for higher limits."
        )
    
    logger.info("=" * 60)
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("IssueLens shutting down")


# Create FastAPI app
app = FastAPI(
    title="IssueTrace",
    description="IssueTrace — AI-powered GitHub Issue Intelligence Platform. Every claim has a trail. Follow the evidence.",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware — allows the frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)


@app.get("/")
async def root(request: Request):
    """Root endpoint — serves app in browser, JSON in API clients."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return {
        "app": "IssueLens",
        "platform": "IssueTrace",
        "tagline": "Every claim has a trail. Follow the evidence.",
        "version": "0.2.0",
        "docs": "/docs",
        "app_url": "/app",
    }


@app.get("/app")
async def serve_app():
    """Explicit endpoint to serve the frontend application."""
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return HTMLResponse("<h1>IssueTrace</h1><p>index.html not found</p>")
