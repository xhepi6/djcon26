from django.db import models


class Account(models.Model):
    name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} (${self.balance})"


class TransferLog(models.Model):
    """Records a completed transfer between two accounts."""
    from_account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="outgoing_transfers"
    )
    to_account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="incoming_transfers"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"${self.amount}: {self.from_account.name} -> {self.to_account.name}"
