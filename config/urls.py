from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def index(request):
    return redirect("/accounts/login/")


urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("exams/", include("examination.urls")),
    path("teacher/", include("examination.teacher_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
