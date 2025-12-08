from django.db import models

# assets Groups
class Groups(models.Model):
    name = models.CharField(max_length=100, unique=True,null=False,blank=False)
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='asset_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def obj(self):
        return {
            'pk':self.pk,
            'name':self.name,
            'created_by':self.created_by.username
        }

        # INSERT_YOUR_CODE

# Asset model
class Asset(models.Model):
    group = models.ForeignKey('Groups', on_delete=models.CASCADE, related_name='assets')
    name = models.CharField(max_length=100, unique=False, null=False, blank=False)
    model = models.CharField(max_length=100, null=True, blank=True)
    serial = models.CharField(max_length=100, null=True, blank=True)
    assigned_to = models.ForeignKey('auth.User', on_delete=models.SET_NULL,null=True, related_name='assigned_to')
    is_assgned = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('maintenance', 'Maintenance'),
            ('other', 'Other')
        ],
        default='active'
    )

    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='assets_created')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def obj(self):
        return {
            'pk': self.pk,
            'group': self.group.pk if self.group else None,
            'group_name': self.group.name if self.group else "",
            'name': self.name,
            'model': self.model,
            'serial': self.serial,
            'type': self.type,
            'assigned_to': self.assigned_to.username if self.assigned_to else "",
            'status': self.status,
            'created_by': self.created_by.username if self.created_by else "",
            'created_at': self.created_at.isoformat() if self.created_at else ""
        }

        # INSERT_YOUR_CODE

class AssetTransaction(models.Model):
    ASSET_ACTIONS = [
        
        ('assign', 'Assign'),
        ('transfer', 'Transfer'),
        ('maintenance', 'Maintenance'),
        ('service', 'Service'),
        ('return', 'Return'),
        ('other', 'Other'),
    ]
    asset = models.ForeignKey('Asset', on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField(null=False,blank=False)
    action = models.CharField(max_length=30, choices=ASSET_ACTIONS)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='asset_transactions_performed')
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.asset.name} - {self.action} by {self.performed_by} on {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    def obj(self):
        return {
            'pk': self.pk,
            'asset_pk': self.asset.pk,
            'asset_name': self.asset.name,
            'action': self.action,
            'performed_by': self.performed_by.username if self.performed_by else None,
            'assigned_to': self.assigned_to.username if self.assigned_to else None,
            'date': self.date.isoformat() if self.date else "",
            'notes': self.notes or ""
        }


class AssetSpecifications(models.Model):
    asset = models.ForeignKey(Asset,on_delete=models.CASCADE)
    key = models.CharField(max_length=255,null=False)
    value = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='specification_adder')

    def obj(self):
        return {
            'pk': self.pk,
            'asset_pk': self.asset.pk,
            'asset_name': self.asset.name,
            'key': self.key,
            'value': self.value,
            'timestamp': self.timestamp.isoformat() if self.timestamp else "",
            'added_by': self.added_by.username if self.added_by else None
        }


