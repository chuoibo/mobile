"""Where a one-time code leaves the server, and the one rule about the debug code.

`SmsSender` is a seam with two implementations. `LogSmsSender` sends nothing --
it is what a host without a gateway runs, which today is every host, and it
writes the code to the log only when asked. `HttpJsonSmsSender` is the shape a
real gateway plugs into: one JSON POST with a bearer token; vendor specifics
(eSMS.vn, SpeedSMS, Twilio) become subclasses that override `payload()`.

`MOBILE_OTP_DEBUG_CODE` makes every challenge carry one fixed code so Maestro
flows and the seed can sign in deterministically. It is honoured ONLY when the
sender is the log sender. A host with a real gateway and a debug code refuses
to start: the same fail-closed shape as `AuthModeInvalid`, because a debug code
on a host that can reach real phones would be a universal password that a
missing environment variable happened to switch on.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Protocol
from uuid import UUID

LOGGER = logging.getLogger(__name__)

GATEWAY_URL_ENV = "MOBILE_SMS_GATEWAY_URL"
GATEWAY_TOKEN_ENV = "MOBILE_SMS_GATEWAY_TOKEN"
TEMPLATE_ENV = "MOBILE_SMS_TEMPLATE"
LOG_CODES_ENV = "MOBILE_OTP_LOG_CODES"
DEBUG_CODE_ENV = "MOBILE_OTP_DEBUG_CODE"
DEFAULT_TEMPLATE = "Ma Ru Di cua ban: {code}. Ma het han sau 5 phut."

_DEBUG_CODE_SHAPE = re.compile(r"^[0-9]{6}$")


class SmsDeliveryError(RuntimeError):
    """The gateway did not accept the message. Carries no phone number."""


class OtpConfigInvalid(RuntimeError):
    """A debug code beside a real gateway. Refuse to start rather than guess."""


class SmsSender(Protocol):
    def send_otp(
        self, *, canonical_phone: str, code: str, challenge_id: UUID
    ) -> None: ...


class LogSmsSender:
    """No gateway. Logs that a challenge was issued; the code only when asked.

    Never logs the number: a phone number in a log file is a phone number in a
    file, and the repo's rule for numbers is no column, no cache, no file.
    """

    def __init__(self, *, log_codes: bool = False) -> None:
        self.log_codes = log_codes

    def send_otp(self, *, canonical_phone: str, code: str, challenge_id: UUID) -> None:
        del canonical_phone
        if self.log_codes:
            LOGGER.info("otp challenge %s issued, code %s", challenge_id, code)
        else:
            LOGGER.info("otp challenge %s issued", challenge_id)


class HttpJsonSmsSender:
    """One JSON POST per code. Vendor subclasses override `payload`."""

    def __init__(
        self,
        url: str,
        token: str,
        template: str = DEFAULT_TEMPLATE,
        timeout: float = 8.0,
    ):
        self.url = url
        self.token = token
        self.template = template
        self.timeout = timeout

    def payload(self, canonical_phone: str, code: str) -> dict:
        return {"to": canonical_phone, "body": self.template.format(code=code)}

    def send_otp(self, *, canonical_phone: str, code: str, challenge_id: UUID) -> None:
        body = json.dumps(self.payload(canonical_phone, code)).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                if not 200 <= response.status < 300:
                    raise SmsDeliveryError(f"gateway answered {response.status}")
        except urllib.error.URLError as exc:
            # Type name only: the exception text can carry the URL and, with
            # some gateways, the request body -- which has the number in it.
            raise SmsDeliveryError(type(exc).__name__) from None
        LOGGER.info("otp challenge %s handed to gateway", challenge_id)


def build_sms_sender(environ) -> SmsSender:
    url = (environ.get(GATEWAY_URL_ENV) or "").strip()
    if not url:
        return LogSmsSender(log_codes=(environ.get(LOG_CODES_ENV) or "").strip() == "1")
    token = (environ.get(GATEWAY_TOKEN_ENV) or "").strip()
    if not token:
        raise OtpConfigInvalid(
            f"{GATEWAY_URL_ENV} is set but {GATEWAY_TOKEN_ENV} is empty"
        )
    return HttpJsonSmsSender(
        url, token, (environ.get(TEMPLATE_ENV) or "").strip() or DEFAULT_TEMPLATE
    )


def resolve_otp_debug_code(environ, sender: SmsSender) -> str | None:
    """The fixed code, or None -- and a refusal when it would be dangerous."""
    raw = (environ.get(DEBUG_CODE_ENV) or "").strip()
    if not raw:
        return None
    if not isinstance(sender, LogSmsSender):
        raise OtpConfigInvalid(
            f"{DEBUG_CODE_ENV} is set on a host with a real SMS gateway; refuse to start"
        )
    if not _DEBUG_CODE_SHAPE.fullmatch(raw):
        raise OtpConfigInvalid(f"{DEBUG_CODE_ENV} must be exactly six digits")
    return raw
