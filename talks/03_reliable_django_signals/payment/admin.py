from django.contrib import admin

from payment.models import PaymentProcess


@admin.register(PaymentProcess)
class PaymentProcessAdmin(admin.ModelAdmin):
    list_display = ("id", "amount", "status")
    list_filter = ("status",)
    readonly_fields = ("id",)
