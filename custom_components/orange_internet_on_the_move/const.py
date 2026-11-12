"""Constants for the Orange Internet On the move integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "orange_internet_on_the_move"

# The portal publishes the remaining data once in a while: hourly polling is plenty.
UPDATE_INTERVAL: Final = timedelta(hours=1)

BASE_URL: Final = "https://internetonthemove.orange-business.com"
LOGIN_PATH: Final = "/user-api/login"
DEVICES_PATH: Final = "/user-api/devices"
CONSUMPTION_PATH: Final = "/user-api/devices/{device_id}/consumption"

# Headers the client portal sends; the provider is the car maker the plan comes with.
HEADER_APPLICATION: Final = "CLIENT_PORTAL"
HEADER_PROVIDER: Final = "RENAULT"
TOKEN_HEADER: Final = "x-auth-token"

# Config entry data keys written by rexave/hass-orange-internet-on-the-move (entry version 1),
# migrated to the standard CONF_USERNAME / CONF_PASSWORD in version 2.
LEGACY_CONF_USERNAME: Final = "config_username"
LEGACY_CONF_PASSWORD: Final = "config_password"
