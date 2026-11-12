"""Client for the Orange Internet On the move portal (internetonthemove.orange-business.com).

The portal logs in with HTTP basic auth and hands back a token in the ``x-auth-token``
response header; every other call sends that token. The token is kept and reused across
updates, and the login is only repeated when the portal rejects it.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    CONSUMPTION_PATH,
    DEVICES_PATH,
    HEADER_APPLICATION,
    HEADER_PROVIDER,
    LOGIN_PATH,
    TOKEN_HEADER,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_AUTH_STATUSES = frozenset({401, 403})


class OrangeIotmError(Exception):
    """The portal could not be reached or answered something unexpected."""


class OrangeIotmAuthError(OrangeIotmError):
    """The portal rejected the credentials."""


@dataclass(frozen=True, slots=True)
class Plan:
    """A data plan of a device; data amounts are in KiB, as the portal sends them."""

    plan_type: str | None
    initial_data: float | None
    left_data: float | None
    start_date: datetime | None
    expiry_date: datetime | None

    @property
    def used_data(self) -> float | None:
        """Data used so far, in KiB."""
        if self.initial_data is None or self.left_data is None:
            return None
        return max(self.initial_data - self.left_data, 0)

    @property
    def left_percentage(self) -> int | None:
        """Share of the plan left, rounded down (never shows 100 % once data was used)."""
        if not self.initial_data or self.left_data is None:
            return None
        return max(0, min(100, int(self.left_data * 100 // self.initial_data)))


@dataclass(frozen=True, slots=True)
class Device:
    """A connected car (SIM) of the account."""

    device_id: str
    tag: str | None
    serial_number: str | None
    status: str | None


@dataclass(frozen=True, slots=True)
class DeviceData:
    """What the integration exposes for one device."""

    device: Device
    plan: Plan | None


def _parse_datetime(value: Any) -> datetime | None:
    """ISO 8601 date from the portal, made timezone-aware (UTC when it carries no offset)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        _LOGGER.debug("Unparsable date from the portal: %s", value)
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_plan(raw: dict[str, Any]) -> Plan:
    return Plan(
        plan_type=raw.get("type"),
        initial_data=_parse_number(raw.get("initial_data")),
        left_data=_parse_number(raw.get("left_data")),
        start_date=_parse_datetime(raw.get("start_date")),
        expiry_date=_parse_datetime(raw.get("expiry_date")),
    )


def select_plan(plans: list[Plan], now: datetime) -> Plan | None:
    """The plan to show: the running one ending last, else the one that started last.

    The portal lists every plan of the device (past, running, upcoming) in no
    guaranteed order, so the first entry is not necessarily the current one.
    """
    if not plans:
        return None
    running = [
        plan
        for plan in plans
        if (plan.start_date is None or plan.start_date <= now) and (plan.expiry_date is None or now < plan.expiry_date)
    ]
    if running:
        return max(running, key=lambda plan: plan.expiry_date or datetime.max.replace(tzinfo=UTC))
    return max(plans, key=lambda plan: plan.start_date or datetime.min.replace(tzinfo=UTC))


def _parse_device(raw: dict[str, Any]) -> Device | None:
    device_id = raw.get("id")
    if device_id in (None, ""):
        return None
    return Device(
        device_id=str(device_id),
        tag=raw.get("tag") or None,
        serial_number=raw.get("serial_number") or None,
        status=raw.get("status") or None,
    )


class OrangeIotmClient:
    """Talks to the portal on behalf of one account."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        """Keep the shared session and the credentials; nothing is sent yet."""
        self._session = session
        self._auth = aiohttp.BasicAuth(username, password)
        self._token: str | None = None
        # One login at a time, even when several requests find the token expired together.
        self._login_lock = asyncio.Lock()

    def _headers(self) -> dict[str, str]:
        headers = {"x-application": HEADER_APPLICATION, "x-provider": HEADER_PROVIDER, "Accept": "application/json"}
        if self._token:
            headers[TOKEN_HEADER] = self._token
        return headers

    async def async_login(self) -> None:
        """Log in and keep the token. Raises OrangeIotmAuthError on bad credentials."""
        try:
            async with self._session.post(
                f"{BASE_URL}{LOGIN_PATH}", headers=self._headers(), auth=self._auth, timeout=_TIMEOUT
            ) as response:
                if response.status in _AUTH_STATUSES:
                    raise OrangeIotmAuthError(f"Login rejected (HTTP {response.status})")
                if response.status != 200:
                    raise OrangeIotmError(f"Login failed (HTTP {response.status})")
                token = response.headers.get(TOKEN_HEADER)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OrangeIotmError(f"Cannot reach the portal: {err!r}") from err
        if not token:
            raise OrangeIotmError("The portal sent no token")
        self._token = token

    async def _async_get_json(self, path: str) -> Any:
        """GET a portal path, logging in first if needed and once again if the token was rejected."""
        rejected: str | None = None
        for attempt in range(2):
            async with self._login_lock:
                # Log in when there is no token yet, or when the portal rejected the one we hold
                # (unless a parallel request already replaced it while this one waited).
                if self._token is None or self._token == rejected:
                    self._token = None
                    await self.async_login()
                token = self._token
            try:
                async with self._session.get(
                    f"{BASE_URL}{path}", headers=self._headers(), timeout=_TIMEOUT
                ) as response:
                    if response.status in _AUTH_STATUSES:
                        if attempt == 0:
                            _LOGGER.debug("Token rejected (HTTP %s), logging in again", response.status)
                            rejected = token
                            continue
                        raise OrangeIotmAuthError(f"Access rejected after a fresh login (HTTP {response.status})")
                    if response.status != 200:
                        raise OrangeIotmError(f"{path} failed (HTTP {response.status})")
                    return await response.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                raise OrangeIotmError(f"Cannot read {path}: {err!r}") from err
        raise OrangeIotmError(f"{path} failed")  # pragma: no cover - the loop always returns or raises

    async def async_get_devices(self) -> list[Device]:
        """Every device of the account."""
        raw = await self._async_get_json(DEVICES_PATH)
        if not isinstance(raw, list):
            raise OrangeIotmError("Unexpected device list from the portal")
        return [device for item in raw if isinstance(item, dict) and (device := _parse_device(item)) is not None]

    async def async_get_plans(self, device_id: str) -> list[Plan]:
        """Every plan of one device."""
        raw = await self._async_get_json(CONSUMPTION_PATH.format(device_id=device_id))
        if not isinstance(raw, list):
            raise OrangeIotmError("Unexpected consumption data from the portal")
        return [_parse_plan(item) for item in raw if isinstance(item, dict)]

    async def async_get_data(self, now: datetime) -> dict[str, DeviceData]:
        """Devices and their current plan, the plans of all devices fetched in parallel."""
        devices = await self.async_get_devices()
        plans = await asyncio.gather(*(self.async_get_plans(device.device_id) for device in devices))
        return {
            device.device_id: DeviceData(device=device, plan=select_plan(device_plans, now))
            for device, device_plans in zip(devices, plans, strict=True)
        }
