import time
import logging
from typing import Any

import requests
import urllib3
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class TBBApiClient:
    """Base client for TBB verisistemi API.

    All TBB data routes go through POST /api/router with a JSON body
    containing {"route": "<route_name>", ...params}.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "Content-Type": "application/json",
            "token": settings.TBB_API_TOKEN,
            "role": settings.TBB_API_ROLE,
            "LANG": settings.TBB_API_LANG,
        })
        self.base_url = settings.TBB_API_URL
        self._last_request_time: float = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        wait = settings.TBB_RATE_LIMIT_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying TBB API call (attempt %d)", retry_state.attempt_number
        ),
    )
    def call(self, route: str, params: dict[str, Any] | None = None) -> Any:
        self._rate_limit()

        payload = {"route": route}
        if params:
            payload.update(params)

        logger.info("TBB API call: route=%s", route)
        response = self.session.post(self.base_url, json=payload, timeout=60)
        self._last_request_time = time.time()

        response.raise_for_status()
        return response.json()

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
