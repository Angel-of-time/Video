import yt_dlp
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional, Any
import json
import os
from urllib.parse import urlparse

class MediaResolver:
    """Main media resolver using yt-dlp and fallbacks"""
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'force_generic_extractor': False,
        }
        
        # Supported sites (yt-dlp supports 1000+)
        self.supported_sites = [
            'youtube.com', 'youtu.be',
            'instagram.com', 'twitter.com', 'x.com',
            'facebook.com', 'fb.watch',
            'tiktok.com',
            'vimeo.com', 'dailymotion.com',
            'reddit.com', 'twitch.tv',
            'soundcloud.com', 'bandcamp.com',
            'pinterest.com', 'tumblr.com',
            # Add more as needed
        ]
        
        # Format preferences
        self.format_priorities = {
            'mp4': ['bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'],
            'mp3': ['bestaudio[ext=m4a]/bestaudio/best'],
            'best': ['best'],
            'worst': ['worst'],
        }
    
    async def resolve(self, url: str, format_preference: Optional[str] = None, 
                     quality_preference: Optional[str] = None) -> Dict[str, Any]:
        """Resolve media URL to formats"""
        # Use async executor for yt-dlp
        loop = asyncio.get_event_loop()
        
        try:
            # Configure yt-dlp options based on preferences
            ydl_opts = self.ydl_opts.copy()
            
            if format_preference and format_preference in self.format_priorities:
                ydl_opts['format'] = self.format_priorities[format_preference][0]
            
            # Extract info using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
            
            if not info:
                # Fallback to generic extraction
                return await self._generic_resolve(url)
            
            # Process formats
            formats = self._process_formats(info)
            
            # Filter by quality if specified
            if quality_preference:
                formats = self._filter_by_quality(formats, quality_preference)
            
            return {
                'id': info.get('id', ''),
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', ''),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'description': info.get('description', '')[:500],
                'formats': formats,
                'extractor': info.get('extractor', 'generic'),
                'webpage_url': info.get('webpage_url', url),
            }
            
        except Exception as e:
            # If yt-dlp fails, try generic resolution
            try:
                return await self._generic_resolve(url)
            except Exception:
                raise Exception(f"Failed to resolve URL: {str(e)}")
    
    def _process_formats(self, info: Dict) -> List[Dict]:
        """Process yt-dlp formats into a cleaner structure"""
        formats = []
        
        # Handle different format structures
        if 'formats' in info:
            format_list = info['formats']
        elif 'entries' in info:
            # Playlist or multiple entries
            format_list = info['entries'][0].get('formats', []) if info['entries'] else []
        else:
            format_list = []
        
        for fmt in format_list:
            if not fmt.get('url'):
                continue
            
            format_info = {
                'format_id': fmt.get('format_id', ''),
                'ext': fmt.get('ext', ''),
                'url': fmt.get('url'),
                'filesize': fmt.get('filesize', 0),
                'quality': self._extract_quality(fmt),
                'resolution': fmt.get('resolution', ''),
                'fps': fmt.get('fps', 0),
                'vcodec': fmt.get('vcodec', ''),
                'acodec': fmt.get('acodec', ''),
                'format_note': fmt.get('format_note', ''),
            }
            
            # Clean up None values
            format_info = {k: v for k, v in format_info.items() if v is not None}
            formats.append(format_info)
        
        # If no formats found, create one from direct URL
        if not formats and info.get('url'):
            formats.append({
                'format_id': 'direct',
                'ext': info.get('ext', 'mp4'),
                'url': info.get('url'),
                'quality': 'best',
                'resolution': 'unknown',
            })
        
        return formats
    
    def _extract_quality(self, fmt: Dict) -> str:
        """Extract quality from format info"""
        if fmt.get('height'):
            return f"{fmt['height']}p"
        elif fmt.get('tbr'):
            return f"{fmt['tbr']}k"
        elif fmt.get('format_note'):
            return fmt['format_note']
        else:
            return 'unknown'
    
    def _filter_by_quality(self, formats: List[Dict], quality: str) -> List[Dict]:
        """Filter formats by quality preference"""
        if not quality:
            return formats
        
        quality = quality.lower().replace('p', '')
        
        try:
            target_height = int(quality)
            # Find closest match
            filtered = []
            for fmt in formats:
                if 'height' in fmt and fmt['height']:
                    filtered.append(fmt)
            
            if filtered:
                # Sort by closest to target quality
                filtered.sort(key=lambda x: abs(x.get('height', 0) - target_height))
                return filtered[:5]  # Return top 5 closest matches
        except ValueError:
            # Not a numeric quality, try string match
            quality_map = {
                'best': lambda f: f.get('quality', '') == 'best' or f.get('format_id', '') == 'best',
                'worst': lambda f: f.get('quality', '') == 'worst' or f.get('format_id', '') == 'worst',
                'audio': lambda f: f.get('acodec') and not f.get('vcodec'),
                'video': lambda f: f.get('vcodec') and not f.get('acodec'),
            }
            
            if quality in quality_map:
                return [f for f in formats if quality_map[quality](f)]
        
        return formats
    
    async def _generic_resolve(self, url: str) -> Dict[str, Any]:
        """Generic fallback resolution for unsupported sites"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch URL: {response.status}")
                
                html = await response.text()
                
        # Try to find video/audio tags
        soup = BeautifulSoup(html, 'html.parser')
        
        formats = []
        
        # Look for video sources
        for video in soup.find_all('video'):
            for source in video.find_all('source'):
                src = source.get('src')
                if src:
                    # Make absolute URL
                    if not src.startswith('http'):
                        src = self._make_absolute_url(url, src)
                    
                    formats.append({
                        'format_id': 'video',
                        'ext': self._get_extension(src),
                        'url': src,
                        'quality': 'unknown',
                        'resolution': source.get('res', ''),
                    })
        
        # Look for audio sources
        for audio in soup.find_all('audio'):
            for source in audio.find_all('source'):
                src = source.get('src')
                if src:
                    if not src.startswith('http'):
                        src = self._make_absolute_url(url, src)
                    
                    formats.append({
                        'format_id': 'audio',
                        'ext': self._get_extension(src),
                        'url': src,
                        'quality': 'unknown',
                    })
        
        # Look for meta tags with og:video/audio
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            prop = tag.get('property', '')
            content = tag.get('content', '')
            
            if prop in ['og:video', 'og:video:url', 'og:audio', 'og:audio:url'] and content:
                if not content.startswith('http'):
                    content = self._make_absolute_url(url, content)
                
                formats.append({
                    'format_id': 'meta_' + prop.replace(':', '_'),
                    'ext': self._get_extension(content),
                    'url': content,
                    'quality': 'unknown',
                })
        
        # Extract title
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.text.strip()
        else:
            # Try og:title
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content', '')
        
        return {
            'id': self._extract_id(url),
            'title': title or os.path.basename(urlparse(url).path),
            'duration': 0,
            'thumbnail': self._extract_thumbnail(soup, url),
            'formats': formats,
            'extractor': 'generic',
            'webpage_url': url,
        }
    
    def _make_absolute_url(self, base_url: str, relative_url: str) -> str:
        """Convert relative URL to absolute"""
        from urllib.parse import urljoin
        return urljoin(base_url, relative_url)
    
    def _get_extension(self, url: str) -> str:
        """Get file extension from URL"""
        path = urlparse(url).path
        ext = os.path.splitext(path)[1].lower().lstrip('.')
        return ext if ext else 'unknown'
    
    def _extract_id(self, url: str) -> str:
        """Extract ID from URL"""
        # Simple hash of URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:8]
    
    def _extract_thumbnail(self, soup, base_url: str) -> str:
        """Extract thumbnail from HTML"""
        # Try og:image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = og_image['content']
            if not img_url.startswith('http'):
                img_url = self._make_absolute_url(base_url, img_url)
            return img_url
        
        # Try first image
        img = soup.find('img')
        if img and img.get('src'):
            img_url = img['src']
            if not img_url.startswith('http'):
                img_url = self._make_absolute_url(base_url, img_url)
            return img_url
        
        return ''
    
    async def get_info(self, url: str) -> Dict[str, Any]:
        """Get info about URL without resolving formats"""
        loop = asyncio.get_event_loop()
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False, process=False))
            
            return {
                'id': info.get('id', ''),
                'title': info.get('title', ''),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', ''),
                'extractor': info.get('extractor', ''),
                'webpage_url': info.get('webpage_url', url),
                'is_live': info.get('is_live', False),
                'categories': info.get('categories', []),
                'tags': info.get('tags', []),
                'description': info.get('description', '')[:200],
            }
        except Exception as e:
            # Return basic info
            return {
                'url': url,
                'domain': urlparse(url).netloc,
                'available': False,
                'error': str(e)
            }
    
    def get_supported_sites(self) -> List[str]:
        """Get list of supported sites"""
        return self.supported_sites
    
    def is_supported(self, url: str) -> bool:
        """Check if URL is from a supported site"""
        domain = urlparse(url).netloc.lower()
        return any(site in domain for site in self.supported_sites)