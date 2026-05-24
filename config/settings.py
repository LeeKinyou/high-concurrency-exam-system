"""Settings entry point - imports from settings package."""
import os

env = os.environ.get("DJANGO_ENV", "development")

if env == "production":
    from config.settings.production import *  # noqa: F401, F403
elif env == "testing":
    from config.settings.testing import *  # noqa: F401, F403
else:
    from config.settings.development import *  # noqa: F401, F403
