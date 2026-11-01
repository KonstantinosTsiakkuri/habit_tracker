"""Тесты API привычек: CRUD, права, публичный список, пагинация, авторизация."""
import datetime

import pytest
from rest_framework.test import APIClient

from habits.models import Habit

pytestmark = pytest.mark.django_db

LIST_URL = "/habits/"
PUBLIC_URL = "/habits/public/"


def detail_url(habit_id):
    return f"/habits/{habit_id}/"


def make_habit(owner, **fields):
    defaults = {"place": "дом", "time": datetime.time(8, 0), "action": "пить воду", "duration": 60}
    defaults.update(fields)
    return Habit.objects.create(owner=owner, **defaults)


def payload(**overrides):
    data = {"place": "парк", "time": "07:30", "action": "бегать", "duration": 90}
    data.update(overrides)
    return data


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


class TestCrudOwnHabit:
    def test_create_sets_owner_from_request(self, auth_client, user):
        response = auth_client.post(LIST_URL, payload(), format="json")
        assert response.status_code == 201
        assert response.data["owner"] == user.id
        assert Habit.objects.get(pk=response.data["id"]).owner == user

    def test_create_ignores_owner_from_client(self, auth_client, user, other_user):
        response = auth_client.post(LIST_URL, payload(owner=other_user.id), format="json")
        assert response.status_code == 201
        assert response.data["owner"] == user.id

    def test_create_invalid_returns_400(self, auth_client):
        response = auth_client.post(LIST_URL, payload(duration=500), format="json")
        assert response.status_code == 400
        assert "duration" in response.data

    def test_list_contains_only_own(self, auth_client, user, other_user):
        mine = make_habit(user)
        make_habit(other_user)
        response = auth_client.get(LIST_URL)
        assert response.status_code == 200
        assert [h["id"] for h in response.data["results"]] == [mine.id]

    def test_retrieve(self, auth_client, user):
        habit = make_habit(user)
        response = auth_client.get(detail_url(habit.id))
        assert response.status_code == 200
        assert response.data["action"] == "пить воду"

    def test_put_update(self, auth_client, user):
        habit = make_habit(user)
        response = auth_client.put(detail_url(habit.id), payload(action="читать"), format="json")
        assert response.status_code == 200
        habit.refresh_from_db()
        assert habit.action == "читать" and habit.place == "парк"

    def test_patch_update(self, auth_client, user):
        habit = make_habit(user)
        response = auth_client.patch(detail_url(habit.id), {"is_public": True}, format="json")
        assert response.status_code == 200
        habit.refresh_from_db()
        assert habit.is_public is True

    def test_patch_cannot_bypass_validators(self, auth_client, user):
        habit = make_habit(user, reward="кофе")
        pleasant = make_habit(user, is_pleasant=True)
        response = auth_client.patch(detail_url(habit.id), {"related_habit": pleasant.id}, format="json")
        assert response.status_code == 400
        habit.refresh_from_db()
        assert habit.related_habit is None

    def test_delete(self, auth_client, user):
        habit = make_habit(user)
        response = auth_client.delete(detail_url(habit.id))
        assert response.status_code == 204
        assert not Habit.objects.filter(pk=habit.id).exists()

    def test_retrieve_missing_returns_404(self, auth_client):
        assert auth_client.get(detail_url(999999)).status_code == 404


class TestForeignHabit:
    """Чужая привычка недоступна: 404 (queryset фильтруется по владельцу)."""

    def test_retrieve_foreign(self, auth_client, other_user):
        habit = make_habit(other_user)
        assert auth_client.get(detail_url(habit.id)).status_code == 404

    def test_update_foreign(self, auth_client, other_user):
        habit = make_habit(other_user)
        assert auth_client.patch(detail_url(habit.id), {"action": "взлом"}, format="json").status_code == 404
        assert auth_client.put(detail_url(habit.id), payload(), format="json").status_code == 404
        habit.refresh_from_db()
        assert habit.action == "пить воду"

    def test_delete_foreign(self, auth_client, other_user):
        habit = make_habit(other_user)
        assert auth_client.delete(detail_url(habit.id)).status_code == 404
        assert Habit.objects.filter(pk=habit.id).exists()

    def test_foreign_public_habit_not_editable_via_detail(self, auth_client, other_user):
        habit = make_habit(other_user, is_public=True)
        assert auth_client.get(detail_url(habit.id)).status_code == 404

    def test_cannot_link_foreign_habit(self, auth_client, other_user):
        foreign = make_habit(other_user, is_pleasant=True, is_public=True)
        response = auth_client.post(LIST_URL, payload(related_habit=foreign.id), format="json")
        assert response.status_code == 400
        assert "related_habit" in response.data


class TestPublicList:
    def test_shows_foreign_public_hides_foreign_private(self, auth_client, user, other_user):
        public = make_habit(other_user, is_public=True)
        private = make_habit(other_user, is_public=False)
        response = auth_client.get(PUBLIC_URL)
        assert response.status_code == 200
        ids = [h["id"] for h in response.data["results"]]
        assert public.id in ids
        assert private.id not in ids

    def test_hides_own_private(self, auth_client, user):
        private = make_habit(user, is_public=False)
        ids = [h["id"] for h in auth_client.get(PUBLIC_URL).data["results"]]
        assert private.id not in ids

    def test_includes_own_public(self, auth_client, user):
        own_public = make_habit(user, is_public=True)
        ids = [h["id"] for h in auth_client.get(PUBLIC_URL).data["results"]]
        assert own_public.id in ids

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_read_only(self, auth_client, method):
        response = getattr(auth_client, method)(PUBLIC_URL, payload(), format="json")
        assert response.status_code == 405

    def test_pagination_applies(self, auth_client, other_user):
        for _ in range(7):
            make_habit(other_user, is_public=True)
        response = auth_client.get(PUBLIC_URL)
        assert response.data["count"] == 7
        assert len(response.data["results"]) == 5


class TestPagination:
    @pytest.fixture
    def seven_habits(self, user):
        return [make_habit(user, action=f"привычка {i}") for i in range(7)]

    def test_default_page(self, auth_client, seven_habits):
        response = auth_client.get(LIST_URL)
        assert response.status_code == 200
        assert set(response.data) == {"count", "next", "previous", "results"}
        assert response.data["count"] == 7
        assert len(response.data["results"]) == 5
        assert response.data["previous"] is None
        assert "offset=5" in response.data["next"]

    def test_limit(self, auth_client, seven_habits):
        response = auth_client.get(LIST_URL, {"limit": 3})
        assert len(response.data["results"]) == 3
        assert response.data["count"] == 7

    def test_offset(self, auth_client, seven_habits):
        response = auth_client.get(LIST_URL, {"offset": 5})
        assert len(response.data["results"]) == 2
        assert response.data["next"] is None
        assert response.data["previous"] is not None

    def test_limit_and_offset_pages_do_not_overlap(self, auth_client, seven_habits):
        first = auth_client.get(LIST_URL, {"limit": 4, "offset": 0}).data["results"]
        second = auth_client.get(LIST_URL, {"limit": 4, "offset": 4}).data["results"]
        ids = [h["id"] for h in first + second]
        assert len(ids) == 7 and len(set(ids)) == 7

    def test_max_limit_is_enforced(self, auth_client, user):
        Habit.objects.bulk_create(
            [Habit(owner=user, place="дом", time=datetime.time(8, 0), action="x", duration=10) for _ in range(51)]
        )
        response = auth_client.get(LIST_URL, {"limit": 1000})
        assert response.data["count"] == 51
        assert len(response.data["results"]) == 50


class TestAuthRequired:
    @pytest.mark.parametrize("url", [LIST_URL, PUBLIC_URL, "/habits/1/"])
    def test_get_without_token(self, api_client, url):
        assert api_client.get(url).status_code == 401

    def test_post_without_token(self, api_client):
        assert api_client.post(LIST_URL, payload(), format="json").status_code == 401

    def test_delete_without_token(self, api_client, user):
        habit = make_habit(user)
        assert api_client.delete(detail_url(habit.id)).status_code == 401
        assert Habit.objects.filter(pk=habit.id).exists()

    def test_with_real_jwt_token(self, api_client, user):
        tokens = api_client.post("/users/login/", {"email": user.email, "password": "StrongPass123!"}).data
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert api_client.get(LIST_URL).status_code == 200


class TestPermissionClass:
    def test_is_owner_checks_object(self, user, other_user):
        from types import SimpleNamespace

        from habits.permissions import IsOwner

        habit = make_habit(user)
        permission = IsOwner()
        assert permission.has_object_permission(SimpleNamespace(user=user), None, habit)
        assert not permission.has_object_permission(SimpleNamespace(user=other_user), None, habit)
