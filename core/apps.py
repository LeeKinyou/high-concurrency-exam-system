from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        from django.db.backends.signals import connection_created

        def set_sqlite_pragma(sender, connection, **kwargs):
            if connection.vendor == "sqlite":
                cursor = connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=5000")

        connection_created.connect(set_sqlite_pragma)
