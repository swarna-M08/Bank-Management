from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.views.generic import CreateView, ListView
from transactions.constants import DEPOSIT, WITHDRAWAL, LOAN, LOAN_PAID, TRANSFER_MONEY
from datetime import datetime
from django.db.models import Sum
from transactions.forms import (
    DepositForm,
    WithdrawForm,
    LoanRequestForm,
    TransferMoneyForm,
)
from transactions.models import Transaction, Bankrupt
from accounts.models import UserBankAccount


# jehetu proti bar form fill up kre transaction krchi tai createview
class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = "transactions/transaction_form.html"
    model = Transaction
    title = ""
    success_url = reverse_lazy("transaction_report")

    # currently logged in user er data jate forms.py e balance r transaction related kaj krte pari
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"account": self.request.user.account})
        return kwargs

    # template e context data pass kora
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"title": self.title})

        return context


class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = "Deposit"

    # eta j Deposit type transaction seta backend thk bole dilam
    def get_initial(self):
        initial = {"transaction_type": DEPOSIT}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")
        account = self.request.user.account
        if Bankrupt.objects.filter(bank_rupt=True).exists():
            messages.error(self.request, f"Sorry the bank is bankrupted this time!")
            return redirect("transaction_report")
        account.balance += amount
        account.save(update_fields=["balance"])

        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully',
        )

        return super().form_valid(form)


class WithdrawMoneyView(TransactionCreateMixin):
    form_class = WithdrawForm
    title = "Withdraw Money"

    def get_initial(self):
        initial = {"transaction_type": WITHDRAWAL}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")
        if Bankrupt.objects.filter(bank_rupt=True).exists():
            messages.error(self.request, f"Sorry the bank is bankrupted this time!")
            return redirect("transaction_report")
        self.request.user.account.balance -= form.cleaned_data.get("amount")
        self.request.user.account.save(update_fields=["balance"])

        messages.success(
            self.request,
            f'Successfully withdrawn {"{:,.2f}".format(float(amount))}$ from your account',
        )

        return super().form_valid(form)


class LoanRequestView(TransactionCreateMixin):
    form_class = LoanRequestForm
    title = "Request For Loan"

    def get_initial(self):
        initial = {"transaction_type": LOAN}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")
        current_loan_count = Transaction.objects.filter(
            account=self.request.user.account, transaction_type=3, loan_approve=True
        ).count()
        if Bankrupt.objects.filter(bank_rupt=True).exists():
            messages.error(self.request, f"Sorry the bank is bankrupted this time!")
            return redirect("transaction_report")
        if current_loan_count >= 3:
            return HttpResponse("You have cross the loan limits")
        messages.success(
            self.request,
            f'Loan request for {"{:,.2f}".format(float(amount))}$ submitted successfully',
        )

        return super().form_valid(form)


class TransactionReportView(LoginRequiredMixin, ListView):
    template_name = "transactions/transaction_report.html"
    model = Transaction
    balance = 0  # filter korar pore ba age amar total balance ke show korbe

    def get_queryset(self):
        queryset = super().get_queryset().filter(account=self.request.user.account)
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            queryset = queryset.filter(
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            )
            self.balance = Transaction.objects.filter(
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            ).aggregate(Sum("amount"))["amount__sum"]
        else:
            self.balance = self.request.user.account.balance

        return queryset.distinct()  # unique queryset hote hobe

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"account": self.request.user.account})

        return context


class PayLoanView(LoginRequiredMixin, View):
    # loan er id diye get krte hbe
    def get(self, request, loan_id):
        loan = get_object_or_404(Transaction, id=loan_id)
        if loan.loan_approve:
            user_account = loan.account
            if loan.amount < user_account.balance:
                user_account.balance -= loan.amount
                loan.balance_after_transaction = user_account.balance
                user_account.save()
                loan.loan_approved = True
                loan.transaction_type = LOAN_PAID
                loan.save()
                return redirect("loan_list")
            else:
                messages.error(
                    self.request, f"Loan amount is greater than available balance"
                )

        return redirect("loan_list")


class LoanListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "transactions/loan_request.html"
    context_object_name = "loans"  # loan list ta ei loans context er moddhe thakbe

    def get_queryset(self):
        user_account = self.request.user.account
        if Bankrupt.objects.filter(bank_rupt=True).exists():
            messages.error(self.request, f"Sorry the bank is bankrupted this time!")
            return redirect("transaction_report")
        else:
            queryset = Transaction.objects.filter(
                account=user_account, transaction_type=3
            )
            return queryset


class TransferMoneyView(TransactionCreateMixin):
    form_class = TransferMoneyForm
    title = "Transfer Money"

    def get_initial(self):
        initial = {"transaction_type": TRANSFER_MONEY}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")
        transfer_account_no = form.cleaned_data.get("transfer_account_no")

        if Bankrupt.objects.filter(bank_rupt=True).exists():
            messages.error(self.request, f"Sorry the bank is bankrupted this time!")
            return redirect("transaction_report")
        else:
            try:
                transfer_account = UserBankAccount.objects.get(
                    account_no=transfer_account_no
                )
            except UserBankAccount.DoesNotExist:
                messages.error(
                    self.request,
                    f"Transfer account not found!",
                )
                return redirect("transaction_report")
            self.request.user.account.balance -= amount
            transfer_account.balance += amount
            self.request.user.account.save(update_fields=["balance"])
            transfer_account.save(update_fields=["balance"])

            messages.success(
                self.request,
                f'Successfully transferred {"{:,.2f}".format(float(amount))}$ to account {transfer_account_no}',
            )
            return super().form_valid(form)