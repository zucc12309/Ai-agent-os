from __future__ import annotations

from app.config import get_settings


class RateLimitService:
    """MVP placeholder for rate limiting.

    TODO: replace this with a Redis-backed limiter before production traffic.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def enforce(self, agent_id: str, action: str) -> None:
        if not self.settings.rate_limit_placeholder_enabled:
            return
        # Placeholder hook intentionally left minimal for MVP.
        return


rate_limit_service = RateLimitService()

