from django.db import models
from accounts.models import UserBankAccount
from .constants import TRANSACTION_TYPE


class Bankrupt(models.Model):
    bank_rupt = models.BooleanField(default=False)

    def __str__(self):
        return f"Bank Rupted"


class Transaction(models.Model):
    account = models.ForeignKey(
        UserBankAccount, related_name="transactions", on_delete=models.CASCADE
    )

    amount = models.DecimalField(decimal_places=2, max_digits=12)
    balance_after_transaction = models.DecimalField(decimal_places=2, max_digits=12)
    transaction_type = models.IntegerField(choices=TRANSACTION_TYPE, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    loan_approve = models.BooleanField(default=False)
    transfer_account_no = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["timestamp"]