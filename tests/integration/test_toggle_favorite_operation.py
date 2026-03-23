import pytest

from src.data.models import Image
from src.domain.images.operations import toggle_image_favorite


@pytest.mark.django_db
class TestToggleImageFavorite:
    def test_marks_non_favorite_image_as_favorite(self):
        image = Image.objects.create(
            filename="test.jpg", filepath="/shots/test.jpg", is_favorite=False
        )

        result = toggle_image_favorite(image_id=image.id)

        assert result is True
        image.refresh_from_db()
        assert image.is_favorite is True

    def test_unmarks_favorite_image_as_non_favorite(self):
        image = Image.objects.create(
            filename="test.jpg", filepath="/shots/test.jpg", is_favorite=True
        )

        result = toggle_image_favorite(image_id=image.id)

        assert result is False
        image.refresh_from_db()
        assert image.is_favorite is False

    def test_toggling_twice_restores_original_state(self):
        image = Image.objects.create(
            filename="test.jpg", filepath="/shots/test.jpg", is_favorite=False
        )

        toggle_image_favorite(image_id=image.id)
        toggle_image_favorite(image_id=image.id)

        image.refresh_from_db()
        assert image.is_favorite is False
