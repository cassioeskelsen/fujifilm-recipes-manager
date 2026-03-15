from pathlib import Path

import pytest
from django.core.management import call_command

from src.data.models import Image
from src.domain.operations import process_image

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "images"
SAMPLE_IMAGE = str(FIXTURES_DIR / "XS107508.jpg")


@pytest.mark.django_db(transaction=True)
class TestReprocessImagesWithoutRecipeCommand:
    def test_creates_recipe_for_images_without_one(self, capsys, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True

        # Process image so the Image record exists, then clear its recipe
        image = process_image(image_path=SAMPLE_IMAGE)
        assert image.fujifilm_recipe is not None

        image.fujifilm_recipe = None
        image.save()
        image.refresh_from_db()
        assert image.fujifilm_recipe is None

        call_command("reprocess_images_without_recipe")

        image.refresh_from_db()
        assert image.fujifilm_recipe is not None

        captured = capsys.readouterr()
        assert "Found 1 image(s) without a recipe." in captured.out
        assert "Enqueued 1 image(s) for reprocessing." in captured.out

    def test_skips_images_that_already_have_a_recipe(self, capsys, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        process_image(image_path=SAMPLE_IMAGE)

        call_command("reprocess_images_without_recipe")

        captured = capsys.readouterr()
        assert "Found 0 image(s) without a recipe." in captured.out
