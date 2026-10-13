from django.http import HttpResponse
from django.urls import path

urlpatterns = [
    path("internal-only/", lambda r: HttpResponse("site a internal")),
]
