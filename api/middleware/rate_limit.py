"""
Rate Limiting Middleware for Research OS.

Provides API rate limiting using token bucket algorithm.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter.

    Tracks requests per client and enforces rate limits.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst: int = 100,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute
            burst: Maximum burst size (token bucket capacity)
        """
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.refill_rate = requests_per_minute / 60.0  # tokens per second

        # Client state: {client_id: {"tokens": float, "last_update": float}}
        self._clients: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"tokens": float(burst), "last_update": time.time()}
        )

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request."""
        # Use X-Forwarded-For if behind proxy, otherwise use client host
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _refill_tokens(self, client_id: str) -> None:
        """Refill tokens based on time elapsed."""
        client = self._clients[client_id]
        now = time.time()
        elapsed = now - client["last_update"]

        # Add tokens based on elapsed time
        client["tokens"] = min(self.burst, client["tokens"] + elapsed * self.refill_rate)
        client["last_update"] = now

    def check_limit(self, request: Request) -> bool:
        """
        Check if request is within rate limit.

        Args:
            request: FastAPI request

        Returns:
            True if allowed, False if rate limited
        """
        client_id = self._get_client_id(request)
        self._refill_tokens(client_id)

        if self._clients[client_id]["tokens"] >= 1.0:
            self._clients[client_id]["tokens"] -= 1.0
            return True

        return False

    def get_remaining(self, request: Request) -> int:
        """Get remaining requests for client."""
        client_id = self._get_client_id(request)
        self._refill_tokens(client_id)
        return int(self._clients[client_id]["tokens"])

    def get_reset_time(self, request: Request) -> float:
        """Get seconds until token bucket is full."""
        client_id = self._get_client_id(request)
        client = self._clients[client_id]
        tokens_needed = self.burst - client["tokens"]
        return tokens_needed / self.refill_rate if self.refill_rate > 0 else 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Usage:
        app.add_middleware(RateLimitMiddleware, requests_per_minute=60, burst=100)
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst: int = 100,
        enabled: bool = True,
        exclude_paths: list = None,
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests per minute
            burst: Maximum burst size
            enabled: Whether rate limiting is enabled
            exclude_paths: Paths to exclude from rate limiting
        """
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute, burst)
        self.enabled = enabled
        self.exclude_paths = exclude_paths or [
            "/health",
            "/health/live",
            "/health/ready",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Skip if rate limiting is disabled
        if not self.enabled:
            return await call_next(request)

        # Check rate limit
        if not self.limiter.check_limit(request):
            reset_time = self.limiter.get_reset_time(request)
            remaining = self.limiter.get_remaining(request)

            logger.warning(
                f"Rate limit exceeded for {request.client.host if request.client else 'unknown'}",
                extra={"path": request.url.path},
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.limiter.requests_per_minute} requests per minute",
                    "retry_after": int(reset_time) + 1,
                    "remaining": remaining,
                },
                headers={
                    "Retry-After": str(int(reset_time) + 1),
                    "X-RateLimit-Limit": str(self.limiter.requests_per_minute),
                    "X-RateLimit-Remaining": str(remaining),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        remaining = self.limiter.get_remaining(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
