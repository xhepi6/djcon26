from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from bookmarks.models import Bookmark


BOOKMARKS = [
    {"url": "https://docs.djangoproject.com/", "title": "Django Docs", "comment": "Official documentation", "favourite": True},
    {"url": "https://noumenal.es/mantle/", "title": "Mantle Docs", "comment": "Carlton Gibson's typed ORM layer", "favourite": True},
    {"url": "https://github.com/dabapps/django-readers", "title": "django-readers", "comment": "Under the hood of Mantle", "favourite": False},
    {"url": "https://www.attrs.org/", "title": "attrs", "comment": "Python classes without boilerplate", "favourite": False},
    {"url": "https://www.django-rest-framework.org/", "title": "DRF Docs", "comment": "REST framework docs", "favourite": True},
    {"url": "https://pypi.org/project/cattrs/", "title": "cattrs", "comment": "Structured/unstructured conversion", "favourite": False},
]


class Command(BaseCommand):
    help = "Seed bookmarks and users for testing Mantle shapes"

    def handle(self, *args, **options):
        alice, _ = User.objects.get_or_create(username="alice", defaults={"email": "alice@example.com"})
        bob, _ = User.objects.get_or_create(username="bob", defaults={"email": "bob@example.com"})
        users = [alice, bob]

        created = 0
        for i, data in enumerate(BOOKMARKS):
            _, was_created = Bookmark.objects.get_or_create(
                url=data["url"],
                defaults={**data, "user": users[i % len(users)]},
            )
            if was_created:
                created += 1

        self.stdout.write(f"Users: {User.objects.count()}")
        self.stdout.write(f"Bookmarks: {Bookmark.objects.count()} ({created} new)")
        for b in Bookmark.objects.select_related("user").all():
            self.stdout.write(f"  [{b.user.username}] {b.title} — {b.url}")
