from django.urls import path

from .api import parse_markup, preview_markup

urlpatterns = [
    path("parse-markup/", parse_markup, name="parse-markup"),
    path("preview-markup/", preview_markup, name="preview-markup"),
]
