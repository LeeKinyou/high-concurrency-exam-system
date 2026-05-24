import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def teacher(db):
    return User.objects.create_user(
        username="teacher01",
        password="Test@1234",
        role="teacher",
        first_name="张老师",
    )


@pytest.fixture
def student(db):
    return User.objects.create_user(
        username="student01",
        password="Test@1234",
        role="student",
        student_id="2024001",
        first_name="李同学",
    )


@pytest.fixture
def teacher_client(client, teacher):
    client.login(username="teacher01", password="Test@1234")
    return client


@pytest.fixture
def student_client(client, student):
    client.login(username="student01", password="Test@1234")
    return client
