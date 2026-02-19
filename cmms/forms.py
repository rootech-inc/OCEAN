from django import forms

from cmms.models import Customers, CustomerTransactions


class NewSalesCustomer(forms.ModelForm):
    class Meta:
        model = Customers
        exclude = ['created_date', 'created_time', 'updated_date', 'updated_time', 'status']


class NewSaleTransactions(forms.ModelForm):
    class Meta:
        model = CustomerTransactions
        exclude = ['created_date', 'created_time', 'updated_date', 'updated_time', 'status']
