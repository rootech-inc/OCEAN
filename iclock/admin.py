from django.contrib import admin

# Register your models here.
# admin.py
from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.utils import timezone
from .models import Device

class BackfillForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Backfill from date"
    )

class DeviceAdmin(admin.ModelAdmin):
    list_display = ['serial_number', 'ip_address', 'last_log_sync', 'needs_backfill']
    actions      = ['trigger_backfill']

    @admin.action(description="Trigger attendance backfill for selected devices")
    def trigger_backfill(self, request, queryset):
        if 'apply' in request.POST:
            form = BackfillForm(request.POST)
            if form.is_valid():
                start_dt = timezone.make_aware(
                    timezone.datetime.combine(
                        form.cleaned_data['start_date'],
                        timezone.datetime.min.time()
                    )
                )
                updated = queryset.update(
                    needs_backfill=True,
                    backfill_from=start_dt
                )
                self.message_user(request, f"Backfill scheduled for {updated} device(s) from {form.cleaned_data['start_date']}")
                return
        else:
            form = BackfillForm()

        return render(request, 'admin/backfill_action.html', {
            'form':     form,
            'devices':  queryset,
            'action':   'trigger_backfill',
        })

admin.site.register(Device, DeviceAdmin)