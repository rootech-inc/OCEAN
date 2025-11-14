
from datetime import datetime
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum, F

from admin_panel.models import BankAccounts
from django.utils import timezone


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
            'services':self.services()
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
                Cardex.objects.filter(material=self, doc_type__in=['ISS', 'GR', 'RET'], **location_filter)
                .values('doc_type')
                .annotate(total_qty=Sum('qty'))
            )

            # convert result into a dictionary {doc_type: total_qty}
            totals = {row['doc_type']: row['total_qty'] or 0 for row in totals_qs}

            # safely fetch values (default 0 if not present)
            total_ISS = totals.get('ISS', 0)
            total_GR = totals.get('GR', 0)
            total_RET = totals.get('RET', 0)

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
        return Cardex.objects.filter(
            material=self,
            created_at__gte=start_date,
            created_at__lte=end_date,
            doc_type='GR'
            ).aggregate(total_qty=models.Sum('qty'))['total_qty'] or 0

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



    def __str__(self):
        return self.company

    def can_work(self):
        if ContractorError.objects.filter(contractor=self,is_cleared=False).exists():
            return False
        else:
            return True

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
            'code':self.code,
            'can_work':self.can_work(),
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
            
        }

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
            'balance':self.balance
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
        return ServiceOrder.objects.filter(service_type=self,service_date__lte=date).count()
    

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
    qty = models.DecimalField(decimal_places=2,default=0.00,max_digits=10)


    class Meta:
        unique_together = (('service','material'),)


    def obj(self):
        return {
            'id':self.id,
            'service':self.service.name,
            'qty':self.qty,

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
    ]
    status = models.CharField(max_length=255, choices=status_choices, default='pending')
    old_meter_no_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    new_meter_no_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    closed_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='closed_service_orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    location = models.ForeignKey(Location,on_delete=models.CASCADE,null=False)
    gps_code = models.CharField(unique=False,null=True,blank=True,max_length=255,default="none")
    phase = models.CharField(unique=False,null=True,blank=True,max_length=255,default="1 phase")
    is_boxed = models.BooleanField(default=False)
    box_no = models.IntegerField(max_length=100,default=0)
    final_readings = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    

    def items(self):
        obj = []
        items = ServiceOrderItem.objects.filter(service_order=self)
        for item in items:
            obj.append(item.obj())
        return obj

    def total_amount(self):
        return ServiceOrderItem.objects.filter(service_order=self).aggregate(total_amount=models.Sum('amount'))['total_amount'] or 0

    def sn_same_as_wo(self):
        if RetiredMetersTransactions.objects.filter(spn=self.spn).exists():

            row =  RetiredMetersTransactions.objects.filter(spn=self.spn).last()
            
            is_same = "NO" if len(row.diff_old_meter_no) == 0 else "YES"
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
    phase = models.CharField(max_length=255, choices=meter_type_choices, default='other')
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
    ]
    transaction_type = models.CharField(max_length=255, choices=transaction_type_choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    is_approved = models.BooleanField(default=False)
    is_posted = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    entry_no = models.CharField(max_length=255)

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
    

class InvoiceTransactions(models.Model):
    entry = models.ForeignKey(InvoiceHD,on_delete=models.CASCADE)
    service_date = models.DateField(null=False)
    asset = models.CharField(max_length=255,null=False, blank=False)
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
    sn = models.IntegerField(max_length=100)
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