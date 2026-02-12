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
    is_signed = models.BooleanField(default=False)
    signed_document = models.ImageField(upload_to='static/uploads/amc/assets/')

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

    def is_assignable(self):
        obj = {
            'can_assign':False,
            'message':'ini'
        }

        #chec group compliance
        if AssetGroupComplianceType.objects.filter(asset_group=self.group).exists():
            for gp in AssetGroupComplianceType.objects.all():
                if gp.asset_group == self.group:
                    # check if compliance exist
                    if AssetCompliance.objects.filter(asset=self,compliance_type=gp.compliance_type).exists():
                        obj['can_assign'] = True
                        obj['message'] = "Assign"
                    else:
                        obj['can_assign'] = False
                        obj['message'] = f"Asset requires {gp.compliance_type.name}. use Action > Compliance > New on asset to add"

        else:
            obj['can_assign'] = True
            obj['message'] = "Object Group Has No Compliance"

        return obj

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


class AssetImages(models.Model):
    asset = models.ForeignKey(Asset,on_delete=models.CASCADE)
    image = models.ImageField(upload_to='static/uploads/amc/assets/')
    caption = models.CharField(max_length=255,null=True,blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='asset_images_created')
    created_at = models.DateTimeField(auto_now_add=True)

    def obj(self):
        return {
            'pk': self.pk,
            'asset_pk': self.asset.pk,
            'asset_name': self.asset.name,
            'image': self.image.url,
            'caption': self.caption,
            'created_by': self.created_by.username if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else ""
        }

class GroupCompliance(models.Model):
    document = models.ForeignKey('employee.Documents',on_delete=models.CASCADE)
    group = models.ForeignKey('Groups',on_delete=models.CASCADE)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='compliance_crwator')
    created_at = models.DateTimeField(auto_now_add=True)

    # INSERT_YOUR_CODE
    class Meta:
        unique_together = ('document', 'group')
        # INSERT_YOUR_CODE

class ComplianceAuthority(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    email = models.EmailField(max_length=255, blank=False, null=False)
    contact = models.CharField(max_length=255, blank=False, null=False)
    website = models.URLField(blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=False, null=False)
    phone = models.CharField(max_length=64, blank=False, null=False)
    person_email = models.EmailField(max_length=255, blank=False, null=False)
    logo = models.ImageField(upload_to='static/uploads/amc/compliance_authorities/', blank=True, null=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='ca_created_by')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def obj(self):
        return {
            'pk': self.pk,
            'name': self.name,
            'description': self.description,
            'email': self.email,
            'contact': self.contact,
            'website': self.website,
            'contact_person': self.contact_person,
            'phone': self.phone,
            'person_email': self.person_email,
            'logo': self.logo.url if self.logo else None,
            'created_by': self.created_by.username if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else "",
            'updated_at': self.updated_at.isoformat() if self.updated_at else "",
        }


        # INSERT_YOUR_CODE
class ComplianceType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='compliance_type_created_by')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    managed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='compliance_type_managed_by')
    authority = models.ForeignKey(ComplianceAuthority,on_delete=models.CASCADE,blank=True, null=True)


    def __str__(self):
        return self.name

    def obj(self):
        return {
            'pk': self.pk,
            'name': self.name,
            'description': self.description,
            'created_by': self.created_by.username if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else "",
            'updated_at': self.updated_at.isoformat() if self.updated_at else "",
        }



class AssetGroupComplianceType(models.Model):
    asset_group = models.ForeignKey('Groups',on_delete=models.CASCADE)
    compliance_type = models.ForeignKey('ComplianceType',on_delete=models.CASCADE)
    managed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='managed_by_asset_group')

    class Meta:
        unique_together = ('asset_group', 'compliance_type')

class AssetCompliance(models.Model):
    asset = models.ForeignKey(Asset,on_delete=models.CASCADE)
    compliance_type = models.ForeignKey(ComplianceType,on_delete=models.CASCADE)
    expiry_date = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    reference = models.CharField(max_length=255, blank=True, null=True)
    is_expiry = models.BooleanField(default=False)
    linked_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='linked_by')
    document = models.FileField(upload_to='static/uploads/amc/asset_compliance_assets/', blank=True, null=True)

    class Meta:
        unique_together = ('asset', 'compliance_type')

    def managed_by(self):
    
        # Find the AssetGroupComplianceType for this asset and compliance_type
        return self.compliance_type.managed_by.get_full_name() if self.compliance_type.managed_by else "Not Set"

    def days_to_expire(self):
       
        from datetime import date
        if self.expiry_date:
            # Return remaining time to expire as a human-friendly string (e.g., '5 days', '12 hours', '56 mins')
            from datetime import datetime, timedelta

            if isinstance(self.expiry_date, datetime):
                expire_dt = self.expiry_date
            else:
                # If expiry_date is a date, combine with time.min to make a datetime
                expire_dt = datetime.combine(self.expiry_date, datetime.min.time())

            now = datetime.now()
            delta = expire_dt - now

            if delta.total_seconds() < 0:
                return "Expired"

            days = delta.days
            if days > 0:
                return f"{days} day{'s' if days != 1 else ''}"
            hours = delta.seconds // 3600
            if hours > 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            mins = (delta.seconds % 3600) // 60
            return f"{mins} min{'s' if mins != 1 else ''}"
        else:
            return None

    def obj(self):
        return {
            'pk': self.pk,
            'asset_pk': self.asset.pk,
            'asset_name': self.asset.name,
            'compliance_type': self.compliance_type.name,


        }