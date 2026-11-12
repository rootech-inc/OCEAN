"""
foc_reports.py - FOC Invoices Reporting Module
Generates Excel reports for FOC (Contractor) invoices over a specified date range.
Features:
- Pivot matrix: Each row is an FOC, each month in the range is a column.
- Cell values represent the net payable to the FOC after SSML Service Charge (Admin Fee) and Withholding Tax (WHT).
- Formula-driven row totals and column totals.
- Financial audit breakdown sheet (Gross, Admin Fee, WHT, Net).
- Detailed invoice register sheet.
"""

import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from calendar import monthrange

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.conf import settings
from django.db.models import Sum
from ssml.models import Contractor, FocInvoiceHd, FocInvoiceTransactions


def get_month_range(start_date, end_date):
    """
    Returns a list of dicts representing each calendar month between start_date and end_date.
    e.g. [{'year': 2025, 'month': 1, 'label': 'Jan 2025', 'key': '2025-01'}, ...]
    """
    months = []
    curr = start_date.replace(day=1)
    end_month = end_date.replace(day=1)

    while curr <= end_month:
        months.append({
            'year': curr.year,
            'month': curr.month,
            'label': curr.strftime('%b %Y'),
            'key': f"{curr.year}-{curr.month:02d}",
            'date': curr
        })
        if curr.month == 12:
            curr = curr.replace(year=curr.year + 1, month=1)
        else:
            curr = curr.replace(month=curr.month + 1)
    return months


def generate_foc_invoices_excel(start_date, end_date, output_path=None, include_all_contractors=True):
    """
    Generates a professional Excel workbook for FOC invoices in the given date range.
    
    Args:
        start_date (date|str): Start date (YYYY-MM-DD)
        end_date (date|str): End date (YYYY-MM-DD)
        output_path (str, optional): Target file path. Defaults to static/tmp/foc_invoices_matrix_<uuid>.xlsx
        include_all_contractors (bool): If True, lists all registered FOCs. If False, only those with invoices in period.
        
    Returns:
        dict: {
            'file_path': str (relative path),
            'absolute_path': str,
            'file_name': str,
            'months': list,
            'contractors_count': int,
            'invoices_count': int,
            'gross_total': float,
            'service_fee_total': float,
            'wht_total': float,
            'net_total': float
        }
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    if start_date > end_date:
        raise ValueError("start_date cannot be greater than end_date")

    # 1. Determine months in range
    months = get_month_range(start_date, end_date)

    # 2. Query all invoices in date range
    invoices_qs = FocInvoiceHd.objects.filter(
        invoice_date__gte=start_date,
        invoice_date__lte=end_date
    ).select_related('foc', 'location').order_by('invoice_date')

    # Update totals for any invoices where net_amount might be 0 or uncalculated
    for inv in invoices_qs:
        if inv.net_amount == 0 and inv.gross_amount == 0:
            try:
                inv.update_totals()
            except Exception:
                pass

    # 3. Determine contractors to list
    invoiced_foc_ids = set(invoices_qs.values_list('foc_id', flat=True))
    if include_all_contractors:
        contractors = list(Contractor.objects.all().order_by('company'))
    else:
        contractors = list(Contractor.objects.filter(id__in=invoiced_foc_ids).order_by('company'))

    # If no contractors found, fallback to all contractors
    if not contractors:
        contractors = list(Contractor.objects.all().order_by('company'))

    # Sort: Put contractors with invoices first, then alphabetically
    contractors.sort(key=lambda c: (0 if c.id in invoiced_foc_ids else 1, c.company.lower()))

    # 4. Aggregate data per contractor per month
    # contractor_id -> { (year, month): {'net': Decimal, 'gross': Decimal, 'service': Decimal, 'wht': Decimal, 'invoices': list} }
    matrix_data = {}
    for c in contractors:
        matrix_data[c.id] = {m['key']: {'net': Decimal('0.00'), 'gross': Decimal('0.00'), 'service': Decimal('0.00'), 'wht': Decimal('0.00'), 'count': 0} for m in months}

    total_gross = Decimal('0.00')
    total_service = Decimal('0.00')
    total_wht = Decimal('0.00')
    total_net = Decimal('0.00')

    for inv in invoices_qs:
        c_id = inv.foc_id
        if c_id not in matrix_data:
            matrix_data[c_id] = {m['key']: {'net': Decimal('0.00'), 'gross': Decimal('0.00'), 'service': Decimal('0.00'), 'wht': Decimal('0.00'), 'count': 0} for m in months}

        m_key = f"{inv.invoice_date.year}-{inv.invoice_date.month:02d}"
        if m_key in matrix_data[c_id]:
            matrix_data[c_id][m_key]['net'] += Decimal(str(inv.net_amount or 0))
            matrix_data[c_id][m_key]['gross'] += Decimal(str(inv.gross_amount or 0))
            matrix_data[c_id][m_key]['service'] += Decimal(str(inv.service_charge or 0))
            matrix_data[c_id][m_key]['wht'] += Decimal(str(inv.wht_amount or 0))
            matrix_data[c_id][m_key]['count'] += 1

        total_gross += Decimal(str(inv.gross_amount or 0))
        total_service += Decimal(str(inv.service_charge or 0))
        total_wht += Decimal(str(inv.wht_amount or 0))
        total_net += Decimal(str(inv.net_amount or 0))

    # 5. Build Excel Workbook with openpyxl
    wb = openpyxl.Workbook()
    
    # -------------------------------------------------------------
    # STYLES DEFINITION
    # -------------------------------------------------------------
    font_title = Font(name='Segoe UI', size=16, bold=True, color='1B365D')
    font_subtitle = Font(name='Segoe UI', size=10, italic=True, color='555555')
    font_info = Font(name='Segoe UI', size=9, color='333333')
    
    font_table_hdr = Font(name='Segoe UI', size=10, bold=True, color='FFFFFF')
    fill_table_hdr = PatternFill(start_color='1B365D', end_color='1B365D', fill_type='solid')
    fill_month_hdr = PatternFill(start_color='2C5282', end_color='2C5282', fill_type='solid')
    fill_total_hdr = PatternFill(start_color='1A365D', end_color='1A365D', fill_type='solid')

    font_data = Font(name='Segoe UI', size=9, color='000000')
    font_data_bold = Font(name='Segoe UI', size=9, bold=True, color='000000')
    font_total = Font(name='Segoe UI', size=10, bold=True, color='1B365D')
    
    fill_zebra = PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid')
    fill_total_row = PatternFill(start_color='E2E8F0', end_color='E2E8F0', fill_type='solid')
    fill_highlight_green = PatternFill(start_color='E6F4EA', end_color='E6F4EA', fill_type='solid')
    
    border_thin = Border(
        left=Side(style='thin', color='D0D7DE'),
        right=Side(style='thin', color='D0D7DE'),
        top=Side(style='thin', color='D0D7DE'),
        bottom=Side(style='thin', color='D0D7DE')
    )
    border_total_row = Border(
        left=Side(style='thin', color='B0B7BE'),
        right=Side(style='thin', color='B0B7BE'),
        top=Side(style='thin', color='1B365D'),
        bottom=Side(style='double', color='1B365D')
    )

    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')
    align_hdr = Alignment(horizontal='center', vertical='center', wrap_text=True)

    CURRENCY_FORMAT = '#,##0.00'

    # =============================================================
    # SHEET 1: MONTHLY NET PAYABLE MATRIX (PRIMARY REQUEST)
    # =============================================================
    ws1 = wb.active
    ws1.title = "Monthly Net Payable Matrix"
    ws1.views.sheetView[0].showGridLines = True

    # Title & Metadata
    company_name = getattr(settings, 'COMPANY_DETAILS', {}).get('name', 'ROOTECH / SSML')
    ws1['A1'] = str(company_name).upper()
    ws1['A1'].font = font_title
    
    ws1['A2'] = "FOC INVOICES MONTHLY SUMMARY REPORT (NET PAYABLE TO FOC)"
    ws1['A2'].font = Font(name='Segoe UI', size=12, bold=True, color='2C3E50')

    ws1['A3'] = f"Period: {start_date.strftime('%d %b, %Y')} to {end_date.strftime('%d %b, %Y')}  |  Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws1['A3'].font = font_subtitle

    ws1['A4'] = "Note: Values in month columns represent Net Amount Payable to FOC after SSML Service Charge and 5% Withholding Tax (WHT)."
    ws1['A4'].font = font_info

    # Headers for Matrix
    row_hdr = 6
    fixed_headers = ["NO.", "CONTRACTOR / FOC", "CODE", "BANK NAME", "ACCOUNT NUMBER", "BRANCH"]
    
    col_idx = 1
    for h in fixed_headers:
        cell = ws1.cell(row=row_hdr, column=col_idx, value=h)
        cell.font = font_table_hdr
        cell.fill = fill_table_hdr
        cell.alignment = align_hdr
        cell.border = border_thin
        col_idx += 1

    first_month_col = col_idx
    for m in months:
        cell = ws1.cell(row=row_hdr, column=col_idx, value=m['label'])
        cell.font = font_table_hdr
        cell.fill = fill_month_hdr
        cell.alignment = align_hdr
        cell.border = border_thin
        col_idx += 1
    last_month_col = col_idx - 1

    # Total Column Header
    total_col_idx = col_idx
    cell_tot = ws1.cell(row=row_hdr, column=total_col_idx, value="TOTAL NET PAYABLE")
    cell_tot.font = font_table_hdr
    cell_tot.fill = fill_total_hdr
    cell_tot.alignment = align_hdr
    cell_tot.border = border_thin
    ws1.row_dimensions[row_hdr].height = 28

    # Populate Contractor Rows
    curr_row = row_hdr + 1
    for idx, c in enumerate(contractors, 1):
        is_even = (idx % 2 == 0)
        row_fill = fill_zebra if is_even else None

        # Fixed contractor columns
        c_no = ws1.cell(row=curr_row, column=1, value=idx)
        c_no.alignment = align_center
        c_no.font = font_data
        c_no.border = border_thin
        if row_fill: c_no.fill = row_fill

        c_name = ws1.cell(row=curr_row, column=2, value=c.company)
        c_name.alignment = align_left
        c_name.font = font_data_bold
        c_name.border = border_thin
        if row_fill: c_name.fill = row_fill

        c_code = ws1.cell(row=curr_row, column=3, value=c.code or "-")
        c_code.alignment = align_center
        c_code.font = font_data
        c_code.border = border_thin
        if row_fill: c_code.fill = row_fill

        c_bank = ws1.cell(row=curr_row, column=4, value=c.bank_name or "N/A")
        c_bank.alignment = align_left
        c_bank.font = font_data
        c_bank.border = border_thin
        if row_fill: c_bank.fill = row_fill

        c_acct = ws1.cell(row=curr_row, column=5, value=c.bank_acct_number or "N/A")
        c_acct.alignment = align_center
        c_acct.font = font_data
        c_acct.border = border_thin
        if row_fill: c_acct.fill = row_fill

        c_branch = ws1.cell(row=curr_row, column=6, value=c.bank_branch or "N/A")
        c_branch.alignment = align_left
        c_branch.font = font_data
        c_branch.border = border_thin
        if row_fill: c_branch.fill = row_fill

        # Month Columns
        m_col = first_month_col
        for m in months:
            m_key = m['key']
            net_val = float(matrix_data.get(c.id, {}).get(m_key, {}).get('net', Decimal('0.00')))
            cell = ws1.cell(row=curr_row, column=m_col, value=net_val)
            cell.alignment = align_right
            cell.font = font_data
            cell.border = border_thin
            cell.number_format = CURRENCY_FORMAT
            if row_fill: cell.fill = row_fill
            m_col += 1

        # Contractor Row Total Formula: =SUM(first_month:last_month)
        first_m_letter = get_column_letter(first_month_col)
        last_m_letter = get_column_letter(last_month_col)
        tot_cell = ws1.cell(
            row=curr_row, 
            column=total_col_idx, 
            value=f"=SUM({first_m_letter}{curr_row}:{last_m_letter}{curr_row})"
        )
        tot_cell.alignment = align_right
        tot_cell.font = font_data_bold
        tot_cell.border = border_thin
        tot_cell.number_format = CURRENCY_FORMAT
        tot_cell.fill = fill_highlight_green
        
        ws1.row_dimensions[curr_row].height = 20
        curr_row += 1

    # Totals Row at the bottom
    tot_row = curr_row
    for c_i in range(1, first_month_col):
        cell = ws1.cell(row=tot_row, column=c_i)
        cell.border = border_total_row
        cell.fill = fill_total_row

    ws1.cell(row=tot_row, column=1, value="TOTAL MONTHLY NET PAYABLE")
    ws1.merge_cells(start_row=tot_row, start_column=1, end_row=tot_row, end_column=first_month_col - 1)
    cell_tot_lbl = ws1.cell(row=tot_row, column=1)
    cell_tot_lbl.font = font_total
    cell_tot_lbl.alignment = Alignment(horizontal='right', vertical='center')

    # Formulas for each month column
    data_start_row = row_hdr + 1
    data_end_row = tot_row - 1

    for c_i in range(first_month_col, last_month_col + 1):
        col_letter = get_column_letter(c_i)
        cell = ws1.cell(
            row=tot_row, 
            column=c_i, 
            value=f"=SUM({col_letter}{data_start_row}:{col_letter}{data_end_row})"
        )
        cell.font = font_total
        cell.alignment = align_right
        cell.border = border_total_row
        cell.fill = fill_total_row
        cell.number_format = CURRENCY_FORMAT

    # Grand Total (bottom right corner)
    tot_col_letter = get_column_letter(total_col_idx)
    grand_tot_cell = ws1.cell(
        row=tot_row, 
        column=total_col_idx, 
        value=f"=SUM({tot_col_letter}{data_start_row}:{tot_col_letter}{data_end_row})"
    )
    grand_tot_cell.font = Font(name='Segoe UI', size=10, bold=True, color='0E6251')
    grand_tot_cell.alignment = align_right
    grand_tot_cell.border = border_total_row
    grand_tot_cell.fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
    grand_tot_cell.number_format = CURRENCY_FORMAT
    ws1.row_dimensions[tot_row].height = 24

    # Pin frozen panes below header and after FOC company name
    ws1.freeze_panes = 'C7'

    # Auto-adjust column widths for Sheet 1
    for col in ws1.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Skip title rows 1 to 4 for column width calculation
            if cell.row < 6:
                continue
            val_str = str(cell.value or '')
            if cell.number_format == CURRENCY_FORMAT and isinstance(cell.value, (int, float, Decimal)):
                val_str = f"{float(cell.value):,.2f}"
            max_len = max(max_len, len(val_str))
        ws1.column_dimensions[col_letter].width = max(max_len + 4, 12)
    ws1.column_dimensions['A'].width = 6
    ws1.column_dimensions['B'].width = 34
    ws1.column_dimensions['C'].width = 12
    ws1.column_dimensions['D'].width = 22
    ws1.column_dimensions['E'].width = 18
    ws1.column_dimensions['F'].width = 18
    ws1.column_dimensions[get_column_letter(total_col_idx)].width = 22


    # =============================================================
    # SHEET 2: FINANCIAL BREAKDOWN (GROSS, ADMIN FEE, WHT, NET)
    # =============================================================
    ws2 = wb.create_sheet(title="Financial Breakdown")
    ws2.views.sheetView[0].showGridLines = True

    ws2['A1'] = "FOC INVOICES FINANCIAL BREAKDOWN BY MONTH"
    ws2['A1'].font = font_title
    ws2['A2'] = f"Detailed audit schedule showing Gross, Service Fee (10%), Taxable Amount, WHT (5%), and Net Payable."
    ws2['A2'].font = font_subtitle

    headers_s2 = ["NO.", "CONTRACTOR / FOC", "CODE", "MONTH", "INVOICES", "GROSS AMOUNT", "SERVICE FEE (10%)", "TAXABLE AMOUNT", "WHT (5%)", "NET PAYABLE"]
    ws2.row_dimensions[4].height = 26
    for c_i, h in enumerate(headers_s2, 1):
        cell = ws2.cell(row=4, column=c_i, value=h)
        cell.font = font_table_hdr
        cell.fill = fill_table_hdr
        cell.alignment = align_hdr
        cell.border = border_thin

    s2_row = 5
    line_no = 1
    for c in contractors:
        for m in months:
            m_key = m['key']
            d = matrix_data.get(c.id, {}).get(m_key, {})
            # Only include rows with invoice activity or show all with positive activity
            if d.get('count', 0) > 0:
                is_even = (line_no % 2 == 0)
                row_fill = fill_zebra if is_even else None

                ws2.cell(row=s2_row, column=1, value=line_no).alignment = align_center
                ws2.cell(row=s2_row, column=2, value=c.company).alignment = align_left
                ws2.cell(row=s2_row, column=3, value=c.code or "-").alignment = align_center
                ws2.cell(row=s2_row, column=4, value=m['label']).alignment = align_center
                ws2.cell(row=s2_row, column=5, value=d['count']).alignment = align_center
                
                c_gross = ws2.cell(row=s2_row, column=6, value=float(d['gross']))
                c_gross.number_format = CURRENCY_FORMAT
                c_gross.alignment = align_right

                c_srv = ws2.cell(row=s2_row, column=7, value=float(d['service']))
                c_srv.number_format = CURRENCY_FORMAT
                c_srv.alignment = align_right

                c_taxable = ws2.cell(row=s2_row, column=8, value=float(d['gross'] - d['service']))
                c_taxable.number_format = CURRENCY_FORMAT
                c_taxable.alignment = align_right

                c_wht = ws2.cell(row=s2_row, column=9, value=float(d['wht']))
                c_wht.number_format = CURRENCY_FORMAT
                c_wht.alignment = align_right

                c_net = ws2.cell(row=s2_row, column=10, value=float(d['net']))
                c_net.number_format = CURRENCY_FORMAT
                c_net.alignment = align_right
                c_net.font = font_data_bold
                c_net.fill = fill_highlight_green

                for col_k in range(1, 11):
                    ws2.cell(row=s2_row, column=col_k).border = border_thin
                    if row_fill and col_k != 10:
                        ws2.cell(row=s2_row, column=col_k).fill = row_fill

                s2_row += 1
                line_no += 1

    # Totals Row on Sheet 2
    if s2_row > 5:
        for c_i in range(1, 6):
            ws2.cell(row=s2_row, column=c_i).fill = fill_total_row
            ws2.cell(row=s2_row, column=c_i).border = border_total_row
        ws2.cell(row=s2_row, column=1, value="TOTALS")
        ws2.merge_cells(start_row=s2_row, start_column=1, end_row=s2_row, end_column=5)
        ws2.cell(row=s2_row, column=1).font = font_total
        ws2.cell(row=s2_row, column=1).alignment = Alignment(horizontal='right', vertical='center')

        for c_i in range(6, 11):
            col_letter = get_column_letter(c_i)
            cell = ws2.cell(row=s2_row, column=c_i, value=f"=SUM({col_letter}5:{col_letter}{s2_row - 1})")
            cell.font = font_total
            cell.alignment = align_right
            cell.border = border_total_row
            cell.fill = fill_total_row
            cell.number_format = CURRENCY_FORMAT
        ws2.row_dimensions[s2_row].height = 22

    # Column widths for Sheet 2
    ws2.column_dimensions['A'].width = 6
    ws2.column_dimensions['B'].width = 34
    ws2.column_dimensions['C'].width = 12
    ws2.column_dimensions['D'].width = 15
    ws2.column_dimensions['E'].width = 12
    ws2.column_dimensions['F'].width = 18
    ws2.column_dimensions['G'].width = 18
    ws2.column_dimensions['H'].width = 18
    ws2.column_dimensions['I'].width = 16
    ws2.column_dimensions['J'].width = 20
    ws2.freeze_panes = 'C5'


    # =============================================================
    # SHEET 3: INVOICE REGISTER (LINE-BY-LINE AUDIT TRAIL)
    # =============================================================
    ws3 = wb.create_sheet(title="Invoice Register")
    ws3.views.sheetView[0].showGridLines = True

    ws3['A1'] = "FOC INVOICE REGISTER"
    ws3['A1'].font = font_title
    ws3['A2'] = f"Complete listing of individual invoices from {start_date} to {end_date}."
    ws3['A2'].font = font_subtitle

    headers_s3 = [
        "ENTRY NO", "FOC / CONTRACTOR", "LOCATION", "INVOICE DATE", "MONTH",
        "GROSS AMOUNT", "SERVICE FEE", "TAXABLE AMOUNT", "WHT (5%)", "NET AMOUNT",
        "VALIDATED?", "ACCEPTED?", "POSTED?", "BANK NAME", "ACCOUNT NO"
    ]
    ws3.row_dimensions[4].height = 26
    for c_i, h in enumerate(headers_s3, 1):
        cell = ws3.cell(row=4, column=c_i, value=h)
        cell.font = font_table_hdr
        cell.fill = fill_table_hdr
        cell.alignment = align_hdr
        cell.border = border_thin

    s3_row = 5
    for inv_idx, inv in enumerate(invoices_qs, 1):
        is_even = (inv_idx % 2 == 0)
        row_fill = fill_zebra if is_even else None

        ws3.cell(row=s3_row, column=1, value=inv.entry_no).alignment = align_center
        ws3.cell(row=s3_row, column=2, value=inv.foc.company).alignment = align_left
        ws3.cell(row=s3_row, column=3, value=inv.location.loc_name if inv.location else "-").alignment = align_left
        ws3.cell(row=s3_row, column=4, value=str(inv.invoice_date)).alignment = align_center
        ws3.cell(row=s3_row, column=5, value=inv.invoice_date.strftime('%b %Y')).alignment = align_center

        cg = ws3.cell(row=s3_row, column=6, value=float(inv.gross_amount or 0))
        cg.number_format = CURRENCY_FORMAT; cg.alignment = align_right

        cs = ws3.cell(row=s3_row, column=7, value=float(inv.service_charge or 0))
        cs.number_format = CURRENCY_FORMAT; cs.alignment = align_right

        ct = ws3.cell(row=s3_row, column=8, value=float(inv.taxable_amount or 0))
        ct.number_format = CURRENCY_FORMAT; ct.alignment = align_right

        cw = ws3.cell(row=s3_row, column=9, value=float(inv.wht_amount or 0))
        cw.number_format = CURRENCY_FORMAT; cw.alignment = align_right

        cn = ws3.cell(row=s3_row, column=10, value=float(inv.net_amount or 0))
        cn.number_format = CURRENCY_FORMAT; cn.alignment = align_right
        cn.font = font_data_bold; cn.fill = fill_highlight_green

        ws3.cell(row=s3_row, column=11, value="YES" if inv.is_valid else "NO").alignment = align_center
        ws3.cell(row=s3_row, column=12, value="YES" if inv.is_accepted else "NO").alignment = align_center
        ws3.cell(row=s3_row, column=13, value="YES" if inv.is_posted else "NO").alignment = align_center
        ws3.cell(row=s3_row, column=14, value=inv.foc.bank_name or "N/A").alignment = align_left
        ws3.cell(row=s3_row, column=15, value=inv.foc.bank_acct_number or "N/A").alignment = align_center

        for col_k in range(1, 16):
            ws3.cell(row=s3_row, column=col_k).border = border_thin
            if row_fill and col_k != 10:
                ws3.cell(row=s3_row, column=col_k).fill = row_fill

        s3_row += 1

    # Totals Row on Sheet 3
    if s3_row > 5:
        for c_i in range(1, 6):
            ws3.cell(row=s3_row, column=c_i).fill = fill_total_row
            ws3.cell(row=s3_row, column=c_i).border = border_total_row
        ws3.cell(row=s3_row, column=1, value="TOTALS")
        ws3.merge_cells(start_row=s3_row, start_column=1, end_row=s3_row, end_column=5)
        ws3.cell(row=s3_row, column=1).font = font_total
        ws3.cell(row=s3_row, column=1).alignment = Alignment(horizontal='right', vertical='center')

        for c_i in range(6, 11):
            col_letter = get_column_letter(c_i)
            cell = ws3.cell(row=s3_row, column=c_i, value=f"=SUM({col_letter}5:{col_letter}{s3_row - 1})")
            cell.font = font_total
            cell.alignment = align_right
            cell.border = border_total_row
            cell.fill = fill_total_row
            cell.number_format = CURRENCY_FORMAT

        for c_i in range(11, 16):
            ws3.cell(row=s3_row, column=c_i).fill = fill_total_row
            ws3.cell(row=s3_row, column=c_i).border = border_total_row
        ws3.row_dimensions[s3_row].height = 22

    # Column widths for Sheet 3
    ws3.column_dimensions['A'].width = 16
    ws3.column_dimensions['B'].width = 32
    ws3.column_dimensions['C'].width = 18
    ws3.column_dimensions['D'].width = 14
    ws3.column_dimensions['E'].width = 14
    ws3.column_dimensions['F'].width = 16
    ws3.column_dimensions['G'].width = 16
    ws3.column_dimensions['H'].width = 16
    ws3.column_dimensions['I'].width = 14
    ws3.column_dimensions['J'].width = 18
    ws3.column_dimensions['K'].width = 13
    ws3.column_dimensions['L'].width = 13
    ws3.column_dimensions['M'].width = 12
    ws3.column_dimensions['N'].width = 20
    ws3.column_dimensions['O'].width = 18
    ws3.freeze_panes = 'C5'

    # 6. Save Workbook
    if not output_path:
        os.makedirs('static/tmp', exist_ok=True)
        unique_token = uuid.uuid4().hex[:6]
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        file_name = f"foc_monthly_invoices_{start_str}_to_{end_str}_{unique_token}.xlsx"
        output_path = f"static/tmp/{file_name}"
    else:
        file_name = os.path.basename(output_path)

    wb.save(output_path)

    return {
        'file_path': output_path,
        'absolute_path': os.path.abspath(output_path),
        'file_name': file_name,
        'months': [m['label'] for m in months],
        'contractors_count': len(contractors),
        'invoices_count': invoices_qs.count(),
        'gross_total': float(total_gross),
        'service_fee_total': float(total_service),
        'wht_total': float(total_wht),
        'net_total': float(total_net)
    }
