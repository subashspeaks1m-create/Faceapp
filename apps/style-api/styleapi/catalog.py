"""The authoritative style catalog: loaded from catalog.json and validated once at import.

Only `public_catalog()` leaves the server. Prompt text stays here.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CATALOG_PATH = Path(__file__).with_name("catalog.json")

CategoryId = Literal["retro", "illustration", "cinematic", "editorial", "artistic"]
StyleId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=40)]
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-F]{6}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=1200)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Category(_Model):
    id: CategoryId
    name: Text
    summary: Text


class StylePrompt(_Model):
    style: Text
    high_intensity: Text
    avoid: tuple[Text, ...] = Field(min_length=1)
    allowed_changes: Text | None = None


class Style(_Model):
    id: StyleId
    number: int = Field(ge=1, le=99)
    name: Text
    category: CategoryId
    summary: Annotated[str, StringConstraints(min_length=1, max_length=90)]
    tags: tuple[Annotated[str, StringConstraints(min_length=1, max_length=30)], ...]
    default_intensity: int = Field(ge=0, le=100)
    swatch: tuple[HexColor, HexColor, HexColor]
    prompt: StylePrompt


class PromptParts(_Model):
    task: Text
    identity: Text
    composition: Text
    quality: Text
    safety: Text
    global_avoid: tuple[Text, ...] = Field(min_length=1)


class IntensityBand(_Model):
    min: int = Field(ge=0, le=100)
    max: int = Field(ge=0, le=100)
    label: Text
    instruction: Text


class Catalog(_Model):
    version: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}\.\d+$")]
    categories: tuple[Category, ...]
    prompt_parts: PromptParts
    intensity_bands: tuple[IntensityBand, ...]
    styles: tuple[Style, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Catalog:
        ids = [s.id for s in self.styles]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate style id")
        numbers = [s.number for s in self.styles]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("style numbers must be 1..n in order")
        category_ids = {c.id for c in self.categories}
        for s in self.styles:
            if s.category not in category_ids:
                raise ValueError(f"style {s.id} has unknown category")
        # Bands must cover 0..100 exactly once, in order.
        expected = 0
        for band in self.intensity_bands:
            if band.min != expected or band.max < band.min:
                raise ValueError("intensity bands must tile 0..100")
            expected = band.max + 1
        if expected != 101:
            raise ValueError("intensity bands must end at 100")
        return self

    def style(self, style_id: str) -> Style | None:
        return next((s for s in self.styles if s.id == style_id), None)

    def band(self, intensity: int) -> IntensityBand:
        for b in self.intensity_bands:
            if b.min <= intensity <= b.max:
                return b
        raise ValueError("intensity out of range")


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    return Catalog.model_validate_json(CATALOG_PATH.read_bytes())


_PUBLIC_STYLE_FIELDS = ("id", "number", "name", "category", "summary", "tags", "default_intensity", "swatch")


def public_catalog(catalog: Catalog | None = None) -> dict[str, object]:
    """What GET /api/styles returns and what the app bundles. No prompt text."""
    c = catalog or load_catalog()
    return {
        "version": c.version,
        "categories": [c2.model_dump() for c2 in c.categories],
        "intensity_bands": [{"min": b.min, "max": b.max, "label": b.label} for b in c.intensity_bands],
        "styles": [{k: (list(v) if isinstance(v, tuple) else v) for k, v in s.model_dump(include=set(_PUBLIC_STYLE_FIELDS)).items()} for s in c.styles],
    }


def public_catalog_json() -> str:
    """Stable serialisation used for the app's generated module and its drift test."""
    data = public_catalog()
    # Preserve the field order of _PUBLIC_STYLE_FIELDS for readable diffs.
    data["styles"] = [{k: s[k] for k in _PUBLIC_STYLE_FIELDS} for s in data["styles"]]  # type: ignore[index,union-attr]
    return json.dumps(data, indent=2, ensure_ascii=False)


_WHITESPACE = re.compile(r"\s+")


def _sentence(text: str) -> str:
    text = _WHITESPACE.sub(" ", text).strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def build_prompt(style: Style, intensity: int, catalog: Catalog | None = None) -> str:
    """Compose the provider prompt. Order: task, identity, composition, style, strength, quality, safety, avoid."""
    c = catalog or load_catalog()
    if not 0 <= intensity <= 100:
        raise ValueError("intensity out of range")
    parts = c.prompt_parts
    band = c.band(intensity)
    lines = [
        _sentence(parts.task),
        _sentence(parts.identity),
        _sentence(parts.composition),
        _sentence(f"Style: {style.prompt.style}"),
        _sentence(f"Strength {intensity}/100 ({band.label}). {band.instruction}"),
    ]
    if intensity >= 76:
        lines.append(_sentence(style.prompt.high_intensity))
    if style.prompt.allowed_changes:
        lines.append(_sentence(style.prompt.allowed_changes))
    lines.append(_sentence(parts.quality))
    lines.append(_sentence(parts.safety))
    avoid = list(parts.global_avoid) + list(style.prompt.avoid)
    lines.append(_sentence("Avoid: " + "; ".join(avoid)))
    return "\n".join(lines)
