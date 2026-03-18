from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class SmsSendResult:
    request_id: str
    status: str = "accepted"


class SmsProvider:
    """Placeholder SMS provider for future third-party integration."""

    def send_verification_code(self, phone: str, purpose: str) -> SmsSendResult:
        # TODO: integrate external SMS gateway here.
        request_id = f"mock-{purpose.lower()}-{phone[-4:]}-{int(datetime.now(UTC).timestamp())}"
        return SmsSendResult(request_id=request_id)
