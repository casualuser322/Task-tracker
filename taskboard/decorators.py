import functools
import logging
import time

from django.core.cache import cache
from django.http import JsonResponse


logger = logging.getLogger("tracker")

def rate_limit(
                key_prefix: str, 
                limit: int, period: int, 
                by_user: bool = True, 
            ):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if hasattr(arg, "user"):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request", None)
            
            user_key = f":{request.user.id}" if by_user and request and hasattr(request, "user") else ""
            cache_key = f"rate_limit: {key_prefix}"
            count = cache.get(cache_key, 0)

            if count >= limit: 
                logger.warning(f"Rate limit exceeded for {key_prefix}")
                raise Exception(
                    f"Rate limit exceeded for {key_prefix}", 
                    status=429
                )
            
            cache.incr(cache_key, ignore_key_check=True)
            cache.expire(cache_key, period)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            _delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.exception(f"{func.__name__} failed after {max_attempts} attempts")
                        raise
                    else:
                        logger.warning(f"Retry {attempt}/{max_attempts}")
                        time.sleep(_delay)
                        _delay *= backoff
        return wrapper
    return decorator