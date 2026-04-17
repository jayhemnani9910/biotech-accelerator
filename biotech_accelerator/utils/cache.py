"""Simple disk-based caching for API responses."""

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Simple disk-based cache for API responses.

    Caches JSON-serializable responses with TTL support.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        default_ttl: int = 3600 * 24,  # 24 hours
    ):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files
            default_ttl: Default time-to-live in seconds
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".biotech-accelerator" / "cache"

        self.cache_dir = cache_dir
        self.default_ttl = default_ttl

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, namespace: str, key: str) -> Path:
        """Get the cache file path for a key."""
        # Include namespace in filename for proper isolation
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{namespace}_{safe_key}.json"

    @staticmethod
    def _normalize_entry(cached: dict) -> tuple[float, Any]:
        """Extract (expiration_timestamp, value) from a cached entry.

        Supports both current format ({"value", "expiration"}) and a legacy
        format ({"data", "expires_at"}) produced by earlier versions.
        """
        expiration = cached.get("expiration")
        if expiration is None:
            expiration = cached.get("expires_at", 0)
        value = cached.get("value")
        if value is None:
            value = cached.get("data")
        return float(expiration or 0), value

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Get cached value if it exists and hasn't expired.

        Args:
            namespace: Cache namespace (e.g., "chembl", "uniprot")
            key: Cache key (e.g., query string)

        Returns:
            Cached value or None if not found/expired
        """
        cache_path = self._get_cache_path(namespace, key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Cache read error for {cache_path.name}: {e}")
            return None

        expiration, value = self._normalize_entry(cached)
        if time.time() > expiration:
            cache_path.unlink(missing_ok=True)
            return None

        logger.debug(f"Cache hit: {namespace}:{key[:50]}")
        return value

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Set a value in the cache with atomic write.

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        ttl = ttl or self.default_ttl
        expiration = time.time() + ttl

        cache_path = self._get_cache_path(namespace, key)
        cache_data = {
            "value": value,
            "expiration": expiration,
            "namespace": namespace,
            "key": key,
        }

        # Atomic write via temp file within the same directory.
        try:
            fd, temp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(cache_data, f)
                shutil.move(temp_path, cache_path)
            except (OSError, TypeError) as e:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                logger.warning(f"Failed to write cache {cache_path.name}: {e}")
        except OSError as e:
            logger.warning(f"Failed to create cache temp file: {e}")

    def invalidate(self, namespace: str, key: str) -> None:
        """Remove a cached value."""
        cache_path = self._get_cache_path(namespace, key)
        cache_path.unlink(missing_ok=True)

    def clear_namespace(self, namespace: str) -> int:
        """Clear all entries in a namespace."""
        count = 0
        prefix = f"{namespace}_"
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.stem.startswith(prefix):
                try:
                    cache_file.unlink()
                    count += 1
                except OSError:
                    pass
        return count

    def clear_all(self) -> int:
        """Clear entire cache."""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink(missing_ok=True)
            count += 1
        return count

    def stats(self) -> dict:
        """Get cache statistics."""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        valid_count = 0
        expired_count = 0

        for cache_file in cache_files:
            try:
                with open(cache_file, "r") as f:
                    cached = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.debug(f"Treating unreadable cache {cache_file.name} as expired: {e}")
                expired_count += 1
                continue

            expiration, _ = self._normalize_entry(cached)
            if time.time() <= expiration:
                valid_count += 1
            else:
                expired_count += 1

        return {
            "total_files": len(cache_files),
            "valid_count": valid_count,
            "expired_count": expired_count,
            "total_size_mb": total_size / (1024 * 1024),
        }


# Global cache instance
_cache: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache
