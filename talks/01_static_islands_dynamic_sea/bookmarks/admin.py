from django.contrib import admin

from .models import Bookmark


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "user", "favourite", "created_at")
    list_filter = ("favourite", "user")
