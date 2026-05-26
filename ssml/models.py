import os
from datetime import datetime
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce

from accounts.models import Ledger
from admin_panel.anton import format_currency
from admin_panel.models import BankAccounts
from django.utils import timezone

from ocean.settings import TAX_RATE, SSML_SERVICE_RATE, COMPANY_DETAILS, WHT_RATE


# locations class
class Location(models.Model):
    loc_id = models.CharField(max_length=255,unique=True,blank=False,null=False)
    loc_name = models.CharField(max_length=255,unique=True,blank=False,null=False)
    loc_desc = models.CharField(max_length=255,unique=True,blank=False,null=False)
    country = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    street = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    email = models.CharField(max_length=255)

    date_created = models.DateField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)

    is_default =models.BooleanField(default=False)

    boxing_file_link = models.TextField(default='not set')
    boxing_auth_file = models.FileField(upload_to='static/uploads/files/ssml_docs/')

    def auth_file_path(self):
        if self.boxing_auth_file and hasattr(self.boxing_auth_file, 'path'):
            import os
            if os.path.exists(self.boxing_auth_file.path):
                return self.boxing_auth_file.url.lstrip('/')
        return None

    def obj(self):
        return {
            'pk':self.id,
            'name':self.loc_name,
            'loc_id':self.loc_id,
            'country':self.country,
            'city':self.city,
            'street':self.street,
            'address':self.address,
            'phone':self.phone,
            'email':self.email,
            'default':self.is_default
        }


# Create your models here.
class InventoryGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def obj(self):
        return {
            'id':self.id,
            'name':self.name,
            'created_at':self.created_at,
            'updated_at':self.updated_at
        }
    
class InventoryMaterial(models.Model):
    barcode = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, unique=True)
    group = models.ForeignKey(InventoryGroup, on_delete=models.CASCADE)
    reorder_qty = models.IntegerField(default=0)
    status_choices = [
        ('stock', 'Stock'),
        ('low', 'Low'),
        ('out', 'Out'),
    ]
    status = models.CharField(max_length=255, choices=status_choices, default='stock')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='static/uploads/materials/', null=True, blank=True,default='static/uploads/materials/default.png')
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_return = models.BooleanField(default=False)
    is_issue = models.BooleanField(default=False)
    issue_qty = models.DecimalField(max_digits=10,default=0.00, decimal_places=2)
    auto_issue = models.BooleanField(default=False)
    uom = models.CharField(max_length=255, default='PCS',blank=False,null=False)
    required_qty = models.DecimalField(max_digits=10,default=0.00, decimal_places=2)
    is_billable = models.BooleanField(default=False)


    item_type_choices = [
        ('pri',"Primary"),
        ('gen',"General")
    ]
    item_type = models.CharField(max_length=255, choices=item_type_choices, default='gen')
    def __str__(self):
        return self.name
    
    def obj(self):
        return {
            'id':self.id,
            'required_qty':self.required_qty,
            'barcode':self.barcode,
            'name':self.name,
            'group':self.group.obj(),
            'reorder_qty':self.reorder_qty,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'is_active':self.is_active,
            'status':self.stock_level(),
            'stock':self.stock(),
            'low':self.low(),
            'out':self.out(),
            'image':self.image.url if self.image else None,
            'value':self.value,
            'issue_qty':self.issue_qty,
            'is_issue':self.is_issue,
            'is_return':self.is_return,
            'stock_in':self.stock_in(),
            'stock_out':self.stock_out(),
            'next':InventoryMaterial.objects.filter(id__gt=self.id).first().id if InventoryMaterial.objects.filter(id__gt=self.id).count() > 0 else 0,
            'prev':InventoryMaterial.objects.filter(id__lt=self.id).last().id if InventoryMaterial.objects.filter(id__lt=self.id).count() > 0 else 0,
            'auto_issue':self.auto_issue,
            'service_rates':self.service_rates(),
            'loc_stock':self.loc_stock(),
            'services':self.services(),
            'is_billable':self.is_billable
        }
    
    def service_rates(self):
        return [rt.obj() for rt in ServiceMaterialRates.objects.filter(material=self)]
    
    def services(self):
        return [x.obj() for x in ServiceMaterials.objects.filter(material=self)]

    def stock(self, as_of='*',loc_id='*'):
        
        if as_of == '*':

            # build location filter depending on loc_id
            if loc_id == '*':
                location_filter = {'location__in': Location.objects.all()}
            else:
                location_filter = {'location': Location.objects.get(loc_id=loc_id)}

            # single query for all doc_types
            totals_qs = (
                Cardex.objects.filter(material=self, doc_type__in=['ISS', 'GR', 'RET','TRF'], **location_filter)
                .values('doc_type')
                .annotate(total_qty=Sum('qty'))
            )

            # convert result into a dictionary {doc_type: total_qty}
            totals = {row['doc_type']: row['total_qty'] or 0 for row in totals_qs}

            # safely fetch values (default 0 if not present)
            total_ISS = totals.get('ISS', 0)
            total_GR = totals.get('GR', 0)
            total_RET = totals.get('RET', 0)
            total_TRF = totals.get('TRF',0)

            # issue is out - retuen
            # print(self.name)
            # print("GRN",total_GR)
            # print('ISS',total_ISS)
            # print("RETURN",total_RET)
            total_issue = Decimal(total_ISS) + Decimal(total_RET)
            # print("TOT ISS",total_issue)
            
            
            total = Decimal(total_GR) + Decimal(total_issue)
            # print("TOT",total)
            # print()
            
            return total
        else:
            if loc_id == '*':
                location_filter = {'location__in': Location.objects.all()}
            else:
                location_filter = {'location': Location.objects.get(loc_id=loc_id)}

            return (
                    Cardex.objects.filter(
                        material=self,
                        created_at__lte=as_of,
                        **location_filter
                    ).aggregate(total_qty=Sum('qty'))['total_qty'] or 0
            )

    def loc_stock(self,loc_id='*'):
        locations = Location.objects.all() if loc_id == '*' else Location.objects.filter(loc_id=loc_id)
        arr = []
        for loc in locations:
            arr.append({
                'location': loc.loc_name,
                'loc_id':loc.id,
                'general_in': Cardex.objects.filter(material=self, location=loc, qty__gt=0).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0,
                'total_in': Cardex.objects.filter(material=self, location=loc, qty__gt=0,doc_type__in=['GR','TRF']).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0,
                'total_out': Cardex.objects.filter(material=self, location=loc, qty__lt=0,doc_type__in=['ISS','TRF']).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0,
                'total_consumed': MaterialOrderItem.objects.filter(
                    material=self,
                    material_type='is',
                    service_order__location=loc)
                    .aggregate(total_qty=Sum('quantity'))['total_qty'] or 0,
                'stock': Cardex.objects.filter(material=self, location=loc).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
            })
        return arr

    def low(self):
        return Cardex.objects.filter(material=self).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
    def out(self):
        return Cardex.objects.filter(material=self).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0

    def in_by_date_range(self,start_date,end_date):
        print(
            "Material: ",self.name,
            "\nStart Date:",start_date,
            "\nEnd Date:",end_date,
        )
        total =  Cardex.objects.filter(
            material=self,
            created_at__gte=start_date,
            created_at__lte=end_date,
            doc_type='GR'
            ).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
        print(
            "Material: ", self.name,
            "\nStart Date:", start_date,
            "\nEnd Date:", end_date,
            "\nTotal Received:", total,
        )

        return total

    def used_by_date_range(self,start_date,end_date,is_boxed=False):
        return MaterialOrderItem.objects.filter(
            material=self,
            service_order__service_date__gte=start_date,
            service_order__service_date__lte=end_date,
            material_type='is'
            ).aggregate(total_qty=models.Sum('quantity'))['total_qty'] or 0
    
    def cardex(self,loc='*'):
        obj = []
        if loc == '*':
            cardex = Cardex.objects.filter(material=self).order_by('created_at')
        else:
            location = Location.objects.get(id=loc)
            cardex = Cardex.objects.filter(material=self,location=location).order_by('created_at')
        for item in cardex:
            obj.append(item.obj())
            
        return obj

    def in_and_out(self,as_of,loc_id='*'):
        if loc_id == '*':
            location_filter = {'location__in': Location.objects.all()}
        else:
            location_filter = {'location': Location.objects.get(loc_id=loc_id)}

        in_trans = Cardex.objects.filter(
                material=self,
                created_at__lte=as_of,
                **location_filter,qty__gt=0
            ).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
        out_trans = Cardex.objects.filter(
                material=self,
                created_at__lte=as_of,
                **location_filter,qty__lt=0
            ).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
        return {
            'in_trans': in_trans,
            'out_trans': out_trans,
            'balance':in_trans + out_trans
        }
            

    def stock_in(self):
        grn = Cardex.objects.filter(material=self,doc_type='GR').aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
        tr = Cardex.objects.filter(material=self, doc_type='TRF', qty__gt=0).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
        #returns = Cardex.objects.filter(material=self,doc_type='RET').aggregate(total_qty=models.Sum('qty'))['total_qty']  or 0
        #xr = returns * -1
        #return grn + xr
        
        return grn + tr
    def stock_out(self):
        issue = Cardex.objects.filter(material=self,doc_type='ISS').aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0
        return issue
    
    def stock_level(self):
        stock = self.stock()
        if self.reorder_qty >= stock:
            return "out"
        elif self.reorder_qty <= stock:
            return "stock"
        else:
            return "low"
    
class Contractor(models.Model):
    company = models.CharField(max_length=255, unique=True)
    owner = models.CharField(max_length=255)
    phone = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    country = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=255)
    gh_post_code = models.CharField(max_length=255)
    gh_card_no = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    link = models.CharField(max_length=255)
    recievable = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payable = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    code = models.CharField(max_length=255, unique=False, null=True, blank=True)
    otp = models.CharField(max_length=6, null=True, blank=True)
    is_installer = models.BooleanField(default=True)
    debit_ledger = models.ForeignKey(Ledger,on_delete=models.PROTECT,null=True, blank=True)
    owner_phone = models.CharField(max_length=10,null=True,blank=True)
    owner_email = models.CharField(max_length=255,null=True,blank=True)
    comp_reg_number = models.CharField(max_length=255,null=True,blank=True)
    business_type = models.CharField(max_length=255,null=True,blank=True)
    region = models.CharField(max_length=255,null=True,blank=True)
    business_address = models.CharField(max_length=255,null=True,blank=True)
    business_phone_number = models.CharField(max_length=255,null=True,blank=True)
    business_email = models.CharField(max_length=255,null=True,blank=True)
    bank_name = models.CharField(max_length=255,null=True,blank=True)
    bank_acct_number = models.CharField(max_length=255,null=True,blank=True)
    bank_branch = models.CharField(max_length=255,null=True,blank=True)


    def __str__(self):
        return self.company

    def can_work(self):
        if ContractorError.objects.filter(contractor=self,is_cleared=False).exists():
            return False
        else:
            return True

    def last_active_date(self):
        order = ServiceOrder.objects.filter(contractor=self).order_by('-service_date').first()
        return order.service_date if order else None

    def last_seen_days(self):
        from datetime import date
        last_date = self.last_active_date()
        if not last_date:
            return None
        days = (date.today() - last_date).days
        if days == 0:
            return "Today"
        if days == 1:
            return "Yesterday"
        if days < 7:
            return f"{days} days ago"
        if days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        if days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        years = days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"

    def error_limit(self):
        return {
            'week': 3,
            'month': 10,
            'year': 20,
        }


    
    def next_row(self):
        return Contractor.objects.filter(id__gt=self.id).first().id if Contractor.objects.filter(id__gt=self.id).count() > 0 else 0
    def prev_row(self):
        return Contractor.objects.filter(id__lt=self.id).last().id if Contractor.objects.filter(id__lt=self.id).count() > 0 else 0
    
    def ledger_sum(self):
        from ssml.helper import returns,lederhd
        return lederhd(self.id)
    
        ledger = Ledger.objects.filter(contractor=self,transaction_type='credit')
        total_credit = ledger.aggregate(total_credit=Sum('amount'))['total_credit'] or 0
        total_debit = returns(self.id)['total']
        total_balance = total_credit + total_debit
        return {
                    'total_credit':total_credit,
                    'total_debit':total_debit,
                    'total_balance':total_balance
            }


    def issued(self):
        iss = Issue.objects.filter(contractor=self)
        return [x.obj() for x in iss]

    def my_jobs(self):
        obj = {}
        for st in ServiceType.objects.all():
            total = 0
            jobs = ServiceOrder.objects.filter(contractor=self,service_type=st).order_by('service_date')
            total = jobs.count()
            this_arr = [j.obj() for j in jobs]
            obj[st.name] = {
                'total':total,'transactions':this_arr
            }
        
        return obj

    def minimal_obj(self):
        return {
            "foc_code":self.code,
            "company":self.company,
            "owner":self.owner,

            "phone":self.phone,
            "email":self.email,
            "country":self.country,

            "city":self.city,
            "postal_code":self.postal_code,
            "gh_post_code":self.gh_post_code,

            "gh_card_no":self.gh_card_no,
            "link":self.link,
            "owner_phone":self.owner_phone,

            "owner_email":self.owner_email,
            "comp_reg_number":self.comp_reg_number,
            "business_type":self.business_type,

            "region":self.region,
            "business_address":self.business_address,
            "business_phone_number":self.business_phone_number,

            "business_email":self.business_email,
            "bank_name":self.bank_name,
            "bank_acct_number":self.bank_acct_number,
            "bank_branch":self.bank_branch,
            'can_work':self.can_work(),
            'is_complied':self.is_complied(),
            'complete_profile':self.profile_complete()
        }

    def documents(self):

        return [doc.obj() for doc in ContractorDocuments.objects.filter(contractor=self)]

    def total_issued_meters(self):

        return IssueTransaction.objects.filter(material__item_type='pri',issue__contractor=self).aggregate(total = Sum('total_qty'))['total']

    def total_jobs(self):
        jobs = {}
        for service_type in ServiceType.objects.all():
            jobs.update({service_type.name:ServiceOrder.objects.filter(contractor=self,service_type=service_type).count()})
        jobs.update({'total':sum(jobs.values())})
        return jobs
    
    def on_average(self):
        # Get all service orders for this contractor
        service_orders = ServiceOrder.objects.filter(contractor=self)

        # Get unique dates
        unique_dates = service_orders.values('service_date').distinct().count()

        if unique_dates == 0:
            return 0

        # Total number of installations
        total_installations = service_orders.count()

        # Calculate average installations per day
        avg_per_day = total_installations / unique_dates if unique_dates > 0 else 0

        return round(avg_per_day, 2)
    
    def jobs_by_month(self):
            from django.db.models.functions import ExtractMonth
            from django.db.models import Count
            current_year = timezone.now().year
            current_month = timezone.now().month
            monthly_jobs = (
                ServiceOrder.objects.filter(
                    contractor=self,
                    service_date__year=current_year
                )
                .annotate(month=ExtractMonth('service_date'))
                .values('month')
                .annotate(count=Count('id'))
                .order_by('month')
            )

            months = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }

            result = {}
            for month_num in range(1, current_month + 1):  # Only iterate up to current month
                month_jobs = next((item for item in monthly_jobs if item['month'] == month_num), None)
                result[months[month_num]] = month_jobs['count'] if month_jobs else 0
        
            return result

    def obj(self):
        return {
            'id':self.id,
            'company':self.company,
            'owner':self.owner,
            'phone':self.phone,
            'email':self.email,
            'country':self.country,
            'city':self.city,
            'postal_code':self.postal_code,
            'gh_post_code':self.gh_post_code,
            'gh_card_no':self.gh_card_no,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'created_by':self.created_by.username,
            'link':self.link,
            'next_row':self.next_row(),
            'prev_row':self.prev_row(),
            # 'materials':self.materials(),
            # 'returns':self.returns(),
            'recievable':self.recievable,
            'payable':self.payable,
            'paid':self.paid,
            'balance':self.balance,
            # 'matched':self.matched(),
            'ledger':0, #self.ledger_sum(),
            'code':self.code,
            'can_work':self.can_work(),
            'jobs':self.total_jobs(),
            'total_issued':self.total_issued_meters(),
            'daily_average':self.on_average(),
            'jobs_by_month':self.jobs_by_month(),
            'owner_phone':self.owner_phone,
            'owner_email':self.owner_email,
            'comp_reg_number':self.comp_reg_number,
            'business_type':self.business_type,
            'region':self.region,
            'business_address':self.business_address,
            'business_phone_number':self.business_phone_number,
            'bank_name':self.bank_name,
            'bank_acct_number':self.bank_acct_number,
            'bank_branch':self.bank_branch,
            'pending_compliance':self.pending_compliance()
            
        }

    def dashboard(self,star_date='2000-01-01',end_date=timezone.now().date()):
        bd = {}
        for st in InstallationType.objects.all():
            bd[st.name] = ServiceOrder.objects.filter(
                contractor=self,
                service_date__gt=star_date,
                service_date__lte=end_date,
                installation_type=st
            ).count()
        return {
            'total_installed':ServiceOrder.objects.filter(contractor=self,service_date__gte=star_date,service_date__lte=end_date).count(),
            'install_types':bd
        }

    def waybill(self, start_date='2000-01-01',end_date=timezone.now().date()):
        obj = []
        for issue in Issue.objects.filter(contractor=self,issue_date__gte=start_date,issue_date__lte=end_date).order_by('issue_date'):
            obj.append({
                'id': issue.id,
                'issue_no': issue.issue_no,
                'issue_date': issue.issue_date,
                'remarks': issue.remarks,
                'created_by': issue.created_by.username,
                'created_at': issue.created_at,
                'updated_at': issue.updated_at,
                'issue_type': issue.issue_type,
            })

        return obj

    def invoices(self, start_date, end_date):
        ob = []
        for invoice in FocInvoiceHd.objects.filter(foc=self,invoice_date__gte=start_date,invoice_date__lte=end_date,is_valid=True).order_by('invoice_date'):
            ob.append(invoice.obj())

        return ob

    def inventory(self):
        materials = InventoryMaterial.objects.filter(is_issue=True).order_by('name')

        # Pre-aggregate outside the loop — 2 queries total regardless of material count
        issued_map = {
            row['material']: row['total']
            for row in IssueTransaction.objects.filter(
                material__in=materials,
                issue__contractor=self
            ).values('material').annotate(
                total=Coalesce(Sum('total_qty'), Value(0, output_field=DecimalField()))
            )
        }

        used_map = {
            row['material']: row['quantity']
            for row in MaterialOrderItem.objects.filter(
                material__in=materials,
                service_order__contractor=self,
                material_type='is'
            ).values('material').annotate(
                quantity=Coalesce(Sum('quantity'), Value(0, output_field=DecimalField()))
            )
        }

        arr = []
        total_balance = 0
        for material in materials:
            total_issued = issued_map.get(material.pk, Decimal('0'))
            total_used = used_map.get(material.pk, Decimal('0'))
            balance = total_issued - total_used
            value = Decimal(str(material.value)) * balance
            total_balance += value

            arr.append({
                "material": material.name,
                "issued": total_issued,
                "used": total_used,
                "balance": balance,
                "value": value,
            })

        return {
            "total":total_balance,
            "materials":arr
        }

    def compliance(self):
        return [cp.obj() for cp in FocCompliance.objects.filter(foc=self)]

    def is_complied(self):
        # 1. Get all types that are marked as required
        required_types = FocComplianceType.objects.filter(is_required=True)

        for cc in required_types:
            # 2. Check for the record
            record = FocCompliance.objects.filter(foc=self, c_type=cc).first()

            # 3. If record doesn't exist, OR the file is physically missing from the server
            if not record or not record.actual_file():
                return {
                    'status':False,
                    "message":f"{cc.name} not submitted"
                }

        # If we made it through the whole loop without returning False, they are compliant
        return {
            'status':True,
            'message':"All compliances certified"
        }

    def profile_complete(self):
        # List only the fields the contractor needs to fill manually
        required_fields = [
            'company', 'owner', 'phone', 'email', 'country', 'city',
            'gh_post_code', 'gh_card_no', 'owner_phone', 'owner_email',
            'comp_reg_number', 'business_type', 'region', 'business_address',
            'bank_name', 'bank_acct_number', 'bank_branch'
        ]

        for field in required_fields:
            value = getattr(self, field)
            # Check if the field is None, an empty string, or just whitespace
            if value is None or str(value).strip() == "":
                return {
                    'status':False,
                    'message':"Profile not up to date"
                }

        return {
            "status":True,
            "message":"Profile Up to date"
        }

    def pending_compliance(self):
        total_require_compliance = FocComplianceType.objects.filter(is_required=True).count()
        total_complied = FocCompliance.objects.filter(foc=self,c_type__is_required=True).count()

        return f"{total_complied} / {total_require_compliance}"

class ContractorDocuments(models.Model):
    contractor = models.ForeignKey(Contractor,on_delete=models.CASCADE)
    file = models.FileField(upload_to='static/general/ssml/contractor_documents')
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255,blank=True)
    
    def obj(self):
        return {
            'id':self.pk,
            'contactor':self.contractor.company,
            'title':self.title,
            'description':self.description,
            'file': self.file.url if self.file else None,
        }

class Supplier(models.Model):
    supplier_name = models.CharField(max_length=255, unique=True)
    contact_person = models.CharField(max_length=255)
    supplier_address = models.TextField()
    supplier_phone = models.CharField(max_length=255)
    supplier_email = models.EmailField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.supplier_name
    
    
    
    def obj(self):
        return {
            'id':self.id,
            'supplier_name':self.supplier_name,
            'contact_person':self.contact_person,
            'supplier_address':self.supplier_address,
            'supplier_phone':self.supplier_phone,
            'supplier_email':self.supplier_email,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
        }

class Grn(models.Model):
    type_choices = [
        ('purchase', 'Purchase'),
        ('return', 'Return'),
        ('sample', 'Sample'),
    ]
    grn_no = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255, choices=type_choices)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    grn_date = models.DateField()
    remarks = models.TextField()
    grn_type = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_qty = models.DecimalField(max_digits=10, decimal_places=2)
    is_posted = models.BooleanField(default=False)
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='posted_grns')
    location = models.ForeignKey(Location,on_delete=models.CASCADE,null=False)
    
    

    def __str__(self):
        return self.grn_date
    
    def obj(self):
        return {
            'id':self.id,
            'supplier':self.supplier.obj(),
            'grn_date':self.grn_date,
            'remarks':self.remarks,
            'grn_type':self.grn_type,
            'created_by':self.created_by.username,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'total_amount':self.total_amount,
            'total_qty':GrnTransaction.objects.filter(grn=self).aggregate(total_qty=models.Sum('total_qty'))['total_qty'] or 0,
            'transactions':self.transactions(),
            'next_row':self.next_row(),
            'prev_row':self.prev_row(),
            'status':self.status(),
            'grn_no':self.grn_no,
            'is_posted':self.is_posted,
            'posted_by':self.posted_by.get_full_name() if self.posted_by else "",
            'location':self.location.loc_name if self.location else 'NOT SET'
        }
    def status(self):
        if self.is_posted:
            return 'Posted'
        else:
            return 'Not Posted'
    def save(self, *args, **kwargs):
        if not self.grn_no:
            self.grn_no = f"GRN-{self.id}"
        super().save(*args, **kwargs)

    def transactions(self):
        obj = []
        transactions = GrnTransaction.objects.filter(grn=self)
        for transaction in transactions:
            obj.append(transaction.obj())
        return obj
    def next_row(self):
        return Grn.objects.filter(id__gt=self.id).first().id if Grn.objects.filter(id__gt=self.id).count() > 0 else 0
    def prev_row(self):
        return Grn.objects.filter(id__lt=self.id).last().id if Grn.objects.filter(id__lt=self.id).count() > 0 else 0 
    
class GrnTransaction(models.Model):
    grn = models.ForeignKey(Grn, on_delete=models.CASCADE)
    material = models.ForeignKey(InventoryMaterial, on_delete=models.CASCADE)
    barcode = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    uom = models.CharField(max_length=255)
    pack_qty = models.DecimalField(max_digits=10, decimal_places=2)
    total_qty = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.grn.barcode
    
    def obj(self):
        return {
            'id':self.id,
            'material':self.material.obj(),
            'barcode':self.barcode,
            'name':self.name,
            'qty':self.qty,
            'rate':self.rate,
            'amount':self.amount,
            'uom':self.uom,
            'pack_qty':self.pack_qty,
            'created_at':self.created_at,
            'total_qty':self.total_qty,
            'updated_at':self.updated_at
        }
    # def save(self, *args, **kwargs):
    #     # Calculate this transaction's contribution
    #     self.amount = self.rate * self.qty  # Calculate amount if not set
    #     self.total_qty = self.qty * self.pack_qty  # Calculate total_qty
        
    #     super().save(*args, **kwargs)  # Save first to ensure we have an ID
        
    #     # Recalculate GRN totals from all transactions
    #     grn_transactions = GrnTransaction.objects.filter(grn=self.grn)
    #     total_amount = sum(t.amount for t in grn_transactions)
    #     total_qty = sum(t.total_qty for t in grn_transactions)
        
    #     # Update the related GRN with new totals
    #     self.grn.total_amount = total_amount 
    #     self.grn.total_qty = total_qty
    #     self.grn.save()
        

class Cardex(models.Model):
    doc_type_choices = [
        ('GR', 'GRN'), # IN
        ('ISS', 'ISSUE'), # OUT
        ('CIS', 'Contractor Issue Return'), # IN
        ('RET', 'RETURN'), # IN
        ('TRF',"Transfer")# IN OUT
    ]
    doc_type = models.CharField(max_length=3, choices=doc_type_choices)
    doc_no = models.CharField(max_length=255)
    ref_no = models.CharField(max_length=255)
    material = models.ForeignKey(InventoryMaterial, on_delete=models.CASCADE)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateField(null=False)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.ForeignKey(Location,on_delete=models.CASCADE,null=False)
    balance = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)

   
    
    def obj(self):
        return {
            'id':self.id,
            'doc_type':self.doc_type,
            'doc_no':self.doc_no,
            'ref_no':self.ref_no,
            'material':self.material.obj(),
            'qty':self.qty,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'balance':self.balance,
            'location':self.location.loc_name
        }
    

    



class Issue(models.Model):
    issue_no = models.CharField(max_length=255, unique=True)
    issue_date = models.DateField()
    remarks = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='modified_issues')
    car_no = models.CharField(max_length=255, null=True, blank=True)
    location = models.ForeignKey(Location,on_delete=models.CASCADE,null=False)
    
    issue_type_choices = [
        ('ADJ', 'Adjustment'),
        ('ISS', 'Issue'),
        ('RET', 'Return'),
        ('SMP', 'Sample'),
        ('TRN', 'Transfer'),
        ('CIS', 'Contractor Issue Return'),
    ]
    issue_type = models.CharField(max_length=255, choices=issue_type_choices)
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    is_posted = models.BooleanField(default=False)
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='posted_issues')
    is_deleted = models.BooleanField(default=False)

    def status(self):
        if self.is_posted:
            return 'Posted'
        else:
            return 'Not Posted'

    def obj(self):
        return {
            'id':self.id,
            'issue_no':self.issue_no,
            'issue_date':self.issue_date,
            'remarks':self.remarks,
            'created_by':self.created_by.username,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'issue_type':self.issue_type,
            'contractor':self.contractor.obj(),
            'transactions':self.transactions(),
            'next_row':self.next_row(),
            'prev_row':self.prev_row(),
            'is_posted':self.is_posted,
            'posted_by':self.posted_by.get_full_name() if self.posted_by else "",
            'status':self.status(),
            'total_amount':IssueTransaction.objects.filter(issue=self).aggregate(total_amount=models.Sum('amount'))['total_amount'] or 0,
            'total_qty':IssueTransaction.objects.filter(issue=self).aggregate(total_qty=models.Sum('total_qty'))['total_qty'] or 0,
            'modified_by':self.modified_by.get_full_name() if self.modified_by else "",
            'location':self.location.loc_name
        }
    def transactions(self):
        obj = []
        transactions = IssueTransaction.objects.filter(issue=self)
        for transaction in transactions:
            obj.append(transaction.obj())
        return obj
    def next_row(self):
        return Issue.objects.filter(id__gt=self.id).first().id if Issue.objects.filter(id__gt=self.id).count() > 0 else 0
    def prev_row(self):
        return Issue.objects.filter(id__lt=self.id).last().id if Issue.objects.filter(id__lt=self.id).count() > 0 else 0

    def total_qty(self):
        return IssueTransaction.objects.filter(issue=self).aggregate(total_qty=models.Sum('total_qty'))['total_qty'] or 0
    
class IssueTransaction(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE)
    material = models.ForeignKey(InventoryMaterial, on_delete=models.CASCADE)
    barcode = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    uom = models.CharField(max_length=255)
    pack_qty = models.DecimalField(max_digits=10, decimal_places=2)
    total_qty = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def obj(self):
        return {
            'id':self.id,
            'material':self.material.obj(),
            'barcode':self.barcode,
            'name':self.name,
            'qty':self.qty,
            'rate':self.rate,
            'amount':self.amount,
            'uom':self.uom,
            'pack_qty':self.pack_qty,
            'total_qty':self.total_qty,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'issue_no':self.issue.issue_no,
            'issue_date':self.issue.issue_date,
            'remarks':self.issue.remarks,
            'contractor':self.issue.contractor.company,
            'issue_type':self.issue.issue_type,
            'car_no':self.issue.car_no,
            'is_posted':self.issue.is_posted,
            'posted_by':self.issue.posted_by.get_full_name() if self.issue.posted_by else "",
            

        }



class Plot(models.Model):
    plot_no = models.CharField(max_length=255, unique=True)
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    plot_size = models.DecimalField(max_digits=10, decimal_places=2)
    plot_image = models.ImageField(upload_to='static/uploads/plots/', null=True, blank=True,default='static/uploads/plots/default.png')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.plot_no
    
    def obj(self):
        return {
            'id':self.id,
            'plot_no':self.plot_no,
            'contractor':self.contractor.obj(),
            'plot_size':self.plot_size,
            'plot_image':self.plot_image.url if self.plot_image else None,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'created_by':self.created_by.username
        }
    


class ServiceType(models.Model):
    name = models.CharField(max_length=255,unique=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    debit_account = models.ForeignKey(BankAccounts,null=True,blank=True,on_delete=models.CASCADE,related_name='debit_account')
    credit_account = models.ForeignKey(BankAccounts,null=True,blank=True,on_delete=models.CASCADE,related_name='credit_account')

    def __str__(self):
        return self.name

    def total_installations(self,date=datetime.now().date()):
        return ServiceOrder.objects.filter(service_type=self,service_date__range=('2000-01-01',date)).count()
    

    def today_jobs(self,date=datetime.now().date()):
        #print(date)
        return ServiceOrder.objects.filter(service_type=self,service_date=date).count()
    
    def obj(self):
        return {
            'id':self.id,
            'name':self.name,
            'description':self.description,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'total_installations':self.total_installations(),
            'today_jobs':self.today_jobs(datetime.now().date()),
            'accounts': {
            'debit': {
                'serial': self.debit_account.acct_serial if self.debit_account else None,
                'name': self.debit_account.acct_name if self.debit_account else None
            },
            'credit': {
                'serial': self.credit_account.acct_serial if self.credit_account else None,
                'name': self.credit_account.acct_name if self.credit_account else None
            }
        }
        }
    

class Service(models.Model):
    code = models.CharField(max_length=255,unique=True)
    name = models.CharField(max_length=255,unique=True)
    description = models.TextField()
    uom = models.CharField(max_length=255)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    
    def obj(self):
        return {
            'id':self.id,
            'code':self.code,
            'name':self.name,
            'description':self.description,
            'uom':self.uom,
            'rate':self.rate,
            'created_at':self.created_at,
            'updated_at':self.updated_at
        }
    
class ServiceTypeServices(models.Model):
    service_type = models.ForeignKey(ServiceType,on_delete=models.CASCADE,null=False,blank=False)
    service = models.ForeignKey(Service,on_delete=models.CASCADE,null=False,blank=False)

    class Meta:
        unique_together = (('service_type','service'),)


class ServiceMaterialRates(models.Model):
    service = models.ForeignKey(Service,on_delete=models.CASCADE,null=False,blank=False,related_name='material_service')
    material = models.ForeignKey(InventoryMaterial,on_delete=models.CASCADE,null=False,blank=False,related_name='rate_material',verbose_name='rate_material')
    break_point = models.DecimalField(decimal_places=2,default=0.00,max_digits=10)

    class Meta:
        unique_together = (('service','material'),)

    def obj(self):
        return {
            'id':self.id,
            'service':self.service.name,
            'rate':self.service.rate,
            'description':self.service.description,
            'break_point':self.break_point

        }

class ServiceMaterials(models.Model):
    service = models.ForeignKey(ServiceType,on_delete=models.CASCADE,null=False,blank=False,related_name='material_service_x')
    material = models.ForeignKey(InventoryMaterial,on_delete=models.CASCADE,null=False,blank=False,related_name='rate_material_x',verbose_name='rate_material')
    phase = models.ForeignKey('Phase',on_delete=models.SET_NULL,null=True,blank=True,related_name='material_phase_x')
    qty = models.DecimalField(decimal_places=2,default=0.00,max_digits=10)


    class Meta:
        unique_together = (('service','material','phase'),)


    def obj(self):
        return {
            'id':self.id,
            'service':self.service.name,
            'qty':self.qty,
            'phase':self.phase.description if self.phase else 'Not',
            'material':self.material.name,
        }

class ServiceOrder(models.Model):
    
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    service_date = models.DateField()
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    plot = models.CharField(max_length=255,default="NOT SET")
    geo_code = models.CharField(max_length=255,default="NOT SET")
    customer = models.CharField(max_length=255)
    customer_no = models.CharField(max_length=255)
    old_meter_no = models.CharField(max_length=255,unique=True)
    new_meter = models.CharField(unique=True,null=False,max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    spn = models.CharField(max_length=255,null=False)
    is_routing = models.BooleanField(default=False)
    installation_type = models.ForeignKey('InstallationType',on_delete=models.SET_NULL,null=True)
    status_choices = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('disapproved', 'Disapproved'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('rejected', 'Rejected'),
        ('invoiced',"Invoiced"),
        ('paid', 'Paid'),
        ('ecg_invoiced', 'ECG Invoiced'),
    ]
    status = models.CharField(max_length=255, choices=status_choices, default='pending')
    is_ecg_invoiced = models.BooleanField(default=False)
    old_meter_no_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    new_meter_no_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    closed_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='closed_service_orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    location = models.ForeignKey(Location,on_delete=models.CASCADE,null=False)
    gps_code = models.CharField(unique=False,null=True,blank=True,max_length=255,default="none")
    phase = models.CharField(unique=False,null=True,blank=True,max_length=255,default="1 phase")
    is_boxed = models.BooleanField(default=False)
    box_no = models.CharField(max_length=100,default=0)
    final_readings = models.DecimalField(max_digits=65, decimal_places=2, default=0)

    flag_for_invoice = models.BooleanField(default=False)
    inv_number = models.CharField(max_length=255,null=True,blank=True)
    inv_date = models.DateField(null=True,blank=True)

    ecg_date = models.DateField(null=True,blank=True)
    linked_phase = models.ForeignKey('Phase',on_delete=models.SET_NULL,null=True,blank=True)


    def custom_update(self):
        # updat phase
        sts_no = self.new_meter
        # get meter phase
        meter = Meter.objects.filter(meter_no=sts_no).first()
        lk_phase = meter.linked_phase if meter.linked_phase else None
        print(f"STS {sts_no} set to {lk_phase.description if lk_phase else 'Not Set'}")

        self.linked_phase = meter.linked_phase if meter.linked_phase else None

        self.save()

    def items(self):
        obj = []
        items = ServiceOrderItem.objects.filter(service_order=self)
        for item in items:
            obj.append(item.obj())
        return obj

    def meter_phase(self):
        return Meter.objects.filter(meter_no=self.new_meter).first().linked_phase.description if Meter.objects.filter(meter_no=self.new_meter).exists() else "Not Set"

    def install_amount(self):
        sts_no = self.new_meter
        # get meter phase
        meter = Meter.objects.filter(meter_no=sts_no).first()
        text_phase = self.phase
        meter_text_phase = meter.phase
        linked_phase = meter.linked_phase
        print("#" * 5 , sts_no , "#" * 5)
        print(f"Meter phase: {meter_text_phase}, Order phase: {text_phase}, Linked phase: {linked_phase.description if linked_phase else 'Not Set'}")

        # get installation type
        install_type = self.installation_type
        print(f"Installation Type: {install_type.name if install_type else 'Not Set'}")

        # get rate
        job_rate = InstallationTypePhaseRate.objects.filter(installation_type=install_type, phase=linked_phase).first()
        if job_rate:
            job_rate = job_rate.rate
        else:
            job_rate = 0
        print(f"Job Rate: {job_rate}")

        print("#" * 5, sts_no, "#" * 5)
        print("")


        return job_rate

    def total_amount(self):
        return ServiceOrderItem.objects.filter(service_order=self).aggregate(total_amount=models.Sum('amount'))['total_amount'] or 0

    def sn_same_as_wo(self):
        if RetiredMetersTransactions.objects.filter(spn=self.spn).exists():

            row =  RetiredMetersTransactions.objects.filter(spn=self.spn).last()
            
            is_same = "NO" if row.diff_old_meter_no and len(row.diff_old_meter_no) == 0 else "YES"
            return {
                "application":True,
                "is_same" : is_same
            }

        else:
            return {
                "application":False,
                "is_same":"NO"
            }

    def materials(self):
        obj = []
        materials = MaterialOrderItem.objects.filter(service_order=self,material_type='is')
        for material in materials:
            obj.append(material.obj())
        return obj
    
    def returns(self):
        obj = []
        returns = ServiceOrderReturns.objects.filter(service_order=self)
        for rt in returns:
            obj.append(rt.obj())
        return obj
    
    def installed_meter(self):
        return {}
    
    def obj(self):
        return {
            'id':self.id,
            'service_type':self.service_type.obj(),
            'service_date':self.service_date,
            'installation_type':self.installation_type.obj(),
            'contractor':self.contractor.obj(),
            'plot':self.plot,
            'geo_code':self.geo_code,
            'customer':self.customer,
            'customer_no':self.customer_no,
            'old_meter_no':self.old_meter_no,
            'new_meter_no':self.new_meter,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'created_by':self.created_by.username,
            'status':self.status,
            'service_items':self.items(),
            'total_amount':self.total_amount(),
            'materials':self.materials(),
            'returns':self.returns(),
            'old_meter_reading':self.old_meter_no_reading,
            'new_meter_reading':self.new_meter_no_reading,
            'next_row':self.next_row(),
            'prev_row':self.prev_row(),
        }
    def next_row(self):
        return ServiceOrder.objects.filter(id__gt=self.id).first().id if ServiceOrder.objects.filter(id__gt=self.id).count() > 0 else 0
    def prev_row(self):
        return ServiceOrder.objects.filter(id__lt=self.id).last().id if ServiceOrder.objects.filter(id__lt=self.id).count() > 0 else 0
    


class Phase(models.Model):
    number = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    material = models.ForeignKey(InventoryMaterial,on_delete=models.SET_NULL,null=True)

    def __str__(self):
        return f"Phase {self.number}: {self.description}"

    def total_meters(self):
    # INSERT_YOUR_CODE
        return Meter.objects.filter(linked_phase=self).count()

    def stock(self,as_of='*',loc_id='*'):
        if self.material:
            mt = self.material.stock(as_of,loc_id)
            return mt
        else:
            return 0

    def obj(self):
        return {
            'id': self.id,
            'number': self.number,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'created_by': self.created_by.username if self.created_by else None
        }

    def total_installed(self,date='*'):
        return ServiceOrder.objects.filter(linked_phase=self).count() if date == '*' else ServiceOrder.objects.filter(service_date=date,linked_phase=self).count()


class Meter(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.SET_NULL,null=True)
    meter_no = models.CharField(max_length=255,unique=True)
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_issued = models.BooleanField(default=False)
    service_order = models.ForeignKey(ServiceOrder, on_delete=models.SET_NULL, null=True, blank=True)
    meter_type_choices = [
        ('1 phase ', 'Single Phase'),
        ('3 phase', 'Three Phase'),
        ('other', 'Other'),
    ]

    linked_phase = models.ForeignKey(Phase,on_delete=models.SET_NULL,null=True)
    phase = models.CharField(max_length=255, choices=meter_type_choices, default='other')
    phase_str = models.CharField(max_length=255, default='', help_text='Phase as plain text')

    ecg_invoice_no = models.CharField(max_length=255, null=True, blank=True)






    location = models.ForeignKey(Location,on_delete=models.CASCADE,null=False)
    ip_address = models.CharField(max_length=255, default='0.0.0.0')
    installation_address = models.CharField(max_length=255, default='0')

   

    def __str__(self):
        return self.meter_no
    
    def meter_type_display(self):
        return self.phase
    
    def obj(self):
        return {
            'id':self.id,
            'meter_no':self.meter_no,
            'contractor':self.contractor.obj(),
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'is_issued':self.is_issued,
            'service_order':self.service_order.obj() if self.service_order else None,
            'service':ServiceOrder.objects.get(new_meter=self.meter_no).id if ServiceOrder.objects.filter(new_meter=self.meter_no).exists() else None
        }
    


class ServiceOrderItem(models.Model):
    service_order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='modified_service_order_items')
    class Meta:
        unique_together = ('service_order', 'service')
    
    def obj(self):
        return {
            'id':self.id,
            'quantity':self.quantity,
            'rate':self.rate,
            'amount':self.amount,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'service':self.service.obj()
        }
    
    



class MaterialOrderItem(models.Model):
    service_order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE)
    material = models.ForeignKey(InventoryMaterial, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='modified_material_order_items')
    material_type_choices = [
        ('rt', 'Return'),
        ('is', 'Issue'),
    ]
    material_type = models.CharField(max_length=255, choices=material_type_choices, default='is',null=False,blank=False)
    class Meta:
        unique_together = ('service_order', 'material','material_type')

    def obj(self):
        return {
            'id':self.id,
            'material':self.material.obj(),
            'quantity':self.quantity,
            'rate':self.rate,
            'amount':self.amount,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'material_type':self.material_type
        }
    
class ServiceOrderReturns(models.Model):
    service_order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE)
    material = models.ForeignKey(InventoryMaterial, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='modified_service_order_returns')
    
    class Meta:
        unique_together = ('service_order', 'material')

    def obj(self):
        return {
            'id':self.id,
            'material':self.material.obj(),
            'quantity':self.quantity,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'created_by':self.created_by.username if self.created_by else None,
            'modified_by':self.modified_by.username if self.modified_by else None,
            'rate':self.material.value,
            'amount':self.quantity * self.material.value
        }
    

class Ledger(models.Model):
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_no = models.CharField(max_length=255,unique=True,null=False,blank=False)
    transaction_types = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    transaction_type = models.CharField(max_length=255, choices=transaction_types)
    remarks = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def obj(self):
        return {
            'id':self.id,
            'amount':self.amount,
            'transaction_type':self.transaction_type,
            'remarks':self.remarks,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'created_by':self.created_by.username,
            'contractor':self.contractor.obj()
        }
    

class Reedem(models.Model):
    entry_no = models.CharField(max_length=10,unique=True,null=False,blank=False)
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    entry_date =  models.DateField()
    remarks = models.TextField()
    type_choices = [
        ('RET',"Return"),
        ("ISS","Issue")
    ]
    transaction_type = models.CharField(max_length=255, choices=type_choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_valid = models.BooleanField(default=True)
    location = models.ForeignKey(Location,on_delete=models.CASCADE,null=False)

    def next_row(self):
        return Reedem.objects.filter(id__gt=self.id).first().id if Reedem.objects.filter(id__gt=self.id).count() > 0 else 0
    def prev_row(self):
        return Reedem.objects.filter(id__lt=self.id).last().id if Reedem.objects.filter(id__lt=self.id).count() > 0 else 0

    def transactions(self):
        trans = RedeemTransactions.objects.filter(redeem=self)
        return [redeem.obj() for redeem in trans]


    def obj(self):
        return {
            'id':self.id,
            'entry_no':self.entry_no,
            'contractor':{
                'company':self.contractor.company,
                'id':self.contractor.id
            },
            'entry_date':self.entry_date,
            'type':self.transaction_type,
            'date_created':self.created_at,
            'created_by':self.created_by.username,
            'remarks':self.remarks,
            'transactions':self.transactions(),
            'next_row':self.next_row(),
            'prev_row':self.prev_row(),
            'is_valid':self.is_valid
        }


class RedeemTransactions(models.Model):
    redeem =  models.ForeignKey(Reedem, on_delete=models.CASCADE)
    material = models.ForeignKey(InventoryMaterial, on_delete=models.CASCADE)
    pack_um = models.CharField(max_length=5)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


    def obj(self):
        return {
            'material':self.material.obj(),
            'pack_um':self.pack_um,
            'balance':self.balance,
            'qty':self.qty,
            'reason':self.reason
        }



class ContractorError(models.Model):
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE)
    error_date = models.DateField()
    error_type_choices = [
        ('CBL', 'Cabling'),
        ('INS', 'Installation'),
        ('MT',"Materials"),
        ('OT',"Other")
    ]   
    error_type = models.CharField(max_length=255, choices=error_type_choices)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    meter = models.ForeignKey(Meter, on_delete=models.CASCADE,to_field='meter_no')
    is_cleared = models.BooleanField(default=False)
    cleared_at = models.DateTimeField(null=True, blank=True)
    cleared_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    cleared_remarks = models.TextField(null=True, blank=True)

    def obj(self):
        return {
            'id':self.id,
            'error_type':self.error_type,
            'description':self.description,
            'meter':self.meter.obj(),
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'is_cleared':self.is_cleared,
            'cleared_at':self.cleared_at,
            'cleared_by':self.cleared_by.username if self.cleared_by else None,
            'cleared_remarks':self.cleared_remarks
        }

class PettyCash(models.Model):

    date = models.DateField()
    month = models.CharField(max_length=255,null=False,blank=False)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    entry_no = models.CharField(max_length=255,null=False,blank=False,unique=True)
    total_out = models.DecimalField(max_digits=10, decimal_places=2)
    total_in = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)

    def next_entry_no(self):
        return Expense.objects.filter(id__gt=self.id).first().entry_no if Expense.objects.filter(id__gt=self.id).count() > 0 else False

    def prev_entry_no(self):
        return Expense.objects.filter(id__lt=self.id).last().entry_no if Expense.objects.filter(id__lt=self.id).count() > 0 else False

    def obj(self):
        return {
            'month': datetime.strptime(str(self.month), "%m").strftime("%B") if self.month.isdigit() else self.month,
            'date':self.date,
            'total':self.total,
            'entry_no':self.entry_no,
            'transactions':self.transactions(),
            'total_out':self.total_outt(),
            'total_in':self.total_ins(),
            'next_entry_no':self.next_entry_no(),
            'prev_entry_no':self.prev_entry_no(),
        }

    def total_ins(self):
        return Expense.objects.filter(entry_no=self.entry_no,direction='in').aggregate(total_in=Sum('amount'))['total_in'] or 0
    def total_outt(self):
        return Expense.objects.filter(entry_no=self.entry_no,direction='out').aggregate(total_out=Sum('amount'))['total_out'] or 0

    def transactions(self):
        return [tr.obj() for tr in Expense.objects.filter(entry_no=self.entry_no)]

class Expense(models.Model):

    direction_choices = [
        ('in', 'In'),
        ('out', 'Out'),
    ]
    direction = models.CharField(max_length=255, choices=direction_choices)
    date = models.DateField()
    category_choices = [
        ('home', 'Home Expense'),
        ('staff', 'Staff Expense'),
        ('transport', 'Transport Expense'),
        ('marketing', 'Marketing Expense'),
        ('other', 'Other'),
    ]
    category = models.CharField(max_length=255, choices=category_choices)
    transaction_type_choices = [
        ('cash', 'Cash'),
        ('momo', 'MoMo'),
        ('other', 'Other'),
    ]
    transaction_type = models.CharField(max_length=255, choices=transaction_type_choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    ori_amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)

    reference = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    is_approved = models.BooleanField(default=False)
    is_posted = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    entry_no = models.CharField(max_length=255)

    
    # class Meta:
    #     unique_together = (('date','reference','amount'),)

    def evidence(self):
        # INSERT_YOUR_CODE
        evidences = self.evidences.all()
        items = [f"{e.title}|{e.file.url}" for e in evidences if e.file]
        return ','.join(items)

    def status(self):
        if self.is_rejected:
            return False
        else:
            return True

    def approved(self):
        if not self.status():
            if self.is_approved:
                return True
            else:
                return False
        else:
            return False


    def obj(self):
        return {
            'id':self.id,
            'direction':self.direction,
            'date':self.date,
            'category':self.category,
            'transaction_type':self.transaction_type,
            'amount':self.amount,
            'reference':self.reference,
            'description':self.description,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'created_by':self.created_by.get_full_name(),
            'evidence':self.evidence(),
            'status':self.status(),
            'approval':self.approved()
        }
    
class FinancialEvidence(models.Model):
# INSERT_YOUR_CODE
    transaction = models.ForeignKey('Expense', on_delete=models.CASCADE, related_name='evidences')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='static/general/financial_evidence/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def obj(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction.id if self.transaction else None,
            'title': self.title,
            'file_url': self.file.url if self.file else None,
            'uploaded_by': self.uploaded_by.get_full_name() if self.uploaded_by else None,
            'uploaded_at': self.uploaded_at,
            
        }
    
class InvoiceHD(models.Model):
    entry_no = models.CharField(max_length=255,null=False, blank=False,unique=True)
    entry_date = models.DateField(null=False)
    contractor = models.ForeignKey(Contractor,on_delete=models.SET_NULL,null=True)
    remarks = models.TextField()
    total_amount = models.DecimalField(max_digits=10,max_length=10,decimal_places=2,default=0.00)

    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    date_created = models.DateField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)

    is_approved = models.BooleanField(default=False)
    is_posted = models.BooleanField(default=False)

    approved_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='invapproved_by')
    posted_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='invposted_by')

    is_paid = models.BooleanField(default=False)
    payment_reciept = models.CharField(max_length=255,null=True,blank=True)

    foc_debt = models.DecimalField(max_digits=10,max_length=10,decimal_places=2,default=0.00)
    foc_debt_reason = models.TextField(null=True,blank=True)

    class Meta:
        unique_together = (('entry_date','contractor'),)

    def status(self):
        if not self.is_approved:
            return 'pending approval'
        elif not self.is_posted:
            return 'pending posting'
        elif self.is_approved and self.is_posted:
            return 'posted'
        else:
            return 'unknwn'
        
    def stage(self):
        if not self.is_approved:
            return 1 # pending approve
        elif not self.is_posted:
            return 2 # pending posting
        elif self.is_approved and self.is_posted:
            return 3 # posted
        else:
            return 0 # unknown
        
    def transactions(self):
        return [tran.obj(detailed=False) for tran in InvoiceTransactions.objects.filter(entry=self)]
    
    def next_row(self):
        return InvoiceHD.objects.filter(id__gt=self.id).first().id if InvoiceHD.objects.filter(id__gt=self.id).count() > 0 else 0
    def prev_row(self):
        return InvoiceHD.objects.filter(id__lt=self.id).last().id if InvoiceHD.objects.filter(id__lt=self.id).count() > 0 else 0

    def obj(self):
        return{
            'contractor':{
                "name":self.contractor.company,
            },
            'id':self.id,
            'entry_no':self.entry_no,
            'entry_date':self.entry_date,
            'remarks':self.remarks,
            'total_amount':self.total_amount,
            'created_by':self.created_by.get_full_name(),
            'date_created':self.date_created,
            'time_created':self.time_created,
            'is_approved':self.is_approved,
            'is_posted':self.is_posted,
            'status':self.status(),
            'transactions':self.transactions(),
            'next':self.next_row(),
            'previous':self.prev_row(),
            'stage':self.stage()
        }


class ECGJobRate(models.Model):
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def obj(self):
        return {
            'id': self.id,
            'service_type': self.service_type.obj(),
            'rate': self.rate,
        }

class ECGMeterRate(models.Model):
    phase_choices = [
        ('1 phase ', 'Single Phase'),
        ('3 phase', 'Three Phase'),
    ]
    phase = models.CharField(max_length=255, choices=phase_choices, unique=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def obj(self):
        return {
            'id': self.id,
            'phase': self.phase,
            'rate': self.rate,
        }



class InvoiceTransactions(models.Model):
    entry = models.ForeignKey(InvoiceHD,on_delete=models.CASCADE)
    service_date = models.DateField(null=False)
    asset = models.CharField(max_length=255,null=False, blank=False,unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.CharField(max_length=255,null=False, blank=False)

    class Meta:
        unique_together = (('entry','asset'),)

    def obj(self,detailed=False):
        if detailed:
            return {}
        else:
            return {

                "service_date":self.service_date,
                'asset':self.asset,
                'amount':self.amount,
                'remarks':self.remarks
            }
        
class PaySlipHD(models.Model):
    entry_no = models.CharField(max_length=255,null=False, blank=False,unique=True)
    entry_date = models.DateField(null=False)
    ps_type = models.CharField(max_length=10,null=False,choices=[
        ('CI',"Contractor Invoice")
    ],default='CI')

    ref = models.CharField(max_length=255,null=False, blank=False,unique=True)
    remarks = models.TextField()
    total_amount = models.DecimalField(max_digits=10,max_length=10,decimal_places=2,default=0.00)
    due_date = models.DateField(null=False)

    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    date_created = models.DateField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)

class PaySlipTransactions(models.Model):
    entry = models.ForeignKey(PaySlipHD,on_delete=models.CASCADE)
    remarks = models.TextField()
    acct = models.CharField(max_length=200)
    debit = models.DecimalField(default=0.00,decimal_places=2,max_digits=10)
    credit = models.DecimalField(default=0.00,decimal_places=2,max_digits=10)


class TransferHd(models.Model):
    loc_fr = models.ForeignKey(Location,on_delete=models.CASCADE,related_name='loc_fr')
    loc_to = models.ForeignKey(Location,on_delete=models.CASCADE,related_name='loc_to')
    entry_date = models.DateField(null=False)
    entry_no = models.CharField(max_length=255,null=False, blank=False,unique=True)
    is_posted = models.BooleanField(default=False)
    is_valid = models.BooleanField(default=True)

    transfer_type_choices = [('int','Internal'),
        ('ext','External')]

    tran_type = models.CharField(max_length=255,null=False, blank=False,choices=transfer_type_choices,default='int')

    remarks = models.TextField()
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    date_created = models.DateField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='approved_transfers')
    approved_date = models.DateField(null=True,blank=True)
    approved_time = models.TimeField(null=True,blank=True)

    is_sent = models.BooleanField(default=False)
    sent_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name="sender")
    sent_date = models.DateField(null=True,blank=True)
    transporter = models.CharField(max_length=200,null=True,blank=True)
    car_no  = models.CharField(max_length=200,unique=False,blank=True)


    def post(self):
        for tran in self.transactions():
            tr = self      
            material_id = tran.get('material_id')
            material = InventoryMaterial.objects.get(id=material_id)
            total = Decimal(tran.get('sent_qty') ) * Decimal(tran.get('pack_qty'))

            Cardex.objects.create(
                            doc_type='TRF',
                            doc_no = tr.entry_no,
                            ref_no = tr.entry_no,
                            material=material,
                            qty=total,
                            created_at=tr.date_created,
                            location=tr.loc_to,
                        )

            Cardex.objects.create(
                            doc_type='TRF',
                            doc_no = tr.entry_no,
                            ref_no = tr.entry_no,
                            material=material,
                            qty=total * Decimal(-1),
                            created_at=tr.date_created,
                            location=tr.loc_fr,
                        )
            tr.is_posted = True
            tr.save()

    def status(self):

        if not self.is_valid:
            return 'Deleted'
        elif not self.is_posted:
            return 'Pending'
        else:
            return 'Posted' 
        
    def docs(self):
        docs = []
        for doc in Documents.objects.filter(doc_type='ssml_tr',ref=self.entry_no):
            docs.append({
                'title': doc.title,
                'description': doc.description,
                'file_url': doc.file.url if doc.file else None
            })
        return docs

    def next_row(self):
        return TransferHd.objects.filter(id__gt=self.id).first().id if TransferHd.objects.filter(id__gt=self.id).count() > 0 else 0
    def prev_row(self):
        return TransferHd.objects.filter(id__lt=self.id).last().id if TransferHd.objects.filter(id__lt=self.id).count() > 0 else 0

    def transactions(self):
        return [tran.obj() for tran in TransferTr.objects.filter(entry=self)]
    
    def tran_tp(self):
        return dict(self.transfer_type_choices).get(self.tran_type, self.tran_type)

    def obj(self):
        return {
            'id':self.id,
            'entry_no':self.entry_no,
            'entry_date':self.entry_date,
            'remarks':self.remarks,
            'created_by':self.created_by.get_full_name(),
            'date_created':self.date_created,
            'time_created':self.time_created,
            'is_posted':self.is_posted,
            'is_valid':self.is_valid,
            'tran_type':self.tran_tp(),
            'loc_fr':self.loc_fr.loc_name,
            'loc_to':self.loc_to.loc_name,
            'transactions':self.transactions(),
            'next':self.next_row(),
            'previous':self.prev_row(),
            'status':self.status(),
            'approved_by':self.approved_by.get_full_name() if self.approved_by else 'Pending',
            'is_sent':self.is_sent,
            'sent_by':self.sent_by.get_full_name() if self.sent_by else 'Pending',
            'transporter':self.transporter,
            'docs':self.docs()
        }

class TransferTr(models.Model):
    entry = models.ForeignKey(TransferHd,on_delete=models.CASCADE)
    material = models.ForeignKey(InventoryMaterial,on_delete=models.CASCADE)
    name = models.CharField(max_length=255,null=False, blank=False)
    barcode = models.CharField(max_length=255,null=False, blank=False)

    oum = models.CharField(max_length=255,null=False, blank=False)
    pack_qty = models.DecimalField(max_digits=20,decimal_places=2,default=0.00)
    
    sent_qty = models.DecimalField(max_digits=20,decimal_places=2,default=0.00)
    received_qty = models.DecimalField(max_digits=20,decimal_places=2,default=0.00)

    total_qty = models.DecimalField(max_digits=20,decimal_places=2,default=0.00)
    diff_qty = models.DecimalField(max_digits=20,decimal_places=2,default=0.00)

    # class Meta:
    #     unique_together = (('entry','material'),)

    def obj(self):
        return {
            'id':self.id,
            'name':self.name,
            'barcode':self.barcode,
            'oum':self.oum,
            'pack_qty':self.pack_qty,
            'sent_qty':self.sent_qty,
            'received_qty':self.received_qty,
            'total_qty':Decimal(self.sent_qty) * Decimal(self.pack_qty),
            'diff_qty':self.diff_qty,
            'material_id':self.material.id
        }

    

class RequiredReturn(models.Model):
    service_type = models.ForeignKey(ServiceType,on_delete=models.CASCADE)
    material = models.ForeignKey(InventoryMaterial,on_delete=models.CASCADE)
    as_of = models.DateField(null=False)
    quantity = models.DecimalField(max_digits=20,decimal_places=2,default=0.00)

    class Meta:
        unique_together = (('service_type','material','as_of'),)
    

class Documents(models.Model):
    title = models.CharField(max_length=200)
    file = models.ImageField(upload_to='static/uploads/files/ssml_docs', null=True, blank=True)
    description = models.TextField()
    doc_choices = [
        ('ssml_grn', 'GRN'),
        ('ssml_tr', 'Transfer'),
        ('ssml_iss', 'Material Issue'),
    ]
    doc_type = models.CharField(max_length=15,null=False,blank=False,choices=doc_choices)
    ref = models.CharField(max_length=200)

    def obj(self):
    # INSERT_YOUR_CODE
        data = {
            'id': self.id,
            'tital': self.tital,
            'description': self.description,
            'doc_type': self.doc_type,
            'ref': self.ref,
        }
        if self.file and hasattr(self.file, 'url'):
            data['file'] = self.file.url
        else:
            data['file'] = None
        return data


class InstallationType(models.Model):
    name = models.CharField(max_length=255,unique=True,null=False,blank=False)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)

    def obj(self):
        return {
            'pk':self.id,
            'name':self.name,
            'description':self.description,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'rate':self.rate
        }

class ServiceOrderType(models.Model):
    name = models.CharField(max_length=255,unique=True,null=False,blank=False)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)

    def obj(self):
        return {
            'pk':self.id,
            'name':self.name,
            'description':self.description,
            'created_at':self.created_at,
            'updated_at':self.updated_at,
            'rate':self.rate
        }


class RetiredMetersBox(models.Model):
    box_no = models.CharField(max_length=255,unique=False,blank=False,null=False)
    location = models.ForeignKey(Location,on_delete=models.SET_NULL,null=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='static/general/upload', null=True, blank=True)


    class Meta:
        unique_together = ('box_no', 'location')

    def transactions(self):
        return [tran.obj() for tran in RetiredMetersTransactions.objects.filter(box=self).order_by('sn')]

    def next(self):
        return RetiredMetersBox.objects.filter(pk__gt=self.pk).first().pk if RetiredMetersBox.objects.filter(pk__gt=self.pk).exists() else 0

    def previous(self):
        return RetiredMetersBox.objects.filter(pk__lt=self.pk).last().pk if RetiredMetersBox.objects.filter(pk__lt=self.pk).exists() else 0

    def obj(self):
        return {
            'id': self.id,
            'box_no': self.box_no,
            'location': self.location.obj() if hasattr(self.location, 'obj') else (self.location.id if self.location else None),
            'created_by': self.created_by.get_full_name() if self.created_by else None,
            'created_at': self.created_at,
            'transactions': self.transactions(),
            "next":self.next(),
            'previous':self.previous()
        }

class RetiredMetersTransactions(models.Model):
    box = models.ForeignKey(RetiredMetersBox, on_delete=models.CASCADE, related_name='retired_meters')
    sn = models.IntegerField()
    spn = models.CharField(max_length=100, blank=True, null=True)
    old_meter_no = models.CharField(max_length=100, unique=True, blank=False, null=False)
    diff_old_meter_no = models.CharField(max_length=100, blank=True, null=True)
    ppm_cm = models.CharField(max_length=100, blank=True, null=True)
    final_readings = models.CharField(max_length=100, blank=True, null=True)
    rem_wattage = models.CharField(max_length=100, blank=True, null=True)
    rem_cedis = models.CharField(max_length=100, blank=True, null=True)
    make_year = models.CharField(max_length=100, blank=True, null=True)
    manufacturere = models.CharField(max_length=255, blank=True, null=True)
    has_uiu = models.CharField(max_length=10, blank=True, null=True)
    phase = models.CharField(max_length=20, blank=True, null=True)
    has_enclosure = models.CharField(max_length=10, blank=True, null=True)
    has_sim_card = models.CharField(max_length=10, blank=True, null=True)
    ret_cable_length = models.CharField(max_length=100, blank=True, null=True)
    rating = models.CharField(max_length=100, blank=True, null=True)
    date_removed = models.DateField(max_length=50, blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    has_breaker = models.CharField(max_length=10, blank=True, null=True)
    foc = models.ForeignKey(Contractor, on_delete=models.CASCADE, related_name='foc')
    created_at = models.DateTimeField(auto_now_add=True)
    gps_address = models.CharField(max_length=100, blank=True, null=True)
    installation_type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ('box', 'old_meter_no')

   

    def obj(self):
        return {
            'id': self.id,
            'sn': self.sn,
            'spn': self.spn,
            'old_meter_no': self.old_meter_no,
            'diff_old_meter_no': self.diff_old_meter_no,
            'ppm_cm': self.ppm_cm,
            'final_readings': self.final_readings,
            'rem_wattage': self.rem_wattage,
            'rem_cedis': self.rem_cedis,
            'make_year': self.make_year,
            'manufacturere': self.manufacturere,
            'has_uiu': self.has_uiu,
            'phase': self.phase,
            'has_enclosure': self.has_enclosure,
            'has_sim_card': self.has_sim_card,
            'ret_cable_length': self.ret_cable_length,
            'rating': self.rating,
            'date_removed': self.date_removed,
            'reason': self.reason,
            'has_breaker': self.has_breaker,
            'foc': self.foc.company if self.foc else None,
            'created_at': self.created_at,
        }

class MaterialRequestHeader(models.Model):
    request_no = models.CharField(max_length=255, unique=True, null=False, blank=False)
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)
    location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, default='Pending', choices=[
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return self.request_no

    def obj(self):
        return {
            'id': self.id,
            'request_no': self.request_no,
            'requested_by': self.requested_by.get_full_name() if self.requested_by else None,
            'location': self.location.obj() if hasattr(self.location, 'obj') else (self.location.id if self.location else None),
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'transactions': [t.obj() for t in self.transactions.all()]
        }
    def save(self, *args, **kwargs):
        self.request_no = self.generate_request_no()
        super().save(*args, **kwargs)

    def generate_request_no(self):
        return f"MR-{self.id}"

class MaterialRequestTransactions(models.Model):
    header = models.ForeignKey(MaterialRequestHeader, on_delete=models.CASCADE, related_name='transactions')
    # Assuming a Material model exists, otherwise use CharField for material_name
    material = models.ForeignKey('InventoryMaterial', on_delete=models.CASCADE)
    material_name = models.CharField(max_length=255, null=False, blank=False)
    quantity_requested = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity_approved = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.header.request_no} - {self.material_name}"

    def obj(self):
        return {
            'id': self.id,
            'header_id': self.header.id,
            'material_name': self.material_name,
            'quantity_requested': self.quantity_requested,
            'quantity_approved': self.quantity_approved,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class InstallationTypePhaseRate(models.Model):
    installation_type = models.ForeignKey(InstallationType, on_delete=models.CASCADE)
    phase = models.ForeignKey('Phase', on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('installation_type', 'phase')

    def __str__(self):
        return f"{self.installation_type.name} - {self.phase} Phase"

    def obj(self):
        return {
            'id': self.id,
            'installation_type_id': self.installation_type.id,
            'phase': self.phase,
            'rate': self.rate,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class AccountLedger(models.Model):
    key = models.CharField(max_length=255, unique=True, null=False, blank=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    name = models.CharField(max_length=200,unique=True,null=False,blank=False)
    reference = models.CharField(max_length=200, blank=True, null=True)
    lty = (
        ("FOC", "Contractors"), ("UNK", "Unknown"),("GOV", "Government")
    )
    ledge_type = models.CharField(max_length=5, choices=lty,null=False,blank=False, default='UNK')

    debit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)


    def obj(self):
        self.update_ledger()
        return {
            "key":self.key,
            "name":self.name,
            "description":self.description,
            "debit":self.debit,
            "credit":self.credit,
            "balance":self.balance(),
        }

    def update_ledger(self):
        total_debit = JournalVoucherTransactions.objects.filter(ledger=self).aggregate(Sum('debit'))['debit__sum'] or 0
        total_credit = JournalVoucherTransactions.objects.filter(ledger=self).aggregate(Sum('credit'))['credit__sum'] or 0

        self.debit = total_debit
        self.credit = total_credit
        self.save()

    def balance(self):
        return self.debit - self.credit


class JournalVoucherHd(models.Model):
    entry_no = models.CharField(max_length=10, null=False, blank=False,unique=True)
    entry_date = models.DateField(null=False, blank=False)
    narration = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)
    debit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_posted = models.BooleanField(default=False)

    ref = models.CharField(max_length=200, blank=False, null=False, unique=True)


    def update_totals(self):
        self.debit = JournalVoucherTransactions.objects.filter(hd=self).aggregate(Sum('debit'))['debit__sum'] or 0
        self.credit = JournalVoucherTransactions.objects.filter(hd=self).aggregate(Sum('credit'))['credit__sum'] or 0
        self.save()

    def trans(self):
        return [son.obj() for son in JournalVoucherTransactions.objects.filter(hd=self)]

    def obj(self):
        self.update_totals()
        return {
            "entry_no":self.entry_no,
            "entry_date":self.entry_date,
            "narration":self.narration,
            "created_by":self.created_by.username if self.created_by else '',
            'date_created':self.date_created,
            "time_created":self.time_created,
            "debit":self.debit,
            "credit":self.credit,
            "is_posted":self.is_posted,
            "ref":self.ref,
            "transactions":self.trans()
        }


class JournalVoucherTransactions(models.Model):
    hd = models.ForeignKey(JournalVoucherHd, on_delete=models.CASCADE, related_name='transactions')
    ledger = models.ForeignKey(AccountLedger, on_delete=models.CASCADE, related_name='journal_transactions')

    debit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_created = models.DateField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)

    def obj(self):
        return {
            "debit":self.debit,
            "credit":self.credit,
            "created_by":self.created_by.username if self.created_by else '',
            "date_created":self.date_created,
            "description":self.description,
            "ledger":f"{self.ledger.ledge_type} - {self.ledger.name}"
        }


def amount_to_words(amount):
    """Converts a number into its word representation in Ghana Cedis."""
    from decimal import Decimal
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    thousands = ["", "Thousand", "Million", "Billion"]

    def convert_hundreds(n):
        res = ""
        n = int(n)
        if n >= 100:
            res += units[n // 100] + " Hundred "
            n %= 100
        if n >= 10 and n <= 19:
            res += teens[n - 10] + " "
        else:
            if n >= 20:
                res += tens[n // 10] + " "
                n %= 10
            if n > 0:
                res += units[n] + " "
        return res

    if amount == 0:
        return "Zero Ghana Cedis Only"

    # Use integer arithmetic to avoid floating point issues
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    total_pesewas = int(amount * 100)
    whole_part, decimal_part = divmod(total_pesewas, 100)

    res = ""
    i = 0
    temp_whole = whole_part
    if temp_whole == 0:
        res = "Zero"
    else:
        while temp_whole > 0:
            if temp_whole % 1000 != 0:
                res = convert_hundreds(temp_whole % 1000) + thousands[i] + " " + res
            temp_whole //= 1000
            i += 1

    res = res.strip() + " Ghana Cedis"
    if decimal_part > 0:
        res += " and " + convert_hundreds(decimal_part).strip() + " Pesewas"
    
    return res.strip() + " Only"



class FocInvoiceHd(models.Model):

    entry_no = models.CharField(max_length=10, null=False, blank=False,unique=True)
    foc = models.ForeignKey(Contractor,models.CASCADE,related_name='invoices_foc')
    remarks = models.TextField(blank=True, null=True)
    invoice_date = models.DateField(null=False, blank=False)

    location = models.ForeignKey(Location,on_delete=models.PROTECT,null=True)

    is_valid = models.BooleanField(default=False)
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,related_name='invoices_validator')
    date_validated = models.DateField(null=True, blank=True)

    is_accepted = models.BooleanField(default=False)
    date_accepted = models.DateField(null=True, blank=True)
    accept_remark = models.TextField(blank=True, null=True)

    is_posted = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True)

    date_posted = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,related_name='invoices_creator')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    wht_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def update_totals(self):
        # 1. Sum up all items (Gross Amount - Tax Exclusive)
        gross_amount = FocInvoiceTransactions.objects.filter(invoice=self).aggregate(
            total=Coalesce(models.Sum('amount'), models.Value(0, output_field=models.DecimalField()))
        )['total']

        # 2. Calculate Admin Fee (Service Charge)
        invoice_year = str(self.invoice_date.year)
        service_rate = SSML_SERVICE_RATE.get(invoice_year, 0)
        service_amount = (Decimal(service_rate) / 100) * gross_amount

        # 3. Calculate Withholding Tax (WHT) at 5%
        wht_rate = Decimal('0.05')
        total_wht_amount = gross_amount * wht_rate

        # 4. Calculate Final Net Payable
        total_net_payable = gross_amount - total_wht_amount

        # 5. Update Header Fields
        self.gross_amount = gross_amount
        self.service_charge = service_amount
        self.taxable_amount = gross_amount
        self.tax_amount = 0
        self.wht_amount = total_wht_amount
        self.net_amount = total_net_payable
        self.save()

        # 6. Update individual lines
        for tr in FocInvoiceTransactions.objects.filter(invoice=self):
            tr.wht_amount = tr.amount * wht_rate
            tr.net_amount = tr.amount - tr.wht_amount
            tr.tax_amount = 0
            tr.save()

    def trans(self):


        return [ch.obj() for ch in FocInvoiceTransactions.objects.filter(invoice=self)]

    def previous(self):
        return FocInvoiceHd.objects.filter(pk__lt=self.pk).last().entry_no if FocInvoiceHd.objects.filter(pk__lt=self.pk).exists() else False

    def next(self):
        return FocInvoiceHd.objects.filter(pk__gt=self.pk).first().entry_no if FocInvoiceHd.objects.filter(pk__gt=self.pk).exists() else False

    def obj(self):
        self.update_totals()
        invoice_year = self.invoice_date.year
        self.update_assets()
        return {
            "entry_no":self.entry_no,
            'foc':self.foc.company,
            'date':self.invoice_date,
            'is_posted':self.is_posted,
            'is_accepted':self.is_accepted,
            'gross':format_currency(self.gross_amount),
            'tax':format_currency(self.tax_amount),
            'net':format_currency(self.net_amount),
            'remarks':self.remarks,
            "phone":self.foc.phone,
            "email":self.foc.email,
            "is_valid":self.is_valid,
            "transactions":self.trans(),
            "next":self.next(),
            "previous":self.previous(),
            'service_rate':SSML_SERVICE_RATE.get(f"{invoice_year}",0),
            'taxable':format_currency(self.taxable_amount),
            'invoice':self.invoice_pdf(),
            "service_charge":format_currency(self.service_charge),
            'wht_amount':format_currency(self.wht_amount)
        }

    def invoice_pdf(self):
        from fpdf import FPDF
        import uuid
        import os

        # Ensure totals are up to date
        self.update_totals()

        invoice_year = self.invoice_date.year
        service_rate = SSML_SERVICE_RATE.get(f"{invoice_year}", 0)

        class PDF(FPDF):
            def header(self):
                # Watermark
                self.set_font('Arial', 'B', 50)
                self.set_text_color(245, 245, 245)
                self.text(35, 140, COMPANY_DETAILS.get('name'))
                self.text(35, 190, COMPANY_DETAILS.get('name'))
                self.set_text_color(0, 0, 0)

            def footer(self):

                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Colors
        primary_color = (44, 62, 80)  # Dark Blue
        text_color = (52, 73, 94)

        # Header: Logo & Company Info
        logo_path = 'static/general/logo.png'
        if os.path.exists(logo_path):
            pdf.image(logo_path, 10, 10, 35)

        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(*primary_color)
        pdf.set_xy(50, 10)
        pdf.cell(100, 10, COMPANY_DETAILS.get('name'), 0, 1, 'L')

        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(50)
        pdf.cell(100, 4, COMPANY_DETAILS.get('address'), 0, 1, 'L')
        pdf.set_x(50)
        pdf.cell(100, 4, f"{COMPANY_DETAILS.get('email')} | {COMPANY_DETAILS.get('phone')}", 0, 1, 'L')
        pdf.set_x(50)
        pdf.cell(100, 4, f"Website: {COMPANY_DETAILS.get('website')}", 0, 1, 'L')

        # Invoice Label
        pdf.set_font('Arial', 'B', 24)
        pdf.set_text_color(*primary_color)
        pdf.set_xy(150, 10)
        pdf.cell(50, 20, 'INVOICE', 0, 1, 'R')

        pdf.ln(10)
        pdf.set_draw_color(*primary_color)
        pdf.line(10, 42, 200, 42)
        pdf.ln(5)

        # Two columns: Bill To and Invoice Info
        y_start = pdf.get_y()

        # Left Column: Bill To
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(95, 7, 'CONTRACTOR DETAILS (PAYABLE TO):', 0, 1, 'L')
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 6, str(self.foc.company[:30]).upper(), 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(95, 5, f"Location: {self.foc.city or 'N/A'}, {self.foc.region or ''}", 0, 1, 'L')
        pdf.cell(95, 5, f"Phone: {self.foc.phone}", 0, 1, 'L')
        pdf.cell(95, 5, f"Email: {self.foc.email}", 0, 1, 'L')

        # Right Column: Invoice Info
        pdf.set_xy(110, y_start)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, 7, 'Invoice Number:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(50, 7, str(self.entry_no), 0, 1, 'L')

        pdf.set_x(110)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, 7, 'Invoice Date:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(50, 7, self.invoice_date.strftime("%d %b, %Y") if self.invoice_date else '', 0, 1, 'L')

        pdf.set_x(110)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, 7, 'Location:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(50, 7, str(self.foc.city or 'N/A'), 0, 1, 'L')

        pdf.ln(15)

        # Summary Box for Amounts Breakdown
        pdf.set_fill_color(245, 247, 249)
        pdf.rect(10, pdf.get_y(), 190, 25, 'F')

        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(*primary_color)
        y_sum = pdf.get_y() + 2
        pdf.set_xy(10, y_sum)
        
        col_w = 47.5
        pdf.cell(col_w, 5, 'GROSS AMOUNT', 0, 0, 'C')
        pdf.cell(col_w, 5, 'ADMIN FEE', 0, 0, 'C')
        pdf.cell(col_w, 5, 'WHT (5%)', 0, 0, 'C')
        pdf.cell(col_w, 5, 'NET PAYABLE', 0, 1, 'C')

        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.set_x(10)
        pdf.cell(col_w, 10, f"{self.gross_amount:,.2f}", 0, 0, 'C')
        pdf.cell(col_w, 10, f"{self.service_charge:,.2f}", 0, 0, 'C')
        pdf.cell(col_w, 10, f"{self.wht_amount:,.2f}", 0, 0, 'C')
        pdf.set_text_color(231, 76, 60)
        pdf.cell(col_w, 10, f"{self.net_amount:,.2f}", 0, 1, 'C')

        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        # Remarks if any
        if self.remarks:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 5, 'REMARKS:', 0, 1, 'L')
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, str(self.remarks), 0, 'L')
            pdf.ln(5)

        # Table Header
        pdf.set_fill_color(*primary_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(10, 10, 'NO', 1, 0, 'C', fill=True)
        pdf.cell(55, 10, ' ITEM DESCRIPTION', 1, 0, 'L', fill=True)
        pdf.cell(15, 10, 'QTY', 1, 0, 'C', fill=True)
        pdf.cell(25, 10, 'RATE', 1, 0, 'C', fill=True)
        pdf.cell(25, 10, 'GROSS', 1, 0, 'C', fill=True)
        pdf.cell(25, 10, 'WHT (5%)', 1, 0, 'C', fill=True)
        pdf.cell(35, 10, 'NET AMT', 1, 1, 'C', fill=True)

        # Table Rows
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', '', 8)
        i = 1
        for tr in self.transactions.all():
            pdf.cell(10, 8, str(i), 1, 0, 'C')
            pdf.cell(55, 8, f" {tr.item}", 1, 0, 'L')
            pdf.cell(15, 8, f"{tr.quantity:,.0f}", 1, 0, 'C')
            pdf.cell(25, 8, f"{tr.rate:,.2f}", 1, 0, 'R')
            pdf.cell(25, 8, f"{tr.amount:,.2f}", 1, 0, 'R')
            pdf.cell(25, 8, f"{tr.wht_amount:,.2f}", 1, 0, 'R')
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(35, 8, f"{tr.net_amount:,.2f}", 1, 1, 'R')
            pdf.set_font('Arial', '', 8)
            i += 1

        # Summary Row
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(155, 10, 'TOTAL PAYABLE (GHS)', 1, 0, 'R')
        pdf.set_text_color(231, 76, 60)
        pdf.cell(35, 10, f"{self.net_amount:,.2f}", 1, 1, 'R')

        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', 'B', 9)
        pdf.ln(2)
        pdf.cell(0, 5, f"Amount in Words: {amount_to_words(self.net_amount)}", 0, 1, 'L')

        pdf.ln(10)

        # Bank Details
        pdf.set_fill_color(245, 247, 249)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, ' CONTRACTOR BANK ACCOUNT DETAILS', 0, 1, 'L', fill=True)
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, 6, 'Bank Name:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, str(self.foc.bank_name or 'N/A'), 0, 1, 'L')

        pdf.cell(40, 6, 'Account Number:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, str(self.foc.bank_acct_number or 'N/A'), 0, 1, 'L')

        pdf.cell(40, 6, 'Branch:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, str(self.foc.bank_branch or 'N/A'), 0, 1, 'L')

        pdf.ln(10)
        pdf.set_font('Arial', 'I', 9)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, 'This is a computer generated invoice and does not require a physical signature.', 0, 1, 'C')

        # Asset Installation Details Page
        assets = FocInvoiceAssets.objects.filter(invoice=self)
        if assets.exists():
            pdf.add_page()
            
            # Asset Page Header
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(*primary_color)
            pdf.cell(0, 10, 'ASSET INSTALLATION DETAILS', 0, 1, 'C')
            pdf.set_draw_color(*primary_color)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(8)

            # Assets Table Header
            pdf.set_fill_color(*primary_color)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 9)
            
            # Widths: NO:10, STS:40, SPN:40, INSTALLATION:70, PHASE:30 (Total 190)
            pdf.cell(10, 10, 'NO', 1, 0, 'C', fill=True)
            pdf.cell(40, 10, 'STS', 1, 0, 'C', fill=True)
            pdf.cell(40, 10, 'SPN', 1, 0, 'C', fill=True)
            pdf.cell(70, 10, 'INSTALLATION', 1, 0, 'C', fill=True)
            pdf.cell(30, 10, 'PHASE', 1, 1, 'C', fill=True)

            pdf.set_font('Arial', '', 8)
            pdf.set_text_color(0, 0, 0)
            
            for idx, asset in enumerate(assets, 1):
                asset.update_phase()
                pdf.cell(10, 8, str(idx), 1, 0, 'C')
                pdf.cell(40, 8, f" {asset.sts}", 1, 0, 'L')
                pdf.cell(40, 8, f" {asset.spn or 'N/A'}", 1, 0, 'L')
                pdf.cell(70, 8, f" {'N/A'}", 1, 0, 'L')
                # pdf.cell(70, 8, f" {asset.installation or 'N/A'}", 1, 0, 'L')
                pdf.cell(30, 8, f" {asset.phase or 'N/A'}", 1, 1, 'C')


        # Save file

        unique_name = f"{self.foc.company.replace(' ','_').lower()}invoice_{self.entry_no}_{uuid.uuid4().hex[:6]}.pdf"
        directory = os.path.join('static', 'tmp')
        if not os.path.exists(directory):
            os.makedirs(directory)

        file_path = os.path.join(directory, unique_name)
        pdf.output(file_path)

        return unique_name

    def update_assets(self):
        from datetime import date, datetime
        from calendar import monthrange

        d = datetime.strptime(str(self.invoice_date), '%Y-%m-%d').date()

        first_day = date(d.year, d.month, 1)
        last_day = date(d.year, d.month, monthrange(d.year, d.month)[1])


        services = ServiceOrder.objects.filter(
            contractor=self.foc,
            service_date__gte=first_day, service_date__lte=last_day,
            flag_for_invoice=True,
        )

        for sv in services:
            if FocInvoiceAssets.objects.filter(sts=sv.new_meter).count() == 0:
                FocInvoiceAssets.objects.create(
                    invoice=self,
                    sts=sv.new_meter,
                    spn=sv.spn,
                    phase=sv.meter_phase()
                )


class FocInvoiceTransactions(models.Model):
    invoice = models.ForeignKey(FocInvoiceHd, on_delete=models.CASCADE, related_name='transactions')
    item = models.CharField(max_length=255, null=False, blank=False,unique=False)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount =  models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_amount =  models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    wht_amount =  models.DecimalField(max_digits=10, decimal_places=2, default=0.00)




    def obj(self):
        return {
            'item':self.item,
            'quantity':self.quantity,
            'rate':self.rate,
            'amount':self.amount,
        }

class FocInvoiceAssets(models.Model):
    invoice = models.ForeignKey(FocInvoiceHd, on_delete=models.CASCADE, related_name='invoice')
    sts =  models.CharField(unique=True, max_length=255, null=False, blank=False)
    spn = models.CharField(max_length=255, null=True, blank=True)
    installation = models.CharField(max_length=255, null=True, blank=True)
    phase = models.CharField(max_length=255, null=True, blank=True)

    def update_phase(self):
        self.phase = ServiceOrder.objects.filter(new_meter=self.sts).last().meter_phase() if ServiceOrder.objects.filter(new_meter=self.sts).exists() else "NOT SET"
        self.save()

    def obj(self):
        return {
            'sts':self.sts,
            'spn':self.spn,
            'installation':self.installation,
            'phase':self.phase
        }


class FocComplianceType(models.Model):
    name = models.CharField(max_length=255,unique=True,null=False,blank=False)
    description = models.TextField()
    is_required = models.BooleanField(default=False)


    def obj(self):
        return {
            "name":self.name,
            "description":self.description,
            'is_required':self.is_required,
            "pk":self.pk
        }



class FocCompliance(models.Model):
    foc = models.ForeignKey(Contractor,models.PROTECT, null=False)
    c_type = models.ForeignKey(FocComplianceType,models.PROTECT, null=False)
    ref = models.CharField(max_length=255,null=False,blank=False)
    file = models.FileField(upload_to='static/general/foc_compliance/',null=False,blank=False)

    date_created = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = (('foc','c_type'),)

    def actual_file(self):
        if self.file:
            if os.path.exists(self.file.path):
                return self.file.url

        return None

    def obj(self):
        return  {
            "foc":self.foc.company,
            'compliance':self.c_type.name,
            "description":self.c_type.description,
            "pk":self.foc.pk,
            'file':self.actual_file()
        }


class EcgInvoiceHd(models.Model):

    entry_no = models.CharField(max_length=10, null=False, blank=False,unique=True)
    remarks = models.TextField(blank=True, null=True)
    invoice_date = models.DateField(null=False, blank=False)

    location = models.ForeignKey(Location,on_delete=models.PROTECT,null=True)

    is_valid = models.BooleanField(default=False)
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,related_name='invoicesecg_validator')
    date_validated = models.DateField(null=True, blank=True)

    is_accepted = models.BooleanField(default=False)
    date_accepted = models.DateField(null=True, blank=True)
    accept_remark = models.TextField(blank=True, null=True)

    is_posted = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True)

    date_posted = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,related_name='invoicesecg_creator')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    wht_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)


    def update_totals(self):
        pass

class EcgInvoiceTransactions(models.Model):
    invoice = models.ForeignKey(EcgInvoiceHd, on_delete=models.CASCADE, related_name='traecgnsactions')
    service = models.CharField(max_length=255, null=False, blank=False,unique=False)

    service_type = models.CharField(max_length=255, null=False, blank=False,unique=False)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount =  models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_amount =  models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    wht_amount =  models.DecimalField(max_digits=10, decimal_places=2, default=0.00)


class EcgInvoiceAssets(models.Model):
    invoice = models.ForeignKey(EcgInvoiceHd, on_delete=models.CASCADE, related_name='invecgoice')
    sts =  models.CharField(unique=True, max_length=255, null=False, blank=False)
    spn = models.CharField(max_length=255, null=True, blank=True)
    installation = models.CharField(max_length=255, null=True, blank=True)
    phase = models.CharField(max_length=255, null=True, blank=True)




