"""
Django management command: verify_camera_recipes

Reads each custom slot from the connected Fujifilm camera, validates that
every decoded field matches a known constant, then looks for recipes in the
database with the closest matching parameters.

Intended workflow:
  1. Push a batch of up to 4 recipes into the camera's custom slots.
  2. Run ``python manage.py verify_camera_recipes`` (or ``--batch N`` for context).
  3. Inspect the output:
     - [DECODE ERROR] lines flag any raw PTP values not in our constants.
     - [DB] lines show the best-matching DB recipes, ranked by field-match score.
     - Mismatching fields are listed so you can spot encoding differences.
     - Name similarity helps confirm the slot label matches the DB recipe name.
  4. Swap in the next batch of recipes and repeat.

Usage:
    python manage.py verify_camera_recipes
    python manage.py verify_camera_recipes --batch 2

Prerequisites / camera setup:
    Same as camera_info — see that command's docstring.
"""

from __future__ import annotations

import difflib
from decimal import Decimal, InvalidOperation

import attrs

from django.core.management.base import BaseCommand

from src.data.models import FujifilmRecipe
from src.domain.camera import queries
from src.domain.camera.ptp_device import CameraConnectionError
from src.domain.camera.ptp_usb_device import PTPUSBDevice
from src.domain.images.dataclasses import FujifilmRecipeData

# Fields decoded from the camera that must not be empty for a valid read.
# grain_roughness/grain_size are excluded: "Off" is a valid state but the raw
# PTP value for Off may not yet be in CUSTOM_SLOT_GRAIN_PTP, decoding to "".
_MANDATORY_FIELDS = (
    "film_simulation",
    "white_balance",
    "dynamic_range",
    "color_chrome_effect",
    "color_chrome_fx_blue",
    "high_iso_nr",
)

# Minimum field-match score (0–1) to include a DB candidate in output.
_MIN_SCORE = 0.7


def _validate(recipe: FujifilmRecipeData) -> list[str]:
    """Return validation errors for any field that failed to decode from raw PTP."""
    return [
        f"{field}: raw PTP value not in constants (decoded as empty string)"
        for field in _MANDATORY_FIELDS
        if not getattr(recipe, field)
    ]


def _to_decimal(value: str) -> Decimal | None:
    """Convert a signed recipe string ('+2', '-1.5', '0') to Decimal, or None if blank."""
    if not value or value in ("N/A",):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _name_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


@attrs.frozen
class RecipeMatch:
    db_recipe: FujifilmRecipe
    score: float                              # fraction of fields that match (0–1)
    mismatches: tuple[tuple[str, str, str], ...]  # (field, camera_value, db_value)
    name_similarity: float


def _score_against_camera(camera: FujifilmRecipeData, db: FujifilmRecipe) -> RecipeMatch:
    """Compare all camera-readable fields and return a scored match result."""
    checks: list[tuple[str, object, object]] = [
        ("film_simulation",      camera.film_simulation,       db.film_simulation),
        ("dynamic_range",        camera.dynamic_range,         db.dynamic_range),
        ("grain_roughness",      camera.grain_roughness,       db.grain_roughness),
        ("grain_size",           camera.grain_size,            db.grain_size),
        ("color_chrome_effect",  camera.color_chrome_effect,   db.color_chrome_effect),
        ("color_chrome_fx_blue", camera.color_chrome_fx_blue,  db.color_chrome_fx_blue),
        ("white_balance",        camera.white_balance,         db.white_balance),
        ("white_balance_red",    camera.white_balance_red,     db.white_balance_red),
        ("white_balance_blue",   camera.white_balance_blue,    db.white_balance_blue),
        ("highlight",            _to_decimal(camera.highlight),    db.highlight),
        ("shadow",               _to_decimal(camera.shadow),       db.shadow),
        ("color",                _to_decimal(camera.color),        db.color),
        ("sharpness",            _to_decimal(camera.sharpness),    db.sharpness),
        ("high_iso_nr",          _to_decimal(camera.high_iso_nr),  db.high_iso_nr),
        ("clarity",              _to_decimal(camera.clarity),      db.clarity),
    ]
    applicable = [(field, cam_val, db_val) for field, cam_val, db_val in checks if db_val is not None]
    mismatches = tuple(
        (field, str(cam_val), str(db_val))
        for field, cam_val, db_val in applicable
        if cam_val != db_val
    )
    return RecipeMatch(
        db_recipe=db,
        score=1.0 - len(mismatches) / len(applicable) if applicable else 1.0,
        mismatches=mismatches,
        name_similarity=_name_similarity(camera.name, db.name),
    )


def _find_db_candidates(camera: FujifilmRecipeData) -> list[RecipeMatch]:
    """
    Fetch DB recipes sharing the same film simulation, score each against the
    camera read, and return those above _MIN_SCORE ranked by score then name
    similarity.
    """
    candidates = FujifilmRecipe.objects.filter(film_simulation=camera.film_simulation)
    matches = [_score_against_camera(camera, db) for db in candidates]
    matches = [m for m in matches if m.score >= _MIN_SCORE]
    matches.sort(key=lambda m: (m.score, m.name_similarity), reverse=True)
    return matches


class Command(BaseCommand):
    help = (
        "Read camera custom slots, validate decoded values against constants, "
        "and find matching recipes in the database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            type=int,
            default=None,
            metavar="N",
            help="Batch number (1–4) — labels output only, does not change behaviour.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print all decoded field values for each slot.",
        )

    def handle(self, *args, **options):
        batch = options["batch"]
        header = f"Batch {batch} — verifying camera slots" if batch else "Verifying camera slots"
        self.stdout.write(f"\n{'─' * 60}")
        self.stdout.write(self.style.MIGRATE_HEADING(header))
        self.stdout.write(f"{'─' * 60}\n")

        self._verbose = options["verbose"]
        self.stdout.write("Connecting to camera via USB…")
        device = PTPUSBDevice()
        try:
            device.connect()
        except CameraConnectionError as e:
            self.stderr.write(self.style.ERROR(f"Connection failed: {e}"))
            return

        try:
            self._run(device)
        except CameraConnectionError as e:
            self.stderr.write(self.style.ERROR(f"Camera error: {e}"))
        finally:
            device.disconnect()
            self.stdout.write("\nDisconnected.")

    def _run(self, device: PTPUSBDevice) -> None:
        info = queries.camera_info(device)
        slot_count = queries.custom_slot_count(info.camera_name)
        self.stdout.write(f"Camera: {info.camera_name}  ({slot_count} custom slots)\n")

        if slot_count == 0:
            self.stderr.write(self.style.WARNING("This camera has no custom slots."))
            return

        for slot_index in range(1, slot_count + 1):
            recipe = queries.slot_recipe(device, slot_index)
            self._print_slot(slot_index, recipe, verbose=self._verbose)

    def _print_slot(self, slot_index: int, recipe: FujifilmRecipeData, *, verbose: bool = False) -> None:
        self.stdout.write(self.style.MIGRATE_LABEL(f"Slot C{slot_index}: {recipe.name!r}"))

        # --- Decoded fields ---------------------------------------------------
        if verbose:
            for field in attrs.fields(type(recipe)):
                if field.name == "name":
                    continue
                self.stdout.write(f"  {field.name}: {getattr(recipe, field.name)!r}")

        # --- Validation -------------------------------------------------------
        errors = _validate(recipe)
        if errors:
            for err in errors:
                self.stdout.write(self.style.ERROR(f"  [DECODE ERROR] {err}"))
        else:
            self.stdout.write(self.style.SUCCESS("  [OK] All fields decoded successfully"))

        # --- DB lookup --------------------------------------------------------
        if not recipe.film_simulation:
            self.stdout.write(
                self.style.WARNING("  [DB] Skipping search — film_simulation could not be decoded")
            )
        else:
            candidates = _find_db_candidates(recipe)
            if not candidates:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [DB] No recipe found with ≥{_MIN_SCORE:.0%} field match"
                    )
                )
            else:
                self.stdout.write(f"  [DB] {len(candidates)} candidate(s):")
                for match in candidates:
                    db = match.db_recipe
                    score_label = f"{match.score:.0%} fields"
                    name_label = f"{match.name_similarity:.0%} name"
                    header_line = f"       #{db.id}  {db.name!r}  ← {score_label}, {name_label}"
                    if match.score == 1.0:
                        self.stdout.write(self.style.SUCCESS(header_line))
                    else:
                        self.stdout.write(header_line)
                    for field, cam_val, db_val in match.mismatches:
                        self.stdout.write(
                            self.style.ERROR(
                                f"         ✗ {field}: camera={cam_val!r}  db={db_val!r}"
                            )
                        )
