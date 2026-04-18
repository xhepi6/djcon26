from django.contrib import admin

from order.models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "amount", "status", "payment_process")
    list_filter = ("status",)
    readonly_fields = ("id",)
