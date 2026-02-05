// Universal Media Resolver Frontend
class MediaResolverApp {
    constructor() {
        this.apiUrl = window.location.origin;
        this.elements = {
            urlInput: document.getElementById('urlInput'),
            resolveBtn: document.getElementById('resolveBtn'),
            loading: document.getElementById('loading'),
            results: document.getElementById('results'),
            error: document.getElementById('error'),
            errorText: document.getElementById('errorText'),
            title: document.getElementById('title'),
            thumbnail: document.getElementById('thumbnail'),
            duration: document.getElementById('duration'),
            uploader: document.getElementById('uploader'),
            views: document.getElementById('views'),
            description: document.getElementById('description'),
            formatsList: document.getElementById('formatsList'),
            formatTemplate: document.getElementById('formatTemplate')
        };
        
        this.init();
    }
    
    init() {
        // Event listeners
        this.elements.resolveBtn.addEventListener('click', () => this.resolveUrl());
        this.elements.urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.resolveUrl();
        });
        
        // Check for URL in clipboard
        this.checkClipboard();
        
        // Show API status
        this.checkApiStatus();
    }
    
    async checkApiStatus() {
        try {
            const response = await fetch(`${this.apiUrl}/health`);
            if (response.ok) {
                console.log('✅ API is running');
            }
        } catch (error) {
            console.warn('⚠️ API check failed:', error.message);
        }
    }
    
    async checkClipboard() {
        try {
            const text = await navigator.clipboard.readText();
            if (text.match(/https?:\/\//)) {
                this.elements.urlInput.value = text;
                this.elements.urlInput.focus();
                this.showToast('📋 URL pasted from clipboard');
            }
        } catch (error) {
            // Clipboard access not granted or not available
        }
    }
    
    async resolveUrl() {
        const url = this.elements.urlInput.value.trim();
        
        if (!url) {
            this.showError('Please enter a URL');
            return;
        }
        
        if (!this.isValidUrl(url)) {
            this.showError('Please enter a valid URL (starting with http:// or https://)');
            return;
        }
        
        // Reset UI
        this.hideError();
        this.hideResults();
        this.showLoading();
        
        try {
            // Call API
                    try {
            // Call API
            // NEW (Fixed - sends POST)
            const response = await fetch(`${this.apiUrl}/resolve?url=${encodeURIComponent(url)}`, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json'
                }
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to resolve URL');
            }
            
            if (!data.success) {
                throw new Error(data.error || 'Unknown error');
            }
            
            // Display results
            this.displayResults(data.data);
            
        } catch (error) {
            this.showError(error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    displayResults(data) {
        // Set media info
        this.elements.title.textContent = data.title || 'Untitled';
        this.elements.thumbnail.src = data.thumbnail || 'https://via.placeholder.com/320x180?text=No+Thumbnail';
        this.elements.thumbnail.onerror = () => {
            this.elements.thumbnail.src = 'https://via.placeholder.com/320x180?text=Thumbnail+Error';
        };
        
        // Format duration
        if (data.duration) {
            const hours = Math.floor(data.duration / 3600);
            const minutes = Math.floor((data.duration % 3600) / 60);
            const seconds = data.duration % 60;
            
            if (hours > 0) {
                this.elements.duration.textContent = `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            } else {
                this.elements.duration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
        } else {
            this.elements.duration.textContent = 'Unknown';
        }
        
        // Other info
        this.elements.uploader.textContent = data.uploader ? `by ${data.uploader}` : '';
        this.elements.views.textContent = data.view_count ? `${this.formatNumber(data.view_count)} views` : '';
        this.elements.description.textContent = data.description || '';
        
        // Display formats
        this.displayFormats(data.formats);
        
        // Show results
        this.elements.results.classList.remove('d-none');
        
        // Scroll to results
        this.elements.results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    displayFormats(formats) {
        this.elements.formatsList.innerHTML = '';
        
        if (!formats || formats.length === 0) {
            this.elements.formatsList.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    No downloadable formats found for this URL.
                </div>
            `;
            return;
        }
        
        // Sort formats by quality
        formats.sort((a, b) => {
            const qualityA = this.parseQuality(a.quality);
            const qualityB = this.parseQuality(b.quality);
            return qualityB - qualityA; // Descending
        });
        
        formats.forEach(format => {
            const template = this.elements.formatTemplate.content.cloneNode(true);
            const item = template.querySelector('.list-group-item');
            
            // Format badge
            const badge = item.querySelector('.format-badge');
            badge.textContent = format.ext.toUpperCase() || 'UNK';
            
            // Format name
            const name = item.querySelector('.format-name');
            let qualityText = format.quality || 'Best';
            if (format.resolution) qualityText = format.resolution;
            if (format.fps) qualityText += ` ${format.fps}fps`;
            
            name.textContent = qualityText;
            
            // Format size
            const size = item.querySelector('.format-size');
            if (format.filesize) {
                size.textContent = `(${this.formatFileSize(format.filesize)})`;
            } else {
                size.textContent = '';
            }
            
            // Copy button
            const copyBtn = item.querySelector('.copy-btn');
            copyBtn.addEventListener('click', () => {
                this.copyToClipboard(format.download_url);
            });
            
            // Download button
            const downloadBtn = item.querySelector('.download-btn');
            downloadBtn.href = `${this.apiUrl}${format.download_url}`;
            downloadBtn.download = `${data.title || 'download'}.${format.ext}`;
            
            // Add download tracking
            downloadBtn.addEventListener('click', () => {
                this.trackDownload(format);
            });
            
            this.elements.formatsList.appendChild(item);
        });
    }
    
    parseQuality(quality) {
        if (!quality) return 0;
        const match = quality.match(/(\d+)p/);
        return match ? parseInt(match[1]) : 0;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(`${this.apiUrl}${text}`);
            this.showToast('📋 Link copied to clipboard!');
        } catch (error) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = `${this.apiUrl}${text}`;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showToast('📋 Link copied to clipboard!');
        }
    }
    
    trackDownload(format) {
        console.log('Download started:', format);
        // You can add analytics here
    }
    
    showLoading() {
        this.elements.loading.classList.remove('d-none');
        this.elements.resolveBtn.disabled = true;
    }
    
    hideLoading() {
        this.elements.loading.classList.add('d-none');
        this.elements.resolveBtn.disabled = false;
    }
    
    showError(message) {
        this.elements.errorText.textContent = message;
        this.elements.error.classList.remove('d-none');
    }
    
    hideError() {
        this.elements.error.classList.add('d-none');
    }
    
    hideResults() {
        this.elements.results.classList.add('d-none');
    }
    
    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }
    
    showToast(message, duration = 3000) {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = 'toast-alert';
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-check-circle"></i>
                <span>${message}</span>
            </div>
        `;
        
        // Style
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--primary-color);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            z-index: 9999;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        // Add animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
        
        // Remove after duration
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(toast);
                document.head.removeChild(style);
            }, 300);
        }, duration);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const app = new MediaResolverApp();
    
    // Add some example URLs for testing
    const examples = [
        'https://youtu.be/dQw4w9WgXcQ',
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://vimeo.com/148751763',
        'https://soundcloud.com/...',
        'https://www.tiktok.com/@.../video/...'
    ];
    
    // Add example button
    const exampleBtn = document.createElement('button');
    exampleBtn.className = 'btn btn-outline-secondary btn-sm mt-2';
    exampleBtn.innerHTML = '<i class="fas fa-magic"></i> Try Example URL';
    exampleBtn.addEventListener('click', () => {
        const randomUrl = examples[Math.floor(Math.random() * examples.length)];
        document.getElementById('urlInput').value = randomUrl;
        app.showToast('🎯 Example URL loaded! Click "Resolve" to test.');
    });
    
    document.querySelector('.form-text').appendChild(document.createElement('br'));
    document.querySelector('.form-text').appendChild(exampleBtn);
});
