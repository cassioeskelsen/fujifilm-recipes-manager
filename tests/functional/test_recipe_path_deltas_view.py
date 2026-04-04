import json

import pytest

from tests.factories import FujifilmRecipeFactory


def _get(client, ids):
    return client.get("/recipes/path-deltas/", {"ids": ids})


@pytest.mark.django_db
class TestRecipePathDeltasViewBadRequests:
    def test_missing_ids_param_returns_400(self, client):
        response = client.get("/recipes/path-deltas/")

        assert response.status_code == 400

    def test_non_integer_ids_returns_400(self, client):
        response = client.get("/recipes/path-deltas/", {"ids": "abc,def"})

        assert response.status_code == 400


@pytest.mark.django_db
class TestRecipePathDeltasViewSingleNode:
    def test_returns_200_for_valid_single_id(self, client):
        recipe = FujifilmRecipeFactory()

        response = _get(client, str(recipe.pk))

        assert response.status_code == 200

    def test_response_is_json(self, client):
        recipe = FujifilmRecipeFactory()

        response = _get(client, str(recipe.pk))

        assert response["Content-Type"] == "application/json"

    def test_response_contains_root_diffs_and_path_nodes_keys(self, client):
        recipe = FujifilmRecipeFactory()

        response = _get(client, str(recipe.pk))

        data = json.loads(response.content)
        assert "root_diffs" in data
        assert "path_nodes" in data

    def test_single_node_root_diffs_is_empty(self, client):
        recipe = FujifilmRecipeFactory()

        response = _get(client, str(recipe.pk))

        data = json.loads(response.content)
        assert data["root_diffs"] == []

    def test_single_node_path_nodes_has_one_entry(self, client):
        recipe = FujifilmRecipeFactory()

        response = _get(client, str(recipe.pk))

        data = json.loads(response.content)
        assert len(data["path_nodes"]) == 1

    def test_single_node_root_contains_film_simulation_field(self, client):
        recipe = FujifilmRecipeFactory(film_simulation="Velvia")

        response = _get(client, str(recipe.pk))

        data = json.loads(response.content)
        root_node = data["path_nodes"][0]
        field_names = [f["field"] for f in root_node["fields"]]
        assert "Film Simulation" in field_names

    def test_single_node_film_simulation_value_matches(self, client):
        recipe = FujifilmRecipeFactory(film_simulation="Velvia")

        response = _get(client, str(recipe.pk))

        data = json.loads(response.content)
        root_node = data["path_nodes"][0]
        film_sim_field = next(f for f in root_node["fields"] if f["field"] == "Film Simulation")
        assert film_sim_field["value"] == "Velvia"


@pytest.mark.django_db
class TestRecipePathDeltasViewTwoNodes:
    def test_root_diffs_contains_changed_field(self, client):
        root = FujifilmRecipeFactory(grain_roughness="Off", white_balance_red=0, white_balance_blue=0)
        clicked = FujifilmRecipeFactory(
            film_simulation=root.film_simulation,
            grain_roughness="Strong",
            white_balance_red=0,
            white_balance_blue=0,
        )

        response = _get(client, f"{root.pk},{clicked.pk}")

        data = json.loads(response.content)
        diff_fields = [f["field"] for f in data["root_diffs"]]
        assert "Grain" in diff_fields

    def test_root_diffs_uses_clicked_node_value(self, client):
        root = FujifilmRecipeFactory(grain_roughness="Off", white_balance_red=0, white_balance_blue=0)
        clicked = FujifilmRecipeFactory(
            film_simulation=root.film_simulation,
            grain_roughness="Strong",
            white_balance_red=0,
            white_balance_blue=0,
        )

        response = _get(client, f"{root.pk},{clicked.pk}")

        data = json.loads(response.content)
        grain_diff = next(f for f in data["root_diffs"] if f["field"] == "Grain")
        assert grain_diff["value"] == "Strong"

    def test_clicked_node_delta_contains_only_changed_fields(self, client):
        root = FujifilmRecipeFactory(grain_roughness="Off", white_balance_red=0, white_balance_blue=0)
        clicked = FujifilmRecipeFactory(
            film_simulation=root.film_simulation,
            grain_roughness="Strong",
            white_balance_red=0,
            white_balance_blue=0,
        )

        response = _get(client, f"{root.pk},{clicked.pk}")

        data = json.loads(response.content)
        clicked_node = data["path_nodes"][1]
        field_names = [f["field"] for f in clicked_node["fields"]]
        assert "Grain" in field_names
        assert "Film Simulation" not in field_names

    def test_path_nodes_ordered_root_first(self, client):
        root = FujifilmRecipeFactory(white_balance_red=1, white_balance_blue=0)
        clicked = FujifilmRecipeFactory(white_balance_red=2, white_balance_blue=0)

        response = _get(client, f"{root.pk},{clicked.pk}")

        data = json.loads(response.content)
        assert data["path_nodes"][0]["id"] == root.pk
        assert data["path_nodes"][1]["id"] == clicked.pk

    def test_node_label_uses_recipe_name(self, client):
        root = FujifilmRecipeFactory(name="Street Look")
        clicked = FujifilmRecipeFactory(white_balance_red=root.white_balance_red + 1)

        response = _get(client, f"{root.pk},{clicked.pk}")

        data = json.loads(response.content)
        assert data["path_nodes"][0]["label"] == "Street Look"

    def test_node_label_uses_pk_when_unnamed(self, client):
        root = FujifilmRecipeFactory(name="")

        response = _get(client, str(root.pk))

        data = json.loads(response.content)
        assert data["path_nodes"][0]["label"] == f"#{root.pk}"


@pytest.mark.django_db
class TestRecipePathDeltasViewThreeNodes:
    def test_delta_breakdown_present_for_three_node_path(self, client):
        root = FujifilmRecipeFactory(grain_roughness="Off", white_balance_red=0, white_balance_blue=0)
        mid = FujifilmRecipeFactory(
            film_simulation=root.film_simulation,
            grain_roughness="Weak",
            white_balance_red=0,
            white_balance_blue=0,
        )
        clicked = FujifilmRecipeFactory(
            film_simulation=root.film_simulation,
            grain_roughness="Strong",
            white_balance_red=0,
            white_balance_blue=0,
        )

        response = _get(client, f"{root.pk},{mid.pk},{clicked.pk}")

        data = json.loads(response.content)
        assert len(data["path_nodes"]) == 3

    def test_mid_node_delta_is_vs_previous_not_root(self, client):
        root = FujifilmRecipeFactory(
            grain_roughness="Off",
            white_balance_red=0,
            white_balance_blue=0,
        )
        mid = FujifilmRecipeFactory(
            film_simulation=root.film_simulation,
            grain_roughness="Weak",
            white_balance_red=0,
            white_balance_blue=0,
        )
        clicked = FujifilmRecipeFactory(
            film_simulation=root.film_simulation,
            grain_roughness="Strong",
            white_balance_red=0,
            white_balance_blue=0,
        )

        response = _get(client, f"{root.pk},{mid.pk},{clicked.pk}")

        data = json.loads(response.content)
        mid_node = data["path_nodes"][1]
        mid_fields = {f["field"] for f in mid_node["fields"]}
        # Grain changed from root→mid
        assert "Grain" in mid_fields
        # Film Simulation unchanged → not in mid delta
        assert "Film Simulation" not in mid_fields
