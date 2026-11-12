<p align="center">
  <img src="https://raw.githubusercontent.com/juju35/ha-orange-internet-on-the-move/main/custom_components/orange_internet_on_the_move/brand/icon@2x.png" alt="Orange Internet On the move" width="128" height="128">
</p>

# ha-orange-internet-on-the-move

[![Marketplace](https://img.shields.io/badge/Marketplace-Custom-41BDF5.svg)](https://www.home-assistant.io/integrations/marketplace/)
[![HACS Validation](https://github.com/juju35/ha-orange-internet-on-the-move/actions/workflows/hacs.yml/badge.svg)](https://github.com/juju35/ha-orange-internet-on-the-move/actions/workflows/hacs.yml)
[![Validate](https://github.com/juju35/ha-orange-internet-on-the-move/actions/workflows/validate.yml/badge.svg)](https://github.com/juju35/ha-orange-internet-on-the-move/actions/workflows/validate.yml)
[![Lint](https://github.com/juju35/ha-orange-internet-on-the-move/actions/workflows/lint.yml/badge.svg)](https://github.com/juju35/ha-orange-internet-on-the-move/actions/workflows/lint.yml)
[![Release](https://img.shields.io/github/v/release/juju35/ha-orange-internet-on-the-move)](https://github.com/juju35/ha-orange-internet-on-the-move/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/juju35/ha-orange-internet-on-the-move/blob/main/LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/julienstep9)

Home Assistant integration for **Orange Internet On the move**, the in-car mobile data plan of Renault vehicles managed on the [Orange Business portal](https://internetonthemove.orange-business.com/): data left, data used, plan size and dates, for every car of the account.

It is a maintained rewrite of [rexave/hass-orange-internet-on-the-move](https://github.com/rexave/hass-orange-internet-on-the-move) and a drop-in replacement for it: same domain, same devices and same entity unique IDs, so existing entities, their history and dashboards are kept (see [Migrating from rexave's integration](#migrating-from-rexaves-integration)).

[![Open your Home Assistant instance and open a repository inside the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=juju35&repository=ha-orange-internet-on-the-move&category=integration)

## Features

- Every car of the account, each as a device, and cars added to the account later show up without a reload
- The running plan, even when the portal also lists past or upcoming ones
- Data left, data used, plan data, percentage left, plan start, plan expiry and plan type
- One login reused across updates (logged in again only when the portal rejects the token), the plans of all cars fetched in parallel, hourly polling
- Reauthentication and reconfiguration from the UI, entities unavailable (not stale) when the portal cannot be reached
- Diagnostics with the credentials, serial numbers and device IDs redacted; credentials and tokens never logged
- English, French, German, Spanish, Serbian (Cyrillic and Latin), Italian, Dutch, Portuguese (European and Brazilian), Polish, Romanian, Danish, Swedish, Bulgarian, Russian, Ukrainian, Hungarian, Slovak, Czech, Slovenian, Latvian and Greek

## Prerequisites

- Home Assistant 2025.8 or later
- An account on the [Orange Internet On the move portal](https://internetonthemove.orange-business.com/)

## Installation

### Via the Marketplace (recommended)

Click the button below to add the repository directly:

[![Add to the Marketplace](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=juju35&repository=ha-orange-internet-on-the-move&category=integration)

Then click **Install** and restart Home Assistant.

Or manually:

1. Open **Settings → Marketplace → Add from link** (top right; this needs a GitHub account connected)
2. Add `https://github.com/juju35/ha-orange-internet-on-the-move` — Type: **Integration**
3. Open **Orange Internet On the move** and click **Install**
4. Restart Home Assistant

### Manual

Copy `custom_components/orange_internet_on_the_move/` to `/config/custom_components/orange_internet_on_the_move/`, then restart Home Assistant.

## Configuration

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=orange_internet_on_the_move)

**Settings → Devices & services → Add integration → Orange Internet On the move**, then enter the email and password of the portal account. One entry per account; to change the password later, use **⋮ → Reconfigure**.

### Entities

One device per car, named after its tag on the portal, with:

| Entity | Unit | Description |
|---|---|---|
| `sensor.<car>_data_left` | GiB | Data left in the running plan |
| `sensor.<car>_data_used` | GiB | Data used so far |
| `sensor.<car>_plan_data` | GiB | Size of the plan |
| `sensor.<car>_data_left_percentage` | % | Share of the plan left, rounded down |
| `sensor.<car>_plan_start` | timestamp | Start of the plan |
| `sensor.<car>_plan_expiry` | timestamp | End of the plan |
| `sensor.<car>_plan_type` | | Plan type as the portal names it (for example `onetime`) |

The sizes can be shown in another unit (MiB, GB…) from the entity settings. A car without a plan shows its sensors as unknown; a car removed from the account goes unavailable and can then be deleted from its device page.

## Use with ha-vehicle-card

[ha-vehicle-card](https://github.com/juju35/ha-vehicle-card) shows these sensors in its optional Orange Internet On the move section.

## Migrating from rexave's integration

1. Remove `custom_components/orange_internet_on_the_move/` of rexave's integration (or uninstall it from the Marketplace) — **keep its entry in Devices & services**
2. Install this integration and restart Home Assistant

The existing entry is migrated on its own: the credentials move to the standard keys and the entry gets the account as its unique ID. The device and the entities keep their IDs, so history and dashboards carry on. Changes you will notice:

- The data sizes were labelled `Mbit` but held MiB: the numbers are unchanged and now correctly in MiB. New installs show GiB.
- A new `data_used` sensor, and the other cars of the account if it has several.
- The warnings of Home Assistant about `CONN_CLASS_CLOUD_POLL` (removed in 2027.5) and about an entity without unique ID attached to a device (2027.8) are gone: that entity was a stray copy of the base class, never a real sensor.

## How it works

The integration logs in to the portal (`/user-api/login`, HTTP basic auth) and keeps the token it returns. Every hour it lists the devices of the account (`/user-api/devices`) and fetches their plans (`/user-api/devices/<id>/consumption`) in parallel, then keeps the plan running now. When the portal rejects the token it logs in again once; when it rejects the credentials, Home Assistant asks to sign in again.

To report a problem, download the diagnostics from **Settings → Devices & services → Orange Internet On the move → ⋮ → Download diagnostics** and attach them to the issue. Credentials, serial numbers and device IDs are redacted.

To debug:

```yaml
logger:
  logs:
    custom_components.orange_internet_on_the_move: debug
```

## Development

```bash
pip install -r requirements_test.txt && pytest
```

### Releasing

1. Bump the version in `custom_components/orange_internet_on_the_move/manifest.json`
2. Add a `## <version>` section at the top of [CHANGELOG.md](https://github.com/juju35/ha-orange-internet-on-the-move/blob/main/CHANGELOG.md)
3. Push to `main`: the **Release** workflow creates the tag and the GitHub release with the changelog section as notes

## Translations

The integration follows the language of Home Assistant. Currently supported:

| Language | Code |
|---|---|
| English | `en` |
| Français | `fr` |
| Deutsch | `de` |
| Español | `es` |
| Српски | `sr` |
| Srpski (latinica) | `sr-Latn` |
| Italiano | `it` |
| Nederlands | `nl` |
| Português | `pt` |
| Português (Brasil) | `pt-BR` |
| Polski | `pl` |
| Română | `ro` |
| Dansk | `da` |
| Svenska | `sv` |
| Български | `bg` |
| Русский | `ru` |
| Українська | `uk` |
| Magyar | `hu` |
| Slovenčina | `sk` |
| Čeština | `cs` |
| Slovenščina | `sl` |
| Latviešu | `lv` |
| Ελληνικά | `el` |

## Credits

Based on the work of [rexave](https://github.com/rexave) on [hass-orange-internet-on-the-move](https://github.com/rexave/hass-orange-internet-on-the-move), which found the portal API.

## License

[MIT](https://github.com/juju35/ha-orange-internet-on-the-move/blob/main/LICENSE)

Not affiliated with Orange or Renault. Orange and Renault are trademarks of their respective owners.

## Support

If you find this project useful, you can support its development:

<a href="https://buymeacoffee.com/julienstep9"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="50"></a>
