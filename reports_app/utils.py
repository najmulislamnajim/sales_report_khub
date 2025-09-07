import calendar
from datetime import datetime, timedelta
from rest_framework.response import Response
from rest_framework import status
from django.db import connection

def get_period_list(start_date, end_date):
    periods = []
    current = start_date.replace(day=1)

    while current <= end_date:
        periods.append(current.strftime("%Y%m"))
        # move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)
    return periods


def get_working_days(date):
    day, month , year  = date.day, date.month, date.year
    last_day = calendar.monthrange(year, month)[1]
    total_working_days = 0
    working_days = 0
    for d in range(1, last_day + 1):
        current_date = datetime(year, month, d)
        if current_date.weekday() != 4:
            total_working_days += 1
            if d >= day:
                working_days += 1
    print(working_days, total_working_days)
    return (working_days, total_working_days)


def calculate_prorata_from_date(date, amount):
    print(amount)
    w,twd = get_working_days(date)
    prorata_amount =(amount/twd)*w
    print(prorata_amount)
    return round(prorata_amount)

# def calculate_prorata_to_date(date, amount):
#     w,twd = get_working_days(date)
#     nw = twd - w + 1
#     prorata_amount =(amount/twd)*nw
#     return round(prorata_amount)

def calculate_prorata_to_date(end_date, amount):
    print(amount)
    last_day = calendar.monthrange(end_date.year, end_date.month)[1]
    end_day = end_date.day
    twd = 0
    wd = 0
    for d in range(1, last_day + 1):
        current_date = datetime(end_date.year, end_date.month, d)
        if current_date.weekday() != 4:
            twd += 1
            if d <= end_day:
                wd += 1
    print(wd, twd)                                     
    prorata_amount = (amount / twd) * wd
    print(prorata_amount)
    return round(prorata_amount)
def calculate_prorata_between_dates(start_date, end_date, amount):
    last_day = calendar.monthrange(start_date.year, start_date.month)[1]
    sd = start_date.day
    ed = end_date.day
    twd = 0
    wd = 0
    for d in range(1, last_day + 1):
        current_date = datetime(start_date.year, start_date.month, d)
        if current_date.weekday() != 4:
            twd += 1
            if d >= sd and d <= ed:
                wd += 1
    print(wd, twd)                                     
    prorata_amount = (amount / twd) * wd
    return round(prorata_amount)

def get_sales_data(start_date, end_date, designation, work_area_t, brand_name=""):
    params = [start_date, end_date, work_area_t]
    if brand_name:
        brand = f"AND m.brand_name = %s"
        params.append(brand_name)
    else:
        brand = ""
        
    query = f"""
        SELECT rsis.territory_code AS work_area, rsis.billing_date,
                (SUM(IF(billing_type != 'ZRE', tp*quantity,0)) - SUM(IF(billing_type = 'ZRE', tp*quantity,0))) AS sales_val,
                (SUM(IF(billing_type != 'ZRE', quantity,0)) - SUM(IF(billing_type = 'ZRE', quantity,0))) AS sales_quantity
        FROM rpl_sales_info_sap rsis
        INNER JOIN rpl_material m ON rsis.matnr = m.matnr
        WHERE rsis.billing_date BETWEEN %s AND %s
            AND rsis.billing_type IN ('ZD1','ZD2','ZD3','ZD4','ZRE')
            AND rsis.cancel != 'X'
            AND rsis.territory_code IN (
                SELECT work_area_t
                FROM rpl_user_list
                WHERE {designation} = %s
                AND designation_id = 1
            )
            {brand} 
        GROUP BY rsis.billing_date, rsis.billing_type, rsis.territory_code;
    """
    with connection.cursor() as cursor:
            cursor.execute(query, params)
            sales_data = cursor.fetchall()
    if not sales_data:
        return (0, 0)
    sales_quantity = int(sum(row[3] for row in sales_data))
    sales_amount = round(sum(row[2] for row in sales_data))
    return (sales_quantity, sales_amount)