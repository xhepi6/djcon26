"""Django-Admin-Deux registration — compare this with admin.py to see the differences.

Key things to notice:
- Same @register decorator pattern, just imported from djadmin
- Column objects add filtering, ordering, and styling inline with list_display
- Layout objects replace fieldsets with a composable, nested structure
- Plugins (filters, formset) are auto-discovered — no manual wiring needed
"""

from djadmin import Column, Field, Fieldset, Layout, ModelAdmin, Row, register
from djadmin.dataclasses import Filter

from .models import Author, Category, Product


# --- Simple registration (near-identical to stock admin) ---


@register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name"]


# --- Form layout customization ---


@register(Author)
class AuthorAdmin(ModelAdmin):
    list_display = [
        Column("first_name", order=True),
        Column("last_name", order=True),
        "email",
    ]
    search_fields = ["first_name", "last_name"]

    # Layout replaces stock admin's fieldsets with composable, nested structure
    layout = Layout(
        Fieldset(
            "Personal Information",
            Row(
                Field("first_name", css_classes=["flex-1", "pr-2"]),
                Field("last_name", css_classes=["flex-1", "pl-2"]),
            ),
            Field("email"),
            Field("birth_date", label="Date of Birth"),
        ),
        Fieldset(
            "Biography",
            Field("bio", widget="textarea", attrs={"rows": 6}),
        ),
    )


# --- Enhanced list_display with Column objects ---


@register(Product)
class ProductAdmin(ModelAdmin):
    list_display = [
        # Plain string — works like stock admin
        "name",
        # Column with custom label and CSS class
        Column("sku", label="SKU Code", classes="font-mono"),
        # Boolean shorthand: filter=True gives exact-match, order=True adds sort
        Column("category", filter=True, order=True),
        # Filter with lookup expressions for range queries (price >= X, price <= Y)
        Column("price", order=True, filter=Filter(lookup_expr=["gte", "lte"])),
        # Simple filterable column
        Column("status", filter=True),
        Column("created_at", order=True),
    ]
    search_fields = ["name", "sku"]
