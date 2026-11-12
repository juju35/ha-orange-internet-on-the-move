"""Every translation file has exactly the keys and placeholders of the English one."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

COMPONENT = Path(__file__).parent.parent / "custom_components" / "orange_internet_on_the_move"
TRANSLATIONS = COMPONENT / "translations"
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# Brand and product names stay in Latin letters in the Cyrillic file.
_BRANDS = re.compile(r"Orange Internet On the move|internetonthemove\.orange-business\.com|\{\w+\}")


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, f"{path}."))
        else:
            out[path] = value
    return out


def _read(path: Path) -> dict[str, str]:
    return _flatten(json.loads(path.read_text(encoding="utf-8")))


def _load(lang: str) -> dict[str, str]:
    return _read(TRANSLATIONS / f"{lang}.json")


def test_languages() -> None:
    """Every shipped language, including both Serbian scripts and both Portuguese variants."""
    shipped = {p.stem for p in TRANSLATIONS.glob("*.json")}
    assert shipped >= {"en", "fr", "de", "es", "sr", "sr-Latn", "it", "nl", "pt", "pt-BR", "pl"}
    assert shipped >= {"ro", "da", "sv", "bg", "ru", "uk", "hu", "sk", "cs", "sl", "lv", "el"}


def test_strings_match_english() -> None:
    """strings.json and translations/en.json stay identical."""
    assert _read(COMPONENT / "strings.json") == _load("en")


@pytest.mark.parametrize("lang", sorted(p.stem for p in TRANSLATIONS.glob("*.json") if p.stem != "en"))
def test_parity(lang: str) -> None:
    """Same keys as English, same placeholders in every string, no empty value."""
    en, other = _load("en"), _load(lang)
    assert sorted(other) == sorted(en)
    for key, text in en.items():
        assert other[key].strip(), f"{lang}: {key} is empty"
        assert sorted(PLACEHOLDER.findall(other[key])) == sorted(PLACEHOLDER.findall(text)), f"{lang}: {key}"


def test_serbian_cyrillic_has_no_latin() -> None:
    """sr is Cyrillic only, apart from brand names."""
    for key, text in _load("sr").items():
        assert not re.search(r"[A-Za-z]", _BRANDS.sub("", text)), key


def test_serbian_latin_has_no_cyrillic() -> None:
    """sr-Latn is Latin only."""
    for key, text in _load("sr-Latn").items():
        assert not re.search(r"[Ѐ-ӿ]", text), key


# Serbian Cyrillic letter by letter, then its Latin spelling (љ, њ and џ take two letters).
_SERBIAN = "аaбbвvгgдdђđеeжžзzиiјjкkлlљljмmнnњnjоoпpрrсsтtћćуuфfхhцcчčџdžшš"
_TO_LATIN = dict(re.findall(r"([а-џ])([^а-џ]+)", _SERBIAN))
_TO_LATIN |= {c.upper(): lat.capitalize() for c, lat in _TO_LATIN.items()}


def test_serbian_scripts_match() -> None:
    """The Cyrillic and Latin Serbian files say the same thing, letter for letter."""
    cyrillic, latin = _load("sr"), _load("sr-Latn")
    for key, text in cyrillic.items():
        assert "".join(_TO_LATIN.get(ch, ch) for ch in text) == latin[key], key
