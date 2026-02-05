import os
import time
import json
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from media_resolver import MediaResolver
from link_signer import LinkSigner
from environment_detector import UniversalEnvironmentDetector
import config

# Initialize components
resolver = MediaResolver()
signer = LinkSigner()
env_detector = UniversalEnvironmentDetector()

# Track startup time
startup_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the app"""
    # Startup
    print("🚀 Starting Universal Media Resolver v2.1")
    env_info = env_detector.get_capabilities()
    print(f"📊 Environment: {json.dumps(env_info, indent=2, default=str)}")
    
    # Store environment info
    app.state.environment_info = env_info
    
    yield
    
    # Shutdown
    print("👋 Shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Universal Media Resolver",
    description="Resolve media URLs from 1000+ sites",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting store (simple in-memory for now)
request_timestamps = {}

def rate_limit_check(request: Request, limit_per_minute: int = 60):
    """Simple rate limiting"""
    client_ip = request.client.host
    now = time.time()
    
    # Clean old timestamps
    if client_ip in request_timestamps:
        request_timestamps[client_ip] = [
            ts for ts in request_timestamps[client_ip] 
            if now - ts < 60
        ]
    
    # Check limit
    if len(request_timestamps.get(client_ip, [])) >= limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Add timestamp
    if client_ip not in request_timestamps:
        request_timestamps[client_ip] = []
    request_timestamps[client_ip].append(now)

# --- API ROUTES ---

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    uptime = time.time() - startup_time
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "uptime_seconds": uptime,
        "version": "2.1.0"
    }

@app.get("/environment")
async def environment_info():
    """Get environment information"""
    return app.state.environment_info

@app.post("/resolve")
async def resolve_url(
    request: Request,
    url: str = Query(..., description="Media URL to resolve"),
    format: Optional[str] = Query(None, description="Preferred format (mp4, mp3, best, worst)"),
    quality: Optional[str] = Query(None, description="Preferred quality (1080p, 720p, 480p)")
):
    """Resolve a media URL to direct download links"""
    # Rate limiting
    rate_limit_check(request)
    
    try:
        # Resolve media info
        media_info = await resolver.resolve(url, format_preference=format, quality_preference=quality)
        
        # Generate signed download tokens for each format
        signed_links = []
        for fmt in media_info.get("formats", []):
            download_url = fmt.get("url")
            if download_url:
                token = signer.sign_url(download_url)
                fmt["download_token"] = token
                fmt["download_url"] = f"/download/{token}"
                signed_links.append(fmt)
        
        return {
            "success": True,
            "data": {
                "id": media_info.get("id"),
                "title": media_info.get("title"),
                "duration": media_info.get("duration"),
                "thumbnail": media_info.get("thumbnail"),
                "formats": signed_links,
                "resolved_at": time.time()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download/{token}")
async def download_media(token: str):
    """Redirect to actual media URL with signed token"""
    try:
        # Verify and decode token
        url = signer.verify_token(token)
        if not url:
            raise HTTPException(status_code=404, detail="Invalid or expired token")
        
        # Redirect to actual media URL
        return RedirectResponse(url, status_code=302)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/info")
async def get_info(
    request: Request,
    url: str = Query(..., description="URL to get info about")
):
    """Get information about a URL without downloading"""
    rate_limit_check(request, limit_per_minute=30)
    
    try:
        info = await resolver.get_info(url)
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/supported")
async def get_supported_sites():
    """Get list of supported sites"""
    return {
        "success": True,
        "data": {
            "sites": resolver.get_supported_sites(),
            "count": len(resolver.get_supported_sites())
        }
    }

# --- ERROR HANDLERS ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )

# --- FRONTEND SERVING LOGIC ---

# Check if the frontend directory exists (Docker path vs Local path)
# We prefer "/app/frontend" (Docker) but fallback to "frontend" (Local)
frontend_path = "/app/frontend" if os.path.exists("/app/frontend") else "frontend"

if os.path.exists(frontend_path):
    print(f"✅ Frontend found at: {frontend_path}")
    
    # 1. Mount assets to "/static" (CSS, JS, Images)
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    # 2. Serve index.html at the root "/"
    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))

else:
    print("⚠️  Frontend folder not found. Serving API JSON at root.")
    
    # Fallback: If no frontend, show the API status JSON
    @app.get("/")
    async def root():
        # DEBUG: List all files in the current directory to see what went wrong
        current_files = os.listdir(".")
        
        return {
            "service": "Universal Media Resolver",
            "status": "operational",
            "error": "Frontend folder missing",
            "debug_current_path": os.getcwd(),
            "debug_files_found": current_files,  # <--- THIS WILL SHOW US THE TRUTH
            "note": "Check if 'frontend' is in your .dockerignore file"
        }
