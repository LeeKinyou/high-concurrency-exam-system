import json

import pytest

from core.responses import error_response, paginated_response, success_response


@pytest.mark.django_db
class TestSuccessResponse:
    def test_basic_success(self):
        resp = success_response()
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["code"] == 200
        assert data["message"] == "操作成功"
        assert data["data"] is None

    def test_with_data(self):
        resp = success_response(data={"id": 1, "name": "test"})
        data = json.loads(resp.content)
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "test"

    def test_custom_message_and_status(self):
        resp = success_response(message="创建成功", status_code=201)
        assert resp.status_code == 201
        data = json.loads(resp.content)
        assert data["code"] == 201
        assert data["message"] == "创建成功"


class TestErrorResponse:
    def test_basic_error(self):
        resp = error_response()
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data["code"] == 400
        assert data["message"] == "请求错误"
        assert data["data"] is None

    def test_custom_error(self):
        resp = error_response(code=403, message="权限不足")
        assert resp.status_code == 403
        data = json.loads(resp.content)
        assert data["code"] == 403
        assert data["message"] == "权限不足"

    def test_with_data(self):
        resp = error_response(code=422, message="验证失败", data={"field": ["该字段必填"]})
        data = json.loads(resp.content)
        assert data["data"]["field"] == ["该字段必填"]


@pytest.mark.django_db
class TestPaginatedResponse:
    def test_pagination(self, django_user_model):
        from accounts.models import User

        for i in range(25):
            User.objects.create_user(username=f"user{i}", password="Test@1234", role="student")

        def user_serializer(u):
            return {"id": u.id, "username": u.username}

        queryset = User.objects.all().order_by("id")
        resp = paginated_response(queryset, page=1, page_size=10, serializer=user_serializer)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["data"]["total"] == 25
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 10
        assert data["data"]["total_pages"] == 3
        assert len(data["data"]["items"]) == 10

    def test_with_serializer(self, django_user_model):
        from accounts.models import User

        for i in range(5):
            User.objects.create_user(username=f"ser{i}", password="Test@1234", role="student")

        def user_serializer(u):
            return {"id": u.id, "username": u.username}

        queryset = User.objects.all().order_by("id")
        resp = paginated_response(queryset, page=1, page_size=2, serializer=user_serializer)
        data = json.loads(resp.content)
        assert len(data["data"]["items"]) == 2
        assert "id" in data["data"]["items"][0]
        assert "username" in data["data"]["items"][0]
