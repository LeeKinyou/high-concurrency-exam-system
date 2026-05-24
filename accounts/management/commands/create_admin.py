from django.core.management.base import BaseCommand

from core.constants import UserRole
from core.utils import generate_random_password

from accounts.models import User


class Command(BaseCommand):
    help = "Create a teacher admin user"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default="admin")
        parser.add_argument("--password", type=str, default=None)
        parser.add_argument("--name", type=str, default="管理员")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"] or generate_random_password(16)
        name = options["name"]

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists."))
            return

        User.objects.create_user(
            username=username,
            password=password,
            role=UserRole.TEACHER,
            first_name=name,
            is_staff=True,
            is_superuser=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Admin user created: {username} / {password}"))
