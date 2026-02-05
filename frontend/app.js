class CentralMoonApp {
    constructor() {
        this.apiUrl = window.location.origin;
        this.init();
    }
    
    init() {
        const urlInput = document.getElementById('urlInput');
        const resolveBtn = document.getElementById('resolveBtn');

        // Click Event
        resolveBtn.addEventListener('click', () => this.resolve());

        // Enter Key Event
        urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.resolve();
        });

        console.log("🌑 Central Moon Loaded - By Frdinkoi");
    }
    
    async resolve() {
        const urlInput = document.getElementById('urlInput');
        const url = urlInput.value.trim();
        
        if (!url) return this.showError('Please paste a link first.');

        this.setLoading(true);
        this.hideError();
        document.getElementById('results').classList.add('d-none');

        try {
            // THE FIX: Correct POST request with JSON headers
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
            this.showError(error.message || "Failed to connect to Central Moon server.");
        } finally {
            this.setLoading(false);
        }
    }
    
    renderResults(data) {
        // 1. Fill Info
        document.getElementById('title').textContent = data.title || 'Unknown Title';
        document.getElementById('thumbnail').src = data.thumbnail || '';
        document.getElementById('uploader').querySelector('span').textContent = data.uploader || 'Unknown';
        document.getElementById('description').textContent = data.description || '';
        
        // 2. Clear & Fill Formats
        const list = document.getElementById('formatsList');
        const template = document.getElementById('formatTemplate');
        list.innerHTML = '';

        const formats = data.formats || [];
        if (formats.length === 0) list.innerHTML = '<div class="text-center text-muted">No download links found.</div>';

        formats.forEach(fmt => {
            const clone = template.content.cloneNode(true);
            
            // Badge (MP4/MP3)
            clone.querySelector('.format-badge').textContent = (fmt.ext || 'FILE').toUpperCase();
            
            // Name (1080p, etc)
            let quality = fmt.quality || fmt.resolution || 'Standard';
            if (fmt.fps && fmt.fps > 30) quality += ` ${fmt.fps}fps`;
            clone.querySelector('.format-name').textContent = quality;

            // Size
            const sizeMB = fmt.filesize ? (fmt.filesize / 1024 / 1024).toFixed(1) + ' MB' : '';
            clone.querySelector('.format-size').textContent = sizeMB;

            // Buttons
            const downloadUrl = fmt.download_url.startsWith('http') ? fmt.download_url : this.apiUrl + fmt.download_url;
            clone.querySelector('.download-btn').href = downloadUrl;
            
            clone.querySelector('.copy-btn').addEventListener('click', () => {
                navigator.clipboard.writeText(downloadUrl);
                alert('Link copied to clipboard!');
            });

            list.appendChild(clone);
        });

        // 3. Show Results
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
        const errEl = document.getElementById('error');
        document.getElementById('errorText').textContent = msg;
        errEl.classList.remove('d-none');
    }
    
    hideError() {
        document.getElementById('error').classList.add('d-none');
    }
}

// Start
document.addEventListener('DOMContentLoaded', () => new CentralMoonApp());
