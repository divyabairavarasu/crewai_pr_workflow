"""
Disk-based caching for review results.
Reduces redundant API calls for similar code patterns.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

try:
    from diskcache import Cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


class ReviewCache:
    """
    Cache for review results to avoid redundant LLM calls.
    
    Uses content hashing to identify similar code patterns.
    """
    
    def __init__(
        self,
        cache_dir: str = ".cache/pr_review",
        ttl: int = 3600,
        enabled: bool = True,
    ):
        """
        Initialize the cache.
        
        Args:
            cache_dir: Directory for cache storage
            ttl: Time-to-live in seconds (default: 1 hour)
            enabled: Whether caching is enabled
        """
        self.enabled = enabled and CACHE_AVAILABLE
        self.ttl = ttl
        self.cache_dir = cache_dir
        self._cache: Optional[Cache] = None
        
        if self.enabled:
            os.makedirs(cache_dir, exist_ok=True)
            self._cache = Cache(cache_dir)
    
    def _hash_content(self, content: str, context: str = "") -> str:
        """Generate a hash for content with optional context."""
        combined = f"{context}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def get(self, content: str, review_type: str) -> Optional[dict]:
        """
        Get cached review result.
        
        Args:
            content: The code content being reviewed
            review_type: Type of review (performance/security/coverage)
            
        Returns:
            Cached result dict or None if not found
        """
        if not self.enabled or not self._cache:
            return None
        
        key = self._hash_content(content, review_type)
        
        try:
            result = self._cache.get(key)
            if result:
                return json.loads(result)
        except Exception:
            pass
        
        return None
    
    def set(self, content: str, review_type: str, result: dict) -> bool:
        """
        Cache a review result.
        
        Args:
            content: The code content that was reviewed
            review_type: Type of review
            result: The review result to cache
            
        Returns:
            True if cached successfully
        """
        if not self.enabled or not self._cache:
            return False
        
        key = self._hash_content(content, review_type)
        
        try:
            self._cache.set(key, json.dumps(result), expire=self.ttl)
            return True
        except Exception:
            return False
    
    def get_file_review(
        self,
        file_path: str,
        file_hash: str,
        review_type: str,
    ) -> Optional[dict]:
        """
        Get cached review for a specific file.
        
        Args:
            file_path: Path to the file
            file_hash: Hash of file content
            review_type: Type of review
            
        Returns:
            Cached result or None
        """
        if not self.enabled or not self._cache:
            return None
        
        key = f"file:{review_type}:{file_path}:{file_hash}"
        
        try:
            result = self._cache.get(key)
            if result:
                return json.loads(result)
        except Exception:
            pass
        
        return None
    
    def set_file_review(
        self,
        file_path: str,
        file_hash: str,
        review_type: str,
        result: dict,
    ) -> bool:
        """
        Cache review for a specific file.
        
        Args:
            file_path: Path to the file
            file_hash: Hash of file content
            review_type: Type of review
            result: Review result
            
        Returns:
            True if cached successfully
        """
        if not self.enabled or not self._cache:
            return False
        
        key = f"file:{review_type}:{file_path}:{file_hash}"
        
        try:
            self._cache.set(key, json.dumps(result), expire=self.ttl)
            return True
        except Exception:
            return False
    
    def clear(self) -> bool:
        """Clear all cached data."""
        if not self._cache:
            return False
        
        try:
            self._cache.clear()
            return True
        except Exception:
            return False
    
    def stats(self) -> dict:
        """Get cache statistics."""
        if not self._cache:
            return {"enabled": False}
        
        try:
            return {
                "enabled": True,
                "size": len(self._cache),
                "volume": self._cache.volume(),
                "directory": self.cache_dir,
                "ttl": self.ttl,
            }
        except Exception:
            return {"enabled": True, "error": "Could not get stats"}
    
    def close(self):
        """Close the cache."""
        if self._cache:
            self._cache.close()


# Global cache instance
_cache: Optional[ReviewCache] = None


def get_cache() -> ReviewCache:
    """Get or create the global cache instance."""
    global _cache
    
    if _cache is None:
        enabled = os.getenv("ENABLE_CACHE", "true").lower() == "true"
        ttl = int(os.getenv("CACHE_TTL", "3600"))
        cache_dir = os.getenv("CACHE_DIR", ".cache/pr_review")
        
        _cache = ReviewCache(
            cache_dir=cache_dir,
            ttl=ttl,
            enabled=enabled,
        )
    
    return _cache


def hash_patch(patch: str) -> str:
    """Generate a hash for a patch/diff content."""
    # Normalize whitespace and line endings
    normalized = "\n".join(line.strip() for line in patch.splitlines() if line.strip())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
