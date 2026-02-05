class CentralMoonApp {
    constructor() {
        this.apiUrl = window.location.origin;
        this.init();
    }
    
    init() {
        const urlInput = document.getElementById('urlInput');
        const resolveBtn = document.getElementById('resolveBtn');
        resolveBtn.addEventListener('click', () => this.resolve());
        urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.resolve();
        });
        this.checkClipboard();
        console.log("🌑 Central Moon v2.3 Loaded");
    }

    async checkClipboard() {
        try {
            const text = await navigator.clipboard.readText();
            if (text.startsWith('http')) {
                // Optional: Auto-paste logic
                // document.getElementById('urlInput').value = text;
            }
        } catch (e) {}
    }
    
    async resolve() {
        const urlInput = document.getElementById('urlInput');
        const url = urlInput.value.trim();
        
        if (!url) return this.showError('Please paste a link first.');

        this.setLoading(true);
        this.hideError();
        document.getElementById('results').classList.add('d-none');

        try {
            // POST Request
            const response = await fetch(`${this.apiUrl}/resolve?url=${encodeURIComponent(url)}`, {
                method: 'POST',
                headers: { 'Accept': 'application/json' }
            });

            const data = await response.json();
            
            if (!response.ok) throw new Error(data.detail || 'Server error');
            if (data.success === false) throw new Error(data.error || 'Failed to resolve');

            this.renderResults(data.data || data);

        } catch (error) {
            console.error(error);
            const msg = error.message === 'Method Not Allowed' ? 'Please refresh the page (Update Required)' : error.message;
            this.showError(msg);
        } finally {
            this.setLoading(false);
        }
    }
    
    renderResults(data) {
        // 1. Info
        document.getElementById('title').textContent = data.title || 'Unknown Title';
        document.getElementById('thumbnail').src = data.thumbnail || '';
        const uploader = data.uploader || 'Unknown';
        document.getElementById('uploader').innerHTML = `<i class="fas fa-user me-2"></i>${uploader}`;
        document.getElementById('description').textContent = data.description || '';
        
        // 2. Clear List
        const list = document.getElementById('formatsList');
        const template = document.getElementById('formatTemplate');
        list.innerHTML = '';

        const formats = data.formats || [];
        if (formats.length === 0) {
            list.innerHTML = '<div class="text-center text-muted">No download links found.</div>';
            document.getElementById('results').classList.remove('d-none');
            return;
        }

        // 3. Helper to create row
        const addFormat = (fmt, isAudio) => {
            const clone = template.content.cloneNode(true);
            const badge = clone.querySelector('.format-badge');
            
            // Badge Style
            if (isAudio) {
                badge.textContent = "MP3 / AUDIO";
                badge.className = 'format-badge badge bg-warning text-dark me-3';
            } else {
                badge.textContent = (fmt.ext || 'MP4').toUpperCase();
                badge.className = 'format-badge badge bg-primary me-3';
            }
            
            // Name/Quality
            let quality = fmt.quality || fmt.resolution || 'Standard';
            if (!isAudio && fmt.fps > 30) quality += ` ${fmt.fps}fps`;
            if (isAudio) quality = "High Quality Audio";
            clone.querySelector('.format-name').textContent = quality;

            // Size
            const sizeMB = fmt.filesize ? (fmt.filesize / 1024 / 1024).toFixed(1) + ' MB' : '';
            clone.querySelector('.format-size').textContent = sizeMB;

            // Link Logic
            const downloadUrl = fmt.download_url.startsWith('http') ? fmt.download_url : this.apiUrl + fmt.download_url;
            
            const dlBtn = clone.querySelector('.download-btn');
            dlBtn.href = downloadUrl;
            dlBtn.removeAttribute('target'); // Force download on same page
            
            clone.querySelector('.copy-btn').addEventListener('click', () => {
                navigator.clipboard.writeText(downloadUrl);
                alert('Link copied!');
            });

            list.appendChild(clone);
        };

        // 4. Split Audio & Video
        const audioOnly = formats.filter(f => f.vcodec === 'none' || f.acodec !== 'none' && f.vcodec === 'none');
        const videoOnly = formats.filter(f => f.vcodec !== 'none');

        // Render Video
        if (videoOnly.length > 0) {
            const h = document.createElement('div');
            h.className = "text-muted small fw-bold text-uppercase mt-2 mb-2 ps-2";
            h.innerText = "Video";
            list.appendChild(h);
            // Sort by quality (height) descending
            videoOnly.sort((a,b) => (b.height || 0) - (a.height || 0));
            videoOnly.forEach(f => addFormat(f, false));
        }

        // Render Audio
        if (audioOnly.length > 0) {
            const h = document.createElement('div');
            h.className = "text-muted small fw-bold text-uppercase mt-4 mb-2 ps-2";
            h.innerText = "Audio";
            list.appendChild(h);
            // Pick best audio
            addFormat(audioOnly[0], true); 
        }

        document.getElementById('results').classList.remove('d-none');
    }
    
    setLoading(isLoading) {
        const loader = document.getElementById('loading');
        const btn = document.getElementById('resolveBtn');
        if(isLoading) {
            loader.classList.remove('d-none');
            btn.disabled = true;
        } else {
            loader.classList.add('d-none');
            btn.disabled = false;
        }
    }
    
    showError(msg) {
        document.getElementById('errorText').textContent = msg;
        document.getElementById('error').classList.remove('d-none');
    }
    
    hideError() {
        document.getElementById('error').classList.add('d-none');
    }
}

document.addEventListener('DOMContentLoaded', () => new CentralMoonApp());
