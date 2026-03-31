import attrs
from django.db.models import Count, Max, Min
from django.db.models.functions import TruncMonth

from src.data import models


RECIPE_FIELDS = [
    "film_simulation",
    "dynamic_range",
    "d_range_priority",
    "grain_roughness",
    "grain_size",
    "color_chrome_effect",
    "color_chrome_fx_blue",
    "white_balance",
    "white_balance_red",
    "white_balance_blue",
    "highlight",
    "shadow",
    "color",
    "sharpness",
    "high_iso_nr",
    "clarity",
    "monochromatic_color_warm_cool",
    "monochromatic_color_magenta_green",
]


@attrs.frozen
class RecipeUsageStats:
    recipe_id: int
    photo_count: int
    first_used: object  # datetime | None
    last_used: object  # datetime | None


@attrs.frozen
class RecipeComparisonResult:
    recipes: tuple[models.FujifilmRecipe, ...]
    missing_ids: tuple[int, ...]
    stats_by_id: dict[int, RecipeUsageStats]
    # month_key (YYYY-MM) → {recipe_id: count}
    monthly_counts: dict[str, dict[int, int]]


def get_recipe_comparison(recipe_ids: list[int]) -> RecipeComparisonResult:
    """Fetch recipes, usage stats, and monthly breakdowns for the given IDs.

    Returns a structured result containing all data needed to render a comparison,
    so callers make a single query into the domain rather than issuing multiple
    separate ORM calls.
    """
    recipes_by_id = {
        r.id: r for r in models.FujifilmRecipe.objects.filter(id__in=recipe_ids)
    }
    missing = tuple(sorted(set(recipe_ids) - set(recipes_by_id)))
    ordered = tuple(recipes_by_id[i] for i in recipe_ids if i in recipes_by_id)

    raw_stats = (
        models.Image.objects
        .filter(fujifilm_recipe_id__in=recipe_ids, taken_at__isnull=False)
        .values("fujifilm_recipe_id")
        .annotate(
            first_used=Min("taken_at"),
            last_used=Max("taken_at"),
            photo_count=Count("id"),
        )
    )
    stats_by_id = {
        s["fujifilm_recipe_id"]: RecipeUsageStats(
            recipe_id=s["fujifilm_recipe_id"],
            photo_count=s["photo_count"],
            first_used=s["first_used"],
            last_used=s["last_used"],
        )
        for s in raw_stats
    }

    monthly_qs = (
        models.Image.objects
        .filter(fujifilm_recipe_id__in=recipe_ids, taken_at__isnull=False)
        .annotate(month=TruncMonth("taken_at"))
        .values("month", "fujifilm_recipe_id")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    monthly_counts: dict[str, dict[int, int]] = {}
    for row in monthly_qs:
        key = row["month"].strftime("%Y-%m")
        monthly_counts.setdefault(key, {})[row["fujifilm_recipe_id"]] = row["count"]

    return RecipeComparisonResult(
        recipes=ordered,
        missing_ids=missing,
        stats_by_id=stats_by_id,
        monthly_counts=monthly_counts,
    )
