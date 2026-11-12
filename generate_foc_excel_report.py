#!/usr/bin/env python
"""
generate_foc_excel_report.py
----------------------------
Command-line utility to generate the FOC Invoices Monthly Excel Report.
Outputs:
- Monthly Net Payable Matrix (Rows = FOCs, Columns = Months, Values = Net to Pay after WHT and Service Fee)
- Financial Deductions Breakdown (Gross, Service Fee 10%, Taxable, WHT 5%, Net)
- Complete Invoices Register

Usage:
    python generate_foc_excel_report.py
    python generate_foc_excel_report.py --start-date 2025-01-01 --end-date 2025-12-31
    python generate_foc_excel_report.py --start-date 2025-01-01 --end-date 2025-12-31 --out foc_report_2025.xlsx
"""

import os
import sys
import argparse
from datetime import date, datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ocean.settings')
try:
    import django
    django.setup()
except Exception as e:
    print(f"Error initializing Django: {e}", file=sys.stderr)
    sys.exit(1)

from ssml.models import FocInvoiceHd, Contractor
from ssml.foc_reports import generate_foc_invoices_excel


def main():
    parser = argparse.ArgumentParser(description="Generate FOC Monthly Invoices Excel Report")
    parser.add_argument("--start-date", dest="start_date", help="Start date (YYYY-MM-DD). Defaults to earliest invoice or Jan 1 of current year.")
    parser.add_argument("--end-date", dest="end_date", help="End date (YYYY-MM-DD). Defaults to latest invoice or Dec 31 of current year.")
    parser.add_argument("--out", dest="output_file", help="Custom output path for the generated Excel file.")
    parser.add_argument("--all-foc", dest="all_foc", action="store_true", default=True, help="Include all registered FOCs (default: True).")
    parser.add_argument("--only-invoiced", dest="only_invoiced", action="store_true", default=False, help="Include only FOCs with invoices in the date range.")

    args = parser.parse_args()

    # Determine default date range from database if not supplied
    if not args.start_date or not args.end_date:
        if FocInvoiceHd.objects.exists():
            first_inv = FocInvoiceHd.objects.order_by('invoice_date').first()
            last_inv = FocInvoiceHd.objects.order_by('invoice_date').last()
            # Expand to full years or months
            default_start = first_inv.invoice_date.replace(month=1, day=1) if not args.start_date else datetime.strptime(args.start_date, '%Y-%m-%d').date()
            default_end = last_inv.invoice_date.replace(month=12, day=31) if not args.end_date else datetime.strptime(args.end_date, '%Y-%m-%d').date()
        else:
            today = date.today()
            default_start = date(today.year, 1, 1)
            default_end = date(today.year, 12, 31)

        start_date = default_start if not args.start_date else datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = default_end if not args.end_date else datetime.strptime(args.end_date, '%Y-%m-%d').date()
    else:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()

    include_all = not args.only_invoiced

    print("=" * 75)
    print(" FOC INVOICES MONTHLY EXCEL REPORT GENERATOR")
    print("=" * 75)
    print(f"Date Range     : {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")
    print(f"Contractors    : {'All registered FOCs' if include_all else 'Only invoiced FOCs'}")
    print("-" * 75)

    try:
        report = generate_foc_invoices_excel(
            start_date=start_date,
            end_date=end_date,
            output_path=args.output_file,
            include_all_contractors=include_all
        )

        print(f"[+] Total Invoices in Range  : {report['invoices_count']}")
        print(f"[+] Total FOC Contractors    : {report['contractors_count']}")
        print(f"[+] Total Months Spanned     : {len(report['months'])} ({', '.join(report['months'])})")
        print(f"[+] Gross Amount Billed      : GHS {report['gross_total']:,.2f}")
        print(f"[+] Service Fee / Admin (10%): GHS {report['service_fee_total']:,.2f}")
        print(f"[+] Withholding Tax (WHT 5%) : GHS {report['wht_total']:,.2f}")
        print(f"[+] TOTAL NET PAYABLE TO FOC : GHS {report['net_total']:,.2f}")
        print("-" * 75)
        print(f"[SUCCESS] Excel report generated successfully!")
        print(f"Location: {report['absolute_path']}")
        print("=" * 75)
        return 0

    except Exception as e:
        print(f"[ERROR] Failed to generate report: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
