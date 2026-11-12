# Changelog

## 1.0.0 - 2026-11-12

First stable release. No change since 0.1.0.

## 0.1.0 - 2026-11-12

First release: a maintained rewrite of rexave/hass-orange-internet-on-the-move, usable as a drop-in replacement (same domain, devices and entity unique IDs; its config entries are migrated).

### Features
- Every car of the account, each as a device; cars added to the account later show up on the next update.
- The running plan is shown, even when the portal also lists past or upcoming plans.
- New `Data used` sensor.
- Reauthentication when the portal rejects the credentials, and reconfiguration from the UI.
- Diagnostics with the credentials, serial numbers and device IDs redacted.
- Translations: English, French, German, Spanish, Serbian (Cyrillic and Latin), Italian, Dutch, Portuguese (European and Brazilian), Polish, Romanian, Danish, Swedish, Bulgarian, Russian, Ukrainian, Hungarian, Slovak, Czech, Slovenian, Latvian and Greek.

### Fixes (compared with rexave's integration)
- No more `CONN_CLASS_CLOUD_POLL` deprecation warning (removed in Home Assistant 2027.5).
- No more entity without a unique ID attached to the device (deprecated in 2027.8): the base class was added as an entity by mistake.
- Data sizes were labelled Mbit but held MiB; they now carry the right unit (GiB by default on new installs).
- The token is reused across updates instead of logging in every hour, and the plans of all cars are fetched in parallel.
- A failed update makes the entities unavailable instead of keeping stale values; a plan with a zero size no longer crashes the percentage.
- Dates without a timezone no longer break the timestamp sensors.
- The password and the token are no longer written to the logs.
- The same account can no longer be added twice.
