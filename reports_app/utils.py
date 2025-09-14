import calendar
from datetime import date, datetime, timedelta
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
    return (working_days, total_working_days)


def calculate_prorata_from_date(date, amount, quantity):
    w,twd = get_working_days(date)
    prorata_quantity = (quantity/twd)*w
    prorata_amount =(amount/twd)*w
    return (prorata_quantity, prorata_amount)

# def calculate_prorata_to_date(date, amount):
#     w,twd = get_working_days(date)
#     nw = twd - w + 1
#     prorata_amount =(amount/twd)*nw
#     return round(prorata_amount)

def calculate_prorata_to_date(end_date, amount, quantity):
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
    prorata_quantity = (quantity / twd) * wd                                     
    prorata_amount = (amount / twd) * wd
    return (prorata_quantity, prorata_amount)
def calculate_prorata_between_dates(start_date, end_date, amount, quantity):
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
    prorata_quantity = (quantity / twd) * wd                                  
    prorata_amount = (amount / twd) * wd
    return (prorata_quantity, prorata_amount)

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
    sales_quantity = sum(row[3] for row in sales_data)
    sales_amount = sum(row[2] for row in sales_data)
    return (sales_quantity, sales_amount)

def get_budget_summary(work_area_t, periods, designation, brand_name=""):
    params = [work_area_t,periods]
    if brand_name:
        brand = f"AND rst.brand_name = %s"
        params.append(brand_name)
    else:
        brand = ""
        
    query = f"""
        SELECT
            rst.period, 
            SUM(rst.budget) AS budget_quantity,
            SUM(rst.budget_amount) AS budget_amount,
            SUM(rst.sales) AS sales_quantity,
            SUM(rst.sales_amount) AS sales_amount
        FROM rpl_sales_tty rst 
        WHERE rst.work_area IN (
                SELECT work_area_t 
                FROM rpl_user_list 
                WHERE {designation} = %s AND designation_id=1
            )
            AND rst.period IN %s 
            {brand}
        GROUP BY rst.period
        ORDER BY rst.period ASC;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        sales_tty = cursor.fetchall()
        
    if not sales_tty:
        return {}
    data = {}
    for row in sales_tty:
        data[row[0]] = {
            "budget_quantity": row[1],
            "budget_amount": row[2],
            "sales_quantity": row[3],
            "sales_amount": row[4]
        }
    return data

def get_current_month_data(budget_data, designation, work_area_t, brand_name=""):
    budget_quantity = budget_data.get('budget_quantity', 0)
    budget_amount = budget_data.get('budget_amount', 0)
    end_date = date.today()
    start_date = end_date.replace(day=1)
    
    prorata_quantity, prorata_budget = calculate_prorata_to_date(end_date, budget_amount, budget_quantity)
    sales_quantity, sales_amount = get_sales_data(start_date, end_date, designation, work_area_t, brand_name)
    
    return (budget_quantity,prorata_quantity, budget_amount, prorata_budget, sales_quantity, sales_amount)