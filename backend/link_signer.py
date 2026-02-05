import jwt
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
import hashlib

class LinkSigner:
    """Sign and verify download URLs with JWT tokens"""
    
    def __init__(self):
        self.secret_key = os.environ.get('JWT_SECRET', 'default-secret-change-me')
        self.token_expire_minutes = int(os.environ.get('TOKEN_EXPIRE_MINUTES', '30'))
        
        # Algorithm to use
        self.algorithm = 'HS256'
        
        # Cache for recently verified tokens (prevent replay attacks)
        self.verified_cache = set()
        self.cache_max_size = 1000
        self.cache_ttl = 60  # seconds
    
    def sign_url(self, url: str, metadata: Optional[Dict] = None) -> str:
        """Create a signed token for a URL"""
        # Current time
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.token_expire_minutes)
        
        # Create payload
        payload = {
            'url': url,
            'exp': expire,
            'iat': now,
            'nbf': now,
            'jti': self._generate_token_id(url),
            'metadata': metadata or {},
        }
        
        # Sign token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str) -> Optional[str]:
        """Verify a token and return the URL if valid"""
        # Check cache first (prevent replay attacks)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        try:
            # Decode token
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={
                    'require_exp': True,
                    'verify_exp': True,
                    'require_iat': True,
                    'verify_iat': True,
                    'require_nbf': True,
                    'verify_nbf': True,
                }
            )
            
            # Check if token was already used
            if token_hash in self.verified_cache:
                return None
            
            # Add to cache
            self._add_to_cache(token_hash)
            
            # Return URL
            return payload.get('url')
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode token without verification (for debugging)"""
        try:
            return jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={'verify_signature': False}
            )
        except Exception:
            return None
    
    def _generate_token_id(self, url: str) -> str:
        """Generate unique token ID"""
        timestamp = str(int(time.time() * 1000))
        data = f"{url}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _add_to_cache(self, token_hash: str):
        """Add token hash to cache"""
        self.verified_cache.add(token_hash)
        
        # Limit cache size
        if len(self.verified_cache) > self.cache_max_size:
            # Remove oldest (convert to list and slice)
            cache_list = list(self.verified_cache)
            self.verified_cache = set(cache_list[-self.cache_max_size:])
    
    def is_valid_url(self, url: str) -> bool:
        """Check if URL looks valid"""
        import re
        # Basic URL validation
        url_pattern = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return re.match(url_pattern, url) is not None
    
    def create_download_url(self, token: str) -> str:
        """Create download URL from token"""
        return f"/download/{token}"
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """Get information about a token"""
        decoded = self.decode_token(token)
        if not decoded:
            return {'valid': False, 'error': 'Invalid token'}
        
        # Check if expired
        exp_timestamp = decoded.get('exp', 0)
        is_expired = exp_timestamp < time.time()
        
        return {
            'valid': not is_expired,
            'expired': is_expired,
            'expires_at': datetime.fromtimestamp(exp_timestamp).isoformat() if exp_timestamp else None,
            'issued_at': datetime.fromtimestamp(decoded.get('iat', 0)).isoformat() if decoded.get('iat') else None,
            'url': decoded.get('url', ''),
            'metadata': decoded.get('metadata', {}),
            'token_id': decoded.get('jti', ''),
        }