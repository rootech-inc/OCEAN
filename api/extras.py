import pyodbc
from django.db.models import Sum

from admin_panel.models import  ProductTrans, ProductMaster, SmsApi
from inventory.models import GrnTran
from ocean.settings import DB_SERVER, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def cmm_connect():
    server = f"{DB_SERVER},{DB_PORT}"
    database = DB_NAME
    username = DB_USER
    password = DB_PASSWORD
    driver = '{ODBC Driver 17 for SQL Server}'  # Change this to the driver you're using
    connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    return pyodbc.connect(connection_string)
    # return connection.cursor()


# get stick
def get_stock(prod_pk, legend=None):

    return False


def suppler_details(prod_id, legend=None):
    if legend is None:
        legend = {}
    grns = GrnTran.objects.filter(product_id=prod_id)
    if grns.count() > 0:
        grn = grns.last()
        legend['supplier'] = grn.entry_no.supplier.company,
        legend['last_rec_price'] = grn.un_cost
        legend['last_rec_date'] = grn.entry_no.created_on
    else:
        legend['supplier'] = 'NONE',
        legend['last_rec_price'] = 0
        legend['last_rec_date'] = 'NONE'

    return legend


def cardex(prod_id, legend=None):

    if legend is None:
        legend = []

    trans = ProductTrans.objects.filter(product_id=prod_id)
    for tran in trans:
        legend.append(
            {
                'date': tran.created_on,
                'doc_type': tran.doc,
                'entry_no': tran.doc_ref,
                'loc_id': tran.loc.code,
                'loc_desc': tran.loc.descr,
                'qty': tran.tran_qty
            }
        )

    return legend


def sms_balance(api_key = ''):
    import requests

    endpoint = 'https://api.mnotify.com/api/balance/sms'

    url = endpoint + '?key=' + api_key
    print(url)
    response = requests.get(url)
    data = response.json()



    if data.get('status') == 'success':
        balance =  int(data.get('balance')) + int(data.get('bonus'))
        SmsApi.objects.filter(api_key=api_key).update(balance=balance)
        return balance
    else:
        return 0