import os
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class FileCache:
    """Simple file-based cache for processed documents to avoid reprocessing."""
    
    def __init__(self, cache_dir: str = "cache", ttl_hours: int = 24):
        """
        Initialize the file cache.
        
        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time-to-live for cache entries in hours
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        
    def _get_file_hash(self, file_path: str) -> str:
        """Generate MD5 hash of file contents."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error generating hash for {file_path}: {e}")
            return ""
    
    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key based on file path and hash."""
        file_hash = self._get_file_hash(file_path)
        filename = Path(file_path).name
        return f"{filename}_{file_hash}"
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the full path to cache file."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _is_cache_valid(self, cache_file_path: Path) -> bool:
        """Check if cache file exists and is not expired."""
        if not cache_file_path.exists():
            return False
        
        file_age = time.time() - cache_file_path.stat().st_mtime
        return file_age < self.ttl_seconds
    
    def get(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get cached result for a file.
        
        Args:
            file_path: Path to the original file
            
        Returns:
            Cached result or None if not found/invalid
        """
        cache_key = self._get_cache_key(file_path)
        cache_file_path = self._get_cache_file_path(cache_key)
        
        if not self._is_cache_valid(cache_file_path):
            return None
        
        try:
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            logger.info(f"✅ Cache hit for {Path(file_path).name}")
            return cached_data
            
        except Exception as e:
            logger.error(f"Error reading cache file {cache_file_path}: {e}")
            # Try to delete corrupted cache file
            try:
                cache_file_path.unlink()
            except:
                pass
            return None
    
    def set(self, file_path: str, data: Dict[str, Any]) -> bool:
        """
        Cache result for a file.
        
        Args:
            file_path: Path to the original file
            data: Result data to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = self._get_cache_key(file_path)
        cache_file_path = self._get_cache_file_path(cache_key)
        
        try:
            # Add metadata to cached data
            cache_data = {
                "timestamp": time.time(),
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "result": data
            }
            
            with open(cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Cached result for {Path(file_path).name}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing cache file {cache_file_path}: {e}")
            return False
    
    def invalidate(self, file_path: str) -> bool:
        """
        Invalidate cache for a specific file.
        
        Args:
            file_path: Path to the original file
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        cache_key = self._get_cache_key(file_path)
        cache_file_path = self._get_cache_file_path(cache_key)
        
        try:
            if cache_file_path.exists():
                cache_file_path.unlink()
                logger.info(f"🗑️ Invalidated cache for {Path(file_path).name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error invalidating cache for {file_path}: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired cache files.
        
        Returns:
            Number of files cleaned up
        """
        cleaned_count = 0
        current_time = time.time()
        
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                file_age = current_time - cache_file.stat().st_mtime
                if file_age > self.ttl_seconds:
                    cache_file.unlink()
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"🧹 Cleaned up {cleaned_count} expired cache files")
                
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
        
        return cleaned_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            current_time = time.time()
            expired_count = sum(
                1 for f in cache_files 
                if (current_time - f.stat().st_mtime) > self.ttl_seconds
            )
            
            return {
                "cache_dir": str(self.cache_dir),
                "total_files": len(cache_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "expired_files": expired_count,
                "ttl_hours": self.ttl_seconds / 3600
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}

# Global cache instance
_cache_instance = None

def get_cache() -> FileCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = FileCache()
    return _cache_instance
