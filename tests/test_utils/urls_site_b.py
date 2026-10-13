from django.http import HttpResponse
from django.urls import path

urlpatterns = [
    path("public/", lambda r: HttpResponse("site b public")),
]
