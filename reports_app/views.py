import calendar
from datetime import date, datetime
from django.db import connection
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import get_period_list, calculate_prorata_between_dates, calculate_prorata_from_date, calculate_prorata_to_date, get_sales_data

# Create your views here.

class GetDashboardData(APIView):
    def get(self, request):
        # ------------------------------
        # Get Query Parameters
        # ------------------------------
        work_area_t = request.query_params.get('work_area_t')
        designation_id = int(request.query_params.get('designation_id'))
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        brand_name = request.query_params.get('brand_name', "")
        next_designation_id = max(designation_id - 1, 1)
        
        # ----------------------------
        # Validate Query Parameters
        # ----------------------------
        if not work_area_t or not designation_id:
            return Response(
                {"success": False, "message": "Missing work_area_t or designation_id in query parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ----------------------------
        # Convert Dates
        # ----------------------------
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            start_date = date.today().replace(day=1)
        
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end_date = date.today()
        
        # ------------------------------
        # Map designation to DB columns
        # ------------------------------
        designation_mapping = {
            1: ("work_area_t", "work_area"),
            2: ("rm_code", "region_code"),
            3: ("zm_code", "zone_code"),
            4: ("sm_code", "sm_area_code"),
            5: ("gm_code", "gm_area_code")
        }
        designation, area = designation_mapping.get(designation_id, (None, None))
        if not designation:
            return Response(
                {"success": False, "message": "Invalid designation_id"},
                status=status.HTTP_404_NOT_FOUND
            )
        # ----------------------------------------------
        # Fetch budget summary
        # ----------------------------------------------
        periods = get_period_list(start_date, end_date)
        params = [work_area_t,periods]
        if brand_name:
            brand = f"AND rst.brand_name = %s"
            params.append(brand_name)
        else:
            brand = ""
        query = f"""
            SELECT 
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
            return Response(
                {"success": False, "message": "No Budget data found"},
                status=status.HTTP_404_NOT_FOUND
            )
        # budget_quantity = int(rows[0][0] if rows[0][0] else 0)
        # budget_amount = round(rows[0][1]) if rows[0][1] else 0
        
        # --------------------------------
        # I Don't Know
        # --------------------------------
        if len(periods) == 1:
            print("i am in single period")
            budget_quantity = int(sum([row[0] for row in sales_tty]))
            budget_amount = round(sum([row[1] for row in sales_tty]))
            prorata_budget = calculate_prorata_between_dates(start_date, end_date, budget_amount)
            budget_amount = prorata_budget
            sales_quantity, sales_amount = get_sales_data(start_date, end_date, designation, work_area_t, brand_name)  
        else:
            # Check First Day of Month and Last Day of Month
            first_day_of_month = (start_date.day == 1)
            end_day_of_month = (end_date.day == calendar.monthrange(end_date.year, end_date.month)[1])
                
            # Calculate Budget
            if not first_day_of_month and not end_day_of_month:
                print("i am in if block")
                budget_amount = round(sum([row[1] for row in sales_tty[1:-1]]))
                start_prorata_budget = calculate_prorata_from_date(start_date, sales_tty[0][1])
                end_prorata_budget = calculate_prorata_to_date(end_date, sales_tty[-1][1])
                
                first_date = start_date
                year , month = first_date.year, first_date.month
                last_date = calendar.monthrange(year, month)[1]
                start_sales_quantity, start_sales_amount = get_sales_data(first_date, last_date, designation, work_area_t, brand_name)
                
                first_date = end_date.replace(day=1)
                last_date = end_date
                end_sales_quantity, end_sales_amount = get_sales_data(first_date, last_date, designation, work_area_t, brand_name)
                print(budget_amount)
                budget_quantity = int(sum([row[0] for row in sales_tty]))
                budget_amount = budget_amount + start_prorata_budget + end_prorata_budget
                sales_quantity = int(sum([row[2] for row in sales_tty[1:-1]]))
                sales_quantity = sales_quantity + start_sales_quantity + end_sales_quantity
                sales_amount = round(sum([row[3] for row in sales_tty[1:-1]]))
                sales_amount = sales_amount + start_sales_amount + end_sales_amount
            elif not first_day_of_month:
                print("i am in first elif block")
                budget_amount = round(sum([row[1] for row in sales_tty[1:]]))
                start_prorata_budget = calculate_prorata_from_date(start_date, sales_tty[0][1])
                
                first_date = start_date
                year , month = first_date.year, first_date.month
                last_date = calendar.monthrange(year, month)[1]
                start_sales_quantity, start_sales_amount = get_sales_data(first_date, last_date, designation, work_area_t, brand_name)
                
                budget_quantity = int(sum([row[0] for row in sales_tty]))
                budget_amount = budget_amount + start_prorata_budget
                sales_quantity = int(sum([row[2] for row in sales_tty[1:]]))
                sales_quantity = sales_quantity + start_sales_quantity
                sales_amount = round(sum([row[3] for row in sales_tty[1:]]))
                sales_amount = sales_amount + start_sales_amount
            elif not end_day_of_month:
                print("i am in last elif block")
                budget_amount = round(sum([row[1] for row in sales_tty[:-1]]))
                end_prorata_budget = calculate_prorata_to_date(end_date, sales_tty[-1][1])
                
                first_date = end_date.replace(day=1)
                last_date = end_date
                end_sales_quantity, end_sales_amount = get_sales_data(first_date, last_date, designation, work_area_t, brand_name)
                
                budget_quantity = int(sum([row[0] for row in sales_tty]))
                budget_amount = budget_amount + end_prorata_budget
                sales_quantity = int(sum([row[2] for row in sales_tty[:-1]]))
                sales_quantity = sales_quantity + end_sales_quantity
                sales_amount = round(sum([row[3] for row in sales_tty[:-1]]))
                sales_amount = sales_amount + end_sales_amount
            else:
                print("i am in else block")
                budget_quantity = int(sum([row[0] for row in sales_tty]))
                budget_amount = round(sum([row[1] for row in sales_tty]))
                sales_quantity = int(sum([row[2] for row in sales_tty]))
                sales_amount = round(sum([row[3] for row in sales_tty]))
        
        # ------------------------------
        # Prepare response data
        # ------------------------------
        data = {
            "work_area_t": work_area_t,
            "designation_id": designation_id,
            "start_date": start_date,
            "end_date": end_date,
            "brand_name": brand_name,
            "next_designation_id": next_designation_id,
            "budget_quantity": budget_quantity,
            "budget_amount": budget_amount,
            "sales_quantity": sales_quantity or 0,
            "sales_amount": sales_amount or 0,
        }
        
        return Response({"success": True, "message":"All data fetched successfully.", "data": data}, status=status.HTTP_200_OK)