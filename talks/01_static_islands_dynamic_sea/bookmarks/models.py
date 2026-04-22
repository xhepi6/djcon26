from django.contrib.auth.models import User
from django.db import models


class Bookmark(models.Model):
    url = models.URLField()
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    favourite = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or self.url
