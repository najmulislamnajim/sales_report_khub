from datetime import date, datetime
from django.db import connection
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import get_period_list

# Create your views here.

class GetDashboardData(APIView):
    def get(self, request):
        # ------------------------------
        # Get Query Parameters
        # ------------------------------
        id = request.query_params.get('id')
        designation_id = int(request.query_params.get('designation_id'))
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        brand_name = request.query_params.get('brand_name')
        next_designation_id = designation_id-1
        
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
        # Fetch next user list + budget summary
        # ----------------------------------------------
        periods = get_period_list(start_date, end_date)
        params = [id,periods]
        if brand_name:
            brand = f"AND rst.brand_name = %s"
            params.append(brand_name)
        else:
            brand = ""
        params += [id,next_designation_id]
        query = f"""
        SELECT
                ul.work_area_t,
                budget_summary.budget_quantity,
                budget_summary.budget_amount
            FROM rpl_user_list ul
            CROSS JOIN (
                SELECT 
                    SUM(rst.budget) AS budget_quantity,
                    SUM(rst.budget_amount) AS budget_amount
                FROM rpl_sales_tty rst
                WHERE rst.{area} = %s
                  AND rst.period IN %s 
                  {brand}
            ) AS budget_summary
            WHERE ul.{designation} = %s
              AND ul.designation_id = %s;
        """

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        if not rows:
            return Response(
                {"success": False, "message": "No Budget & user list data found"},
                status=status.HTTP_404_NOT_FOUND
            )
        next_user_list = [row[0] for row in rows]
        budget_quantity = rows[0][1] if rows[0][1] else 0
        budget_amount = round(rows[0][2]) if rows[0][2] else 0
        
        # ------------------------------
        # Fetch current month sales
        # ------------------------------
        params = [start_date, end_date, id]
        if brand_name:
            brand = f"AND m.brand_name = %s"
            params.append(brand_name)
        else:
            brand = ""
            
        sales_query = f"""
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
            cursor.execute(sales_query, params)
            sales_rows = cursor.fetchall()

        # Aggregate total sales 
        sales_quantity = sum(row[3] for row in sales_rows)
        sales_amount = round(sum(row[2] for row in sales_rows))
        
        # ------------------------------
        # Prepare response data
        # ------------------------------
        data = {
            "designation_id": designation_id,
            "budget_quantity": budget_quantity,
            "budget_amount": budget_amount,
            "sales_quantity": sales_quantity or 0,
            "sales_amount": sales_amount or 0,
        }

        # Attach next user list based on designation
        if designation_id == 5:
            data["sm_list"] = next_user_list
        elif designation_id == 4:
            data["zm_list"] = next_user_list
        elif designation_id == 3:
            data["rm_list"] = next_user_list
        elif designation_id == 2:
            data["work_area_list"] = next_user_list
        else:
            data["mio"] = next_user_list
        
        return Response({"success": True, "message":"All data fetched successfully.", "data": data}, status=status.HTTP_200_OK)