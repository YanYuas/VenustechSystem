# ============================================================
# 简单内存缓存（TTL过期，线程安全）
# 用于高频只读查询：dashboard统计、配置、领域列表等
# 对齐架构 v2.0 §5.5 缓存策略
# ============================================================
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class TTLCache:
    """线程安全的TTL内存缓存"""

    def __init__(self, default_ttl: int = 60):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            value, expire_at = item
            if time.time() > expire_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expire_at = time.time() + (ttl or self._default_ttl)
        with self._lock:
            self._store[key] = (value, expire_at)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def cached(self, key: str, ttl: int | None = None) -> Callable:
        """装饰器：缓存函数返回值"""
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                cache_key = f"{key}:{args}:{sorted(kwargs.items())}"
                cached = self.get(cache_key)
                if cached is not None:
                    return cached
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result
            return wrapper
        return decorator


# 全局缓存实例
cache = TTLCache(default_ttl=60)
