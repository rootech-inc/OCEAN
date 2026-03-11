from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import Location
import openpyxl

@csrf_exempt
@login_required
def import_locations(request):
    if request.method == 'POST':
        if 'excel_file' not in request.FILES:
            return JsonResponse({'status_code': 400, 'message': 'No file uploaded'})
        
        excel_file = request.FILES['excel_file']
        try:
            wb = openpyxl.load_workbook(excel_file)
            sheet = wb.active
            headers = [str(cell.value).strip().upper() for cell in sheet[1]]
            
            # Expected headers based on export
            required_headers = ["LOC ID", "NAME", "COUNTRY", "CITY", "STREET", "ADDRESS", "PHONE", "EMAIL", "DEFAULT"]
            for header in required_headers:
                if header not in headers:
                    return JsonResponse({'status_code': 400, 'message': f'Missing required column: {header}'})
            
            created_count = 0
            updated_count = 0
            
            for row in sheet.iter_rows(min_row=2, values_only=True):
                row_dict = dict(zip(headers, row))
                print(row_dict)
                if not row_dict.get('LOC ID'):
                    continue
                
                loc_id = str(row_dict['LOC ID']).strip()
                name = str(row_dict['NAME']).strip()
                country = str(row_dict['COUNTRY']).strip()
                city = str(row_dict['CITY']).strip()
                street = str(row_dict['STREET']).strip()
                address = str(row_dict['ADDRESS']).strip()
                phone = str(row_dict['PHONE']).strip()
                email = str(row_dict['EMAIL']).strip()
                is_default_str = str(row_dict['DEFAULT']).strip().upper()
                is_default = True if is_default_str == 'YES' else False
                loc_desc = f"{name}, {city}, {country}"
                
                loc, created = Location.objects.update_or_create(
                    loc_id=loc_id,
                    defaults={
                        'loc_name': name,
                        'country': country,
                        'city': city,
                        'street': street,
                        'address': address,
                        'phone': phone,
                        'email': email,
                        'is_default': is_default,
                        'loc_desc': loc_desc,
                        'created_by': request.user
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            return JsonResponse({
                'status_code': 200, 
                'message': f'Import successful. Created: {created_count}, Updated: {updated_count}'
            })
            
        except Exception as e:
            return JsonResponse({'status_code': 500, 'message': f'Error processing file: {str(e)}'})

    return JsonResponse({'status_code': 405, 'message': 'Method not allowed'})
