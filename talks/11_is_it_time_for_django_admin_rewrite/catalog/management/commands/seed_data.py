"""Populate the database with sample categories, authors, and products."""

from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Author, Category, Product


class Command(BaseCommand):
    help = "Seed the database with sample catalog data"

    def handle(self, *args, **options):
        # Categories
        categories = {}
        for name, slug in [
            ("Books", "books"),
            ("Electronics", "electronics"),
            ("Clothing", "clothing"),
            ("Food & Drink", "food-drink"),
        ]:
            cat, created = Category.objects.get_or_create(
                slug=slug, defaults={"name": name, "description": f"All {name.lower()} products"}
            )
            categories[slug] = cat
            status = "created" if created else "exists"
            self.stdout.write(f"  Category: {name} ({status})")

        # Authors
        authors = {}
        for first, last, email in [
            ("Ada", "Lovelace", "ada@example.com"),
            ("Grace", "Hopper", "grace@example.com"),
            ("Guido", "van Rossum", "guido@example.com"),
        ]:
            author, created = Author.objects.get_or_create(
                first_name=first,
                last_name=last,
                defaults={"email": email, "bio": f"Author and creator of many things."},
            )
            authors[last.lower()] = author
            status = "created" if created else "exists"
            self.stdout.write(f"  Author: {first} {last} ({status})")

        # Products
        products = [
            ("Two Scoops of Django", "BOOK-001", "books", "lovelace", Decimal("49.99"), Product.Status.ACTIVE),
            ("Django for Professionals", "BOOK-002", "books", "hopper", Decimal("39.99"), Product.Status.ACTIVE),
            ("Lightweight Django", "BOOK-003", "books", "van rossum", Decimal("34.99"), Product.Status.DRAFT),
            ("Mechanical Keyboard", "ELEC-001", "electronics", None, Decimal("149.99"), Product.Status.ACTIVE),
            ("USB-C Hub", "ELEC-002", "electronics", None, Decimal("59.99"), Product.Status.ACTIVE),
            ("Floppy Disk Drive", "ELEC-003", "electronics", None, Decimal("9.99"), Product.Status.DISCONTINUED),
            ("Python T-Shirt", "CLTH-001", "clothing", None, Decimal("24.99"), Product.Status.ACTIVE),
            ("Django Hoodie", "CLTH-002", "clothing", None, Decimal("54.99"), Product.Status.DRAFT),
            ("Artisan Coffee Beans", "FOOD-001", "food-drink", None, Decimal("18.99"), Product.Status.ACTIVE),
            ("Belgian Chocolate", "FOOD-002", "food-drink", None, Decimal("12.99"), Product.Status.ACTIVE),
        ]

        for name, sku, cat_slug, author_key, price, status in products:
            author = authors.get(author_key) if author_key else None
            product, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": categories[cat_slug],
                    "author": author,
                    "price": price,
                    "status": status,
                    "description": f"Sample product: {name}",
                },
            )
            label = "created" if created else "exists"
            self.stdout.write(f"  Product: {name} [{sku}] ({label})")

        self.stdout.write(self.style.SUCCESS("\nDone! Sample data is ready."))
        self.stdout.write(
            "\nTry:\n"
            "  http://localhost:8000/admin/     (stock admin)\n"
            "  http://localhost:8000/djadmin/   (admin-deux)\n"
        )
