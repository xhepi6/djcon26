"""Stock Django admin registration — kept for side-by-side comparison with admin-deux."""

from django.contrib import admin

from .models import Author, Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "email"]
    search_fields = ["first_name", "last_name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "category", "price", "status"]
    list_filter = ["status", "category"]
    search_fields = ["name", "sku"]
