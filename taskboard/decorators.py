import functools
import logging
import random
import time

from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger("tracker")


def rate_limit(
    key_prefix: str,
    limit: int,
    period: int,
    by_user: bool = True,
):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = args[0] if args else kwargs.get("request")
            if request is None:
                raise ValueError(
                    "rate_limit decorator requires request argument"
                )

            if by_user:
                if request.user.is_authenticated:
                    identifier = f"user_{request.user.id}"
                else:
                    ip = (
                        request.META.get("HTTP_X_FORWARDED_FOR", "")
                        .split(",")[0]
                        .strip()  # TODO Change this if you dont use reverse proxy like nginx
                        or request.META.get("REMOTE_ADDR")
                        or "0.0.0.0"
                    )
                    identifier = f"ip_{ip}"
            else:
                identifier = "global"

            cache_key = f"rate_limit:v1:{key_prefix}:{identifier}"

            try:
                count = cache.get(cache_key)

                if count is None:
                    cache.set(cache_key, 1, timeout=period)
                    count = 1
                else:
                    count = cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, timeout=period)
                count = 1

            if count > limit:
                logger.warning(f"Rate limit exceeded for {cache_key}")
                return HttpResponse(
                    "Too many requests",
                    status=429,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts:
                        logger.exception(
                            f"{func.__name__} failed after {max_attempts} attempts"
                        )
                        raise
                    else:
                        logger.warning(f"Retry {attempt}/{max_attempts}")
                        time.sleep(_delay / 2 + random.uniform(0, _delay / 2))
                        _delay *= backoff

        return wrapper

    return decorator
