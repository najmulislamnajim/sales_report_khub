import calendar
from datetime import date, datetime
from django.db import connection
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import get_period_list, calculate_prorata_between_dates, calculate_prorata_from_date, calculate_prorata_to_date, get_sales_data, get_budget_summary, get_current_month_data
from .sqls import get_4p_query

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
                budget_amount = round(sum([row[1] for row in sales_tty[1:-1]]))
                start_prorata_budget = calculate_prorata_from_date(start_date, sales_tty[0][1])
                end_prorata_budget = calculate_prorata_to_date(end_date, sales_tty[-1][1])
                
                first_date = start_date
                last_date = start_date.replace(day=calendar.monthrange(start_date.year, start_date.month)[1])
                start_sales_quantity, start_sales_amount = get_sales_data(first_date, last_date, designation, work_area_t, brand_name)
                
                first_date = end_date.replace(day=1)
                last_date = end_date
                end_sales_quantity, end_sales_amount = get_sales_data(first_date, last_date, designation, work_area_t, brand_name)
                budget_quantity = int(sum([row[0] for row in sales_tty]))
                budget_amount = budget_amount + start_prorata_budget + end_prorata_budget
                sales_quantity = int(sum([row[2] for row in sales_tty[1:-1]]))
                sales_quantity = sales_quantity + start_sales_quantity + end_sales_quantity
                sales_amount = round(sum([row[3] for row in sales_tty[1:-1]]))
                sales_amount = sales_amount + start_sales_amount + end_sales_amount
            elif not first_day_of_month and end_day_of_month:
                budget_amount = round(sum([row[1] for row in sales_tty[1:]]))
                start_prorata_budget = calculate_prorata_from_date(start_date, sales_tty[0][1])
                
                first_date = start_date
                last_date = start_date.replace(day=calendar.monthrange(start_date.year, start_date.month)[1])
                start_sales_quantity, start_sales_amount = get_sales_data(first_date, last_date, designation, work_area_t, brand_name)
                
                budget_quantity = int(sum([row[0] for row in sales_tty]))
                budget_amount = budget_amount + start_prorata_budget
                sales_quantity = int(sum([row[2] for row in sales_tty[1:]]))
                sales_quantity = sales_quantity + start_sales_quantity
                sales_amount = round(sum([row[3] for row in sales_tty[1:]]))
                sales_amount = sales_amount + start_sales_amount
            elif not end_day_of_month and first_day_of_month:
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
    
class GetDashboardReport(APIView):
    def get(self, request):
        # ------------------------------
        # Get Query Parameters
        # ------------------------------
        work_area_t = request.query_params.get('work_area_t')
        designation_id = int(request.query_params.get('designation_id'))
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        brands = request.query_params.get('brands')
        next_designation_id = max(designation_id - 1, 1)
        brands = brands.split(',') if brands else ""
        
        print(brands)
        brand_name = brands or []
        
        # ----------------------------
        # Validate Query Parameters
        # ----------------------------
        if not work_area_t or not designation_id:
            return Response(
                {"success": False, "message": "Missing work_area_t or designation_id in query parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )
        is_current_month = True if not start_date and not end_date else False
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
            
        # -----------------------------
        # Date Validation
        # -----------------------------
        current_year = date.today().year
        current_month = date.today().month
        if start_date.year != current_year and end_date.year != current_year and end_date > date.today():
            return Response(
                {"success": False, "message": "You must be select dates between current year till date."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
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
            
        # --------------------------------------
        # Fetch Budget Data Till Current Month
        # -------------------------------------
        periods = [f"{current_year}{str(i).zfill(2)}" for i in range(1, current_month+1)]
        budget_data_ytd = get_budget_summary(work_area_t, periods, designation, brand_name) # need to update for brand

        # -----------------------------------
        # Fetch Budget Data For Current Month
        # -----------------------------------
        period = f"{current_year}{str(current_month).zfill(2)}"
        budget_data = budget_data_ytd[period]
        budget_quantity_curr_month, prorata_quantity_curr_month, budget_amount_curr_month, prorata_budget_curr_month, sales_quantity_curr_month, sales_amount_curr_month = get_current_month_data(budget_data, designation, work_area_t, brand_name) # need to update for brand
        
        # ------------------------------------
        # Prepare Data For Response (initial)
        # ------------------------------------
        budget_quantity_till_prev_month = sum(val.get("budget_quantity") for key , val in budget_data_ytd.items() if key != period)
        budget_amount_till_prev_month = sum(val.get("budget_amount") for key , val in budget_data_ytd.items() if key != period)
        ytd_budget = budget_amount_till_prev_month + prorata_budget_curr_month
        sales_amount_till_prev_month = sum(val.get("sales_amount") for key , val in budget_data_ytd.items() if key != period)
        ytd_sales = sales_amount_till_prev_month + sales_amount_curr_month

        ytd_achievement = (ytd_sales / ytd_budget) * 100 if ytd_budget else 0
        val_achievement = (sales_amount_curr_month / prorata_budget_curr_month) * 100
        
        data = {
            "work_area_t": work_area_t,
            "designation_id": designation_id,
            "start_date": start_date,
            "end_date": end_date,
            "brand_name": brand_name,
            "budget_quantity": int(budget_quantity_curr_month),
            "prorata_quantity": int(prorata_quantity_curr_month),
            "budget_amount": round(budget_amount_curr_month),
            "prorata_budget": round(prorata_budget_curr_month),
            "sales_quantity": int(sales_quantity_curr_month),
            "sales_amount": round(sales_amount_curr_month),
            "val_achievement": round(val_achievement),
            "ytd_achievement": round(ytd_achievement)
        }
        
        if is_current_month:
            print("Current Month")
            return Response({"success": True, "message":"All data fetched successfully.", "data": data}, status=status.HTTP_200_OK)
        
        # ------------------------------------
        # If date range is selected
        # ------------------------------------
        selected_periods = get_period_list(start_date, end_date)
        first_day = (start_date.day == 1)
        last_day = (end_date.day == calendar.monthrange(end_date.year, end_date.month)[1])
        if len(selected_periods) == 1:
            print("Single Period : ", selected_periods)
            """
            If only one period is selected, calculate prorata budget & sales data.
            """
            period = selected_periods[0]
            budget_quantity = budget_data_ytd[period].get("budget_quantity", 0)
            budget_amount = budget_data_ytd[period].get("budget_amount", 0)
        
            prorata_quantity, prorata_budget = calculate_prorata_between_dates(start_date, end_date, budget_amount, budget_quantity)
            sales_quantity, sales_amount = get_sales_data(
                start_date, end_date, designation, work_area_t, brand_name
            ) # need to update for brand
            
            # Achievement %
            val_achievement = (sales_amount / prorata_budget) * 100 if prorata_budget else 0
        else:
            print("Multiple Periods")
            """
            If more than one period is selected, calculate prorata budget & sales data.
            """
            budget_quantity = sum(budget_data_ytd[period].get("budget_quantity", 0) for period in selected_periods)
            budget_amount = sum(budget_data_ytd[period].get("budget_amount", 0) for period in selected_periods)
            sales_quantity = sum(budget_data_ytd[period].get("sales_quantity", 0) for period in selected_periods)
            sales_amount = sum(budget_data_ytd[period].get("sales_amount", 0) for period in selected_periods)
            prorata_quantity = budget_quantity
            prorata_budget = budget_amount
            
            if not first_day:
                print("not first day")
                prorata_quantity_first, prorata_budget_first = calculate_prorata_from_date(start_date, budget_data_ytd[selected_periods[0]].get("budget_amount", 0), budget_data_ytd[selected_periods[0]].get("budget_quantity", 0))
                end_date_of_month = start_date.replace(day=calendar.monthrange(start_date.year, start_date.month)[1])
                sales_qty_first, sales_amount_first = get_sales_data(start_date, end_date_of_month, designation, work_area_t, brand_name) # need to update for brand
                period = f"{start_date.year}{str(start_date.month).zfill(2)}"
                prorata_quantity = prorata_quantity - budget_data_ytd[period].get("budget_quantity", 0) + prorata_quantity_first
                prorata_budget = prorata_budget - budget_data_ytd[period].get("budget_amount", 0) + prorata_budget_first
                sales_amount = sales_amount - budget_data_ytd[period].get("sales_amount", 0) + sales_amount_first
                sales_quantity = sales_quantity - budget_data_ytd[period].get("sales_quantity", 0) + sales_qty_first
            if not last_day:
                print("not last day")
                prorata_quantity_last,prorata_budget_last = calculate_prorata_to_date(end_date, budget_data_ytd[selected_periods[-1]].get("budget_amount", 0), budget_data_ytd[selected_periods[-1]].get("budget_quantity", 0))
                start_date_of_month = end_date.replace(day=1)
                sales_qty_last, sales_amount_last = get_sales_data(start_date_of_month, end_date, designation, work_area_t, brand_name) # need to update for brand
                period = f"{end_date.year}{str(end_date.month).zfill(2)}"
                prorata_quantity = prorata_quantity - budget_data_ytd[period].get("budget_quantity", 0) + prorata_quantity_last
                prorata_budget = prorata_budget - budget_data_ytd[period].get("budget_amount", 0) + prorata_budget_last
                sales_amount = sales_amount - budget_data_ytd[period].get("sales_amount", 0) + sales_amount_last
                sales_quantity = sales_quantity - budget_data_ytd[period].get("sales_quantity", 0) + sales_qty_last
            val_achievement = (sales_amount / prorata_budget) * 100 if prorata_budget else 0
        data["budget_quantity"] = int(budget_quantity)
        data["prorata_quantity"] = int(prorata_quantity)
        data["budget_amount"] = round(budget_amount)
        data["prorata_budget"] = round(prorata_budget)
        data["sales_quantity"] = int(sales_quantity)
        data["sales_amount"] = round(sales_amount)
        data["val_achievement"] = round(val_achievement)    
            
        return Response({"success": True, "message":"All data fetched successfully.", "data": data}, status=status.HTTP_200_OK)
    
    
class GetFourPData(APIView):
    def get(self, request):
        try:
            work_area_t = request.query_params.get('work_area_t')
            designation_id = int(request.query_params.get('designation_id'))
            if not work_area_t or not designation_id:
                return Response({"success": False, "message": "Missing work_area_t or designation_id in query parameters"}, status=status.HTTP_400_BAD_REQUEST)
            designation_mapping = {
                1: ("work_area_t", "work_area"),
                2: ("rm_code", "region_code"),
                3: ("zm_code", "zone_code"),
                4: ("sm_code", "sm_area_code"),
                5: ("gm_code", "gm_area_code")
            }
            designation, _ = designation_mapping.get(designation_id, ("work_area_t", "work_area"))
            if not designation:
                return Response(
                    {"success": False, "message": "Invalid designation_id"},
                    status=status.HTTP_404_NOT_FOUND
                )
            query = get_4p_query(designation)
            with connection.cursor() as cursor:
                cursor.execute(query, [work_area_t])
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            current_month = datetime.now().month
            
            total = sum(result.get("total", 0) for result in results)
            radiant = sum(result.get("radiant", 0) for result in results)
            current_month_total =  sum(result.get("total", 0) for result in results if result.get("month") == current_month) or 0
            current_month_radiant = sum(result.get("radiant", 0) for result in results if result.get("month") == current_month) or 0
            print(current_month_total)
            
            current_month_name = calendar.month_name[current_month]
            result = {
                "current_month_total": current_month_total,
                "current_month_radiant": current_month_radiant,
                "current_month_share" : round((current_month_radiant / current_month_total) * 100) if current_month_total else 0,
                "current_month_rank" : "",
                "total": total,
                "radiant": radiant,
                "total_share": round((radiant / total) * 100) if total else 0,
                "total_rank": "",
                "current_month_name": current_month_name,
                "current_day" : datetime.now().day
            }

            return Response({"success": True, "message":"All data fetched successfully.", "data": result}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)