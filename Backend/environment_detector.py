import os
import shutil
import subprocess
import platform
import psutil
from typing import Dict, Any, Optional
import json

class UniversalEnvironmentDetector:
    """Detect environment capabilities and auto-configure"""
    
    @staticmethod
    def get_capabilities() -> Dict[str, Any]:
        """Get complete environment information"""
        return {
            'system': UniversalEnvironmentDetector._get_system_info(),
            'resources': UniversalEnvironmentDetector._get_resource_info(),
            'features': UniversalEnvironmentDetector._get_feature_info(),
            'storage': UniversalEnvironmentDetector._get_storage_info(),
            'network': UniversalEnvironmentDetector._get_network_info(),
            'config': UniversalEnvironmentDetector._generate_config(),
        }
    
    @staticmethod
    def _get_system_info() -> Dict[str, Any]:
        """Get system information"""
        system_info = {
            'os': platform.system(),
            'os_release': platform.release(),
            'os_version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'docker': os.path.exists('/.dockerenv'),
            'cgroup_v2': UniversalEnvironmentDetector._is_cgroup_v2(),
            'hostname': platform.node(),
        }
        
        # Detect container runtime
        if system_info['docker']:
            system_info['container_runtime'] = 'docker'
        elif os.path.exists('/run/.containerenv'):
            system_info['container_runtime'] = 'podman'
        else:
            system_info['container_runtime'] = 'bare_metal'
        
        return system_info
    
    @staticmethod
    def _is_cgroup_v2() -> bool:
        """Check if using cgroup v2"""
        return os.path.exists('/sys/fs/cgroup/cgroup.controllers')
    
    @staticmethod
    def _get_resource_info() -> Dict[str, Any]:
        """Get resource information"""
        try:
            cpu_count = os.cpu_count() or 1
            
            # Memory info
            memory_info = UniversalEnvironmentDetector._get_memory_info()
            
            # CPU frequency
            try:
                cpu_freq = psutil.cpu_freq()
                cpu_mhz = cpu_freq.current if cpu_freq else None
            except:
                cpu_mhz = None
            
            return {
                'cpu_cores': cpu_count,
                'cpu_mhz': cpu_mhz,
                'memory': memory_info,
                'cgroup': UniversalEnvironmentDetector._get_cgroup_info(),
            }
        except Exception as e:
            return {
                'cpu_cores': 1,
                'error': str(e)
            }
    
    @staticmethod
    def _get_memory_info() -> Dict[str, Any]:
        """Get memory information with cgroup awareness"""
        try:
            # System memory
            sys_mem = psutil.virtual_memory()
            
            # Cgroup memory limit
            cgroup_limit = UniversalEnvironmentDetector._get_cgroup_memory_limit()
            
            # Determine available memory
            if cgroup_limit == 0 or cgroup_limit > sys_mem.total * 10:
                available = sys_mem.total
                unlimited = True
            else:
                available = min(sys_mem.total, cgroup_limit)
                unlimited = False
            
            return {
                'total_bytes': sys_mem.total,
                'available_bytes': available,
                'percent_used': sys_mem.percent,
                'cgroup_limit_bytes': cgroup_limit,
                'unlimited': unlimited,
                'total_mb': sys_mem.total // (1024 * 1024),
                'available_mb': available // (1024 * 1024),
            }
        except Exception as e:
            return {
                'total_mb': 512,
                'available_mb': 512,
                'unlimited': True,
                'error': str(e)
            }
    
    @staticmethod
    def _get_cgroup_memory_limit() -> int:
        """Get cgroup memory limit (0 = unlimited)"""
        limit = 0
        
        # Try cgroup v2
        v2_path = '/sys/fs/cgroup/memory.max'
        if os.path.exists(v2_path):
            try:
                with open(v2_path, 'r') as f:
                    content = f.read().strip()
                    if content == 'max':
                        return 0
                    limit = int(content)
            except:
                pass
        
        # Try cgroup v1
        v1_path = '/sys/fs/cgroup/memory/memory.limit_in_bytes'
        if limit == 0 and os.path.exists(v1_path):
            try:
                with open(v1_path, 'r') as f:
                    limit = int(f.read().strip())
                    # Check for "unlimited" (typically 9223372036854771712)
                    if limit > 10**12:  # > 1TB
                        return 0
            except:
                pass
        
        return limit
    
    @staticmethod
    def _get_cgroup_info() -> Dict[str, Any]:
        """Get cgroup configuration"""
        try:
            info = {
                'version': 2 if UniversalEnvironmentDetector._is_cgroup_v2() else 1,
                'cpu_quota': None,
                'cpu_period': None,
                'cpu_cores_limit': None,
            }
            
            if info['version'] == 2:
                # Cgroup v2
                cpu_max_path = '/sys/fs/cgroup/cpu.max'
                if os.path.exists(cpu_max_path):
                    with open(cpu_max_path, 'r') as f:
                        quota, period = f.read().strip().split()
                        if quota != 'max':
                            info['cpu_quota'] = int(quota)
                            info['cpu_period'] = int(period)
                            if period and int(period) > 0:
                                info['cpu_cores_limit'] = int(quota) / int(period)
            else:
                # Cgroup v1
                quota_path = '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'
                period_path = '/sys/fs/cgroup/cpu/cpu.cfs_period_us'
                if os.path.exists(quota_path) and os.path.exists(period_path):
                    with open(quota_path, 'r') as f:
                        info['cpu_quota'] = int(f.read().strip())
                    with open(period_path, 'r') as f:
                        info['cpu_period'] = int(f.read().strip())
                    
                    if info['cpu_quota'] > 0 and info['cpu_period'] > 0:
                        info['cpu_cores_limit'] = info['cpu_quota'] / info['cpu_period']
            
            return info
        except Exception:
            return {'version': 'unknown'}
    
    @staticmethod
    def _get_feature_info() -> Dict[str, bool]:
        """Detect available features"""
        features = {
            'ffmpeg': UniversalEnvironmentDetector._check_command('ffmpeg -version'),
            'curl': UniversalEnvironmentDetector._check_command('curl --version'),
            'wget': UniversalEnvironmentDetector._check_command('wget --version'),
            'redis': bool(os.environ.get('REDIS_URL')),
            'network': True,
        }
        
        # Check specific ffmpeg codecs
        if features['ffmpeg']:
            try:
                result = subprocess.run(
                    ['ffmpeg', '-codecs'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                output = result.stdout.lower()
                features['ffmpeg_mp4'] = 'mp4' in output or 'h264' in output
                features['ffmpeg_mp3'] = 'mp3' in output or 'libmp3lame' in output
            except:
                features['ffmpeg_mp4'] = False
                features['ffmpeg_mp3'] = False
        
        return features
    
    @staticmethod
    def _check_command(cmd: str) -> bool:
        """Check if a command is available"""
        try:
            subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=1
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    @staticmethod
    def _get_storage_info() -> Dict[str, Any]:
        """Get storage information"""
        try:
            # System storage
            sys_disk = psutil.disk_usage('/')
            
            # App storage (if different)
            app_disk = psutil.disk_usage('/app') if os.path.exists('/app') else sys_disk
            
            return {
                'system': {
                    'total_bytes': sys_disk.total,
                    'used_bytes': sys_disk.used,
                    'free_bytes': sys_disk.free,
                    'percent_used': sys_disk.percent,
                    'total_gb': sys_disk.total // (1024**3),
                    'free_gb': sys_disk.free // (1024**3),
                },
                'app': {
                    'total_bytes': app_disk.total,
                    'used_bytes': app_disk.used,
                    'free_bytes': app_disk.free,
                    'percent_used': app_disk.percent,
                    'total_gb': app_disk.total // (1024**3),
                    'free_gb': app_disk.free // (1024**3),
                },
                'writable': os.access('/app/data', os.W_OK) if os.path.exists('/app/data') else False,
            }
        except Exception as e:
            return {
                'system': {'total_gb': 0, 'free_gb': 0},
                'app': {'total_gb': 0, 'free_gb': 0},
                'writable': False,
                'error': str(e)
            }
    
    @staticmethod
    def _get_network_info() -> Dict[str, Any]:
        """Get network information"""
        try:
            net_info = {
                'hostname': platform.node(),
                'interfaces': {},
            }
            
            # Get network interfaces
            addrs = psutil.net_if_addrs()
            for interface, addresses in addrs.items():
                net_info['interfaces'][interface] = [
                    {
                        'family': str(addr.family),
                        'address': addr.address,
                        'netmask': addr.netmask,
                    }
                    for addr in addresses
                ]
            
            return net_info
        except Exception:
            return {'hostname': platform.node()}
    
    @staticmethod
    def _generate_config() -> Dict[str, Any]:
        """Generate optimal configuration based on environment"""
        # Get resource info
        resources = UniversalEnvironmentDetector._get_resource_info()
        memory_mb = resources.get('memory', {}).get('available_mb', 512)
        cpu_cores = resources.get('cpu_cores', 1)
        
        # Determine optimal workers
        if memory_mb >= 2048:  # 2GB+
            workers = min(8, cpu_cores * 2)
        elif memory_mb >= 1024:  # 1GB+
            workers = min(4, cpu_cores)
        elif memory_mb >= 512:  # 512MB
            workers = min(2, cpu_cores)
        else:  # < 512MB
            workers = 1
        
        # Adjust based on cgroup CPU limits
        cgroup_cores = resources.get('cgroup', {}).get('cpu_cores_limit')
        if cgroup_cores:
            workers = min(workers, int(cgroup_cores))
        
        workers = max(1, workers)
        
        # Determine timeout based on network
        timeout = 30
        keepalive = 5
        
        # Get storage info
        storage = UniversalEnvironmentDetector._get_storage_info()
        free_gb = storage.get('app', {}).get('free_gb', 0)
        
        # Determine max file size
        if free_gb > 50:  # > 50GB free
            max_file_size_mb = 2000
        elif free_gb > 10:  # > 10GB free
            max_file_size_mb = 1000
        elif free_gb > 1:  # > 1GB free
            max_file_size_mb = 500
        else:  # < 1GB free
            max_file_size_mb = 100
        
        return {
            'server': {
                'workers': workers,
                'timeout': timeout,
                'keepalive': keepalive,
                'max_requests': 1000,
                'max_requests_jitter': 50,
            },
            'features': {
                'enable_conversion': UniversalEnvironmentDetector._check_command('ffmpeg -version'),
                'enable_cache': bool(os.environ.get('REDIS_URL')),
                'max_file_size_mb': max_file_size_mb,
                'cache_ttl_seconds': 3600,
            },
            'limits': {
                'rate_per_minute': 60,
                'rate_per_hour': 1000,
                'max_duration_seconds': 3600,
                'max_concurrent_downloads': workers * 2,
            },
            'security': {
                'token_expire_minutes': int(os.environ.get('TOKEN_EXPIRE_MINUTES', '30')),
                'cors_origins': os.environ.get('CORS_ORIGINS', '*').split(','),
                'require_https': os.environ.get('REQUIRE_HTTPS', 'false').lower() == 'true',
            },
        }
    
    @staticmethod
    def get_recommendations() -> Dict[str, Any]:
        """Get environment-specific recommendations"""
        caps = UniversalEnvironmentDetector.get_capabilities()
        config = caps['config']
        features = caps['features']
        
        recommendations = []
        warnings = []
        
        # Check memory
        memory_mb = caps['resources']['memory']['available_mb']
        if memory_mb < 256:
            warnings.append(f"Low memory ({memory_mb}MB). Consider increasing to at least 512MB.")
        
        # Check storage
        free_gb = caps['storage']['app']['free_gb']
        if free_gb < 1:
            warnings.append(f"Low disk space ({free_gb}GB free). Media caching may be limited.")
        
        # Check FFmpeg
        if not features['ffmpeg']:
            recommendations.append("Install FFmpeg for media conversion capabilities.")
        
        # Check Redis
        if not features['redis']:
            recommendations.append("Configure Redis for better caching and rate limiting.")
        
        return {
            'workers': config['server']['workers'],
            'max_file_size_mb': config['features']['max_file_size_mb'],
            'recommendations': recommendations,
            'warnings': warnings,
        }