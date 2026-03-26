"""
Validation query for FujifilmRecipeData before writing to a camera.

Uses write-side constants, which differ from read-side constants in some
cases (e.g. Grain "Off" is stored as raw value 6 or 7 when read back, but
validated as the domain pair ("Off", "Off") for writing).
"""
from __future__ import annotations

import re

from src.data.camera import constants
from src.domain.images.dataclasses import FujifilmRecipeData

# ---------------------------------------------------------------------------
# Pre-computed allowed value sets (write-side constants)
# ---------------------------------------------------------------------------

_VALID_FILM_SIMS: frozenset[str] = frozenset(constants.FILM_SIMULATION_TO_PTP)

_VALID_WB_MODES: frozenset[str] = frozenset(constants.WHITE_BALANCE_TO_PTP)

_VALID_DR_MODES: frozenset[str] = frozenset(constants.DRANGE_MODE_TO_PTP)

_VALID_DR_PRIORITIES: frozenset[str] = frozenset(
    constants.CUSTOM_SLOT_DR_PRIORITY_DECODE.values()
)

# Grain valid (roughness, size) pairs come from the unique tuples in the
# decode table.  The decode table maps two raw values (6 and 7) to the same
# domain pair ("Off", "Off"); the unique pairs are what the write side cares about.
_VALID_GRAIN_PAIRS: frozenset[tuple[str, str]] = frozenset(
    constants.CUSTOM_SLOT_GRAIN_PTP.values()
)

_VALID_CCE: frozenset[str] = frozenset(constants.CUSTOM_SLOT_CCE_PTP.values())

_VALID_CFX: frozenset[str] = frozenset(constants.CUSTOM_SLOT_CFX_PTP.values())

# Valid high-ISO NR domain integers: values of the NR decode table.
_VALID_NR_INTS: frozenset[int] = frozenset(constants.CUSTOM_SLOT_NR_DECODE.values())

_KELVIN_RE: re.Pattern[str] = re.compile(r"^\d+K$")

_EMPTY_OR_NA: frozenset[str] = frozenset(("", "N/A"))


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class RecipeValidationError(ValueError):
    """Raised when a FujifilmRecipeData field contains a value the camera cannot accept."""

    def __init__(self, field: str, value: object) -> None:
        self.field = field
        self.value = value
        super().__init__(f"Invalid value for field {field!r}: {value!r}")


# ---------------------------------------------------------------------------
# Public validation query
# ---------------------------------------------------------------------------


def validate_recipe_for_camera(recipe: FujifilmRecipeData) -> None:
    """
    Validate that every field in *recipe* contains a camera-acceptable value.

    Validates against write-side constants.  Fields that are optional on the
    write path (dynamic_range, d_range_priority, colour chrome, etc.) may be
    empty strings or "N/A" without raising.

    Args:
        recipe: The recipe to validate.

    Raises:
        RecipeValidationError: On the first field that fails validation,
                               carrying the field name and the offending value.
    """
    # --- film_simulation ---
    if recipe.film_simulation not in _VALID_FILM_SIMS:
        raise RecipeValidationError("film_simulation", recipe.film_simulation)

    # --- white_balance: named mode or Kelvin string ("6500K" etc.) ---
    wb = recipe.white_balance
    if wb not in _VALID_WB_MODES and not _KELVIN_RE.match(wb):
        raise RecipeValidationError("white_balance", wb)

    # --- dynamic_range ---
    if recipe.dynamic_range not in _EMPTY_OR_NA and recipe.dynamic_range not in _VALID_DR_MODES:
        raise RecipeValidationError("dynamic_range", recipe.dynamic_range)

    # --- d_range_priority ---
    if (
        recipe.d_range_priority not in _EMPTY_OR_NA
        and recipe.d_range_priority not in _VALID_DR_PRIORITIES
    ):
        raise RecipeValidationError("d_range_priority", recipe.d_range_priority)

    # --- grain: validated as a (roughness, size) pair ---
    grain_pair = (recipe.grain_roughness, recipe.grain_size)
    if grain_pair not in _VALID_GRAIN_PAIRS:
        raise RecipeValidationError("grain_roughness", grain_pair)

    # --- color_chrome_effect ---
    if recipe.color_chrome_effect not in _EMPTY_OR_NA and recipe.color_chrome_effect not in _VALID_CCE:
        raise RecipeValidationError("color_chrome_effect", recipe.color_chrome_effect)

    # --- color_chrome_fx_blue ---
    if (
        recipe.color_chrome_fx_blue not in _EMPTY_OR_NA
        and recipe.color_chrome_fx_blue not in _VALID_CFX
    ):
        raise RecipeValidationError("color_chrome_fx_blue", recipe.color_chrome_fx_blue)

    # --- high_iso_nr: must be a parseable int in the NR lookup ---
    if recipe.high_iso_nr not in _EMPTY_OR_NA:
        try:
            nr_int = int(recipe.high_iso_nr)
        except (ValueError, TypeError):
            raise RecipeValidationError("high_iso_nr", recipe.high_iso_nr)
        if nr_int not in _VALID_NR_INTS:
            raise RecipeValidationError("high_iso_nr", recipe.high_iso_nr)

    # --- numeric string fields ---
    _validate_int_str(recipe, "color")
    _validate_int_str(recipe, "sharpness")
    _validate_int_str(recipe, "clarity")
    _validate_float_str(recipe, "highlight")
    _validate_float_str(recipe, "shadow")
    _validate_float_str(recipe, "monochromatic_color_warm_cool")
    _validate_float_str(recipe, "monochromatic_color_magenta_green")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_int_str(recipe: FujifilmRecipeData, field: str) -> None:
    value = getattr(recipe, field)
    if value in _EMPTY_OR_NA:
        return
    try:
        int(value)
    except (ValueError, TypeError):
        raise RecipeValidationError(field, value)


def _validate_float_str(recipe: FujifilmRecipeData, field: str) -> None:
    value = getattr(recipe, field)
    if value in _EMPTY_OR_NA:
        return
    try:
        float(value)
    except (ValueError, TypeError):
        raise RecipeValidationError(field, value)
