import os
import time
import json
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
import aiohttp
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse, StreamingResponse
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
    print("🚀 Starting Central Moon v2.3")
    env_info = env_detector.get_capabilities()
    print(f"📊 Environment: {json.dumps(env_info, indent=2, default=str)}")
    app.state.environment_info = env_info
    yield
    print("👋 Shutting down...")

app = FastAPI(title="Central Moon", version="2.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTES ---

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.3.0"}

@app.post("/resolve")
async def resolve_url(
    request: Request,
    url: str = Query(..., description="Media URL"),
):
    try:
        # 1. Get Media Info
        media_info = await resolver.resolve(url)
        
        # 2. Sign Links (Store Title inside token for filename)
        signed_links = []
        # Clean title for filename
        raw_title = media_info.get("title", "download")
        safe_title = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()[:50]
        
        for fmt in media_info.get("formats", []):
            download_url = fmt.get("url")
            if download_url:
                # Add metadata to token
                meta = {
                    't': safe_title,
                    'e': fmt.get('ext', 'mp4')
                }
                token = signer.sign_url(download_url, metadata=meta)
                
                fmt["download_token"] = token
                fmt["download_url"] = f"/download/{token}"
                signed_links.append(fmt)
        
        return {
            "success": True,
            "data": {
                **media_info,
                "formats": signed_links
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download/{token}")
async def download_media(token: str):
    """
    PROXY STREAM: The server downloads the file and passes it to the user.
    This fixes the '403 Forbidden' error on TikTok/Instagram.
    """
    try:
        # 1. Verify Token
        token_info = signer.get_token_info(token)
        if not token_info['valid']:
            raise HTTPException(status_code=403, detail="Link expired")
        
        target_url = token_info['url']
        meta = token_info.get('metadata', {})
        
        # Build Filename: "My Video Title.mp4"
        filename = f"{meta.get('t', 'video')}.{meta.get('e', 'mp4')}"
        encoded_filename = quote(filename)

        # 2. Stream the file
        async def iterfile():
            async with aiohttp.ClientSession() as session:
                # User-Agent is critical for TikTok
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.tiktok.com/'
                }
                async with session.get(target_url, headers=headers) as resp:
                    if resp.status >= 400:
                        yield b"" # Stop if error
                        return
                    
                    async for chunk in resp.content.iter_chunked(1024 * 1024): # 1MB chunks
                        yield chunk

        # 3. Return as Attachment (Forces browser to show download dialog)
        return StreamingResponse(
            iterfile(), 
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"
            }
        )

    except Exception as e:
        print(f"Download Error: {e}")
        raise HTTPException(status_code=400, detail="Download failed")

# --- FRONTEND ---
frontend_path = "/app/frontend" if os.path.exists("/app/frontend") else "frontend"
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))
