from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection
from rest_framework import status
from datetime import date

class LoginView(APIView):
    """
    Login API View
    ----------------
    1. Authenticate user by work_area_t and password.
    2. Determine current designation and next designation.
    3. Fetch next user list + budget summary.
    4. Fetch current month sales.
    5. Return aggregated data.
    """

    def post(self, request):
        work_area_t = request.data.get('id')
        password = request.data.get('password')
        
        # ------------------------------
        # Step 1: Authenticate user
        # ------------------------------
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT designation_id, work_area_t, name, group_name FROM rpl_user_list WHERE work_area_t = %s AND password = %s",
                [work_area_t, password]
            )
            row = cursor.fetchone()
            
        if not row:
            return Response(
                {"success": False, "message": "Invalid work_area or password"},
                status=status.HTTP_404_NOT_FOUND
            )
            
        designation_id = row[0]
        territory_code = row[1]
        name = row[2]
        brand_name=row[3]
        next_designation_id = max(designation_id - 1, 1)
        period = date.today().strftime('%Y%m')

        # ------------------------------
        # Step 2: Map designation to DB columns
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

        # ------------------------------
        # Step 3: Fetch next user list + budget summary in one query
        # ------------------------------
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
                  AND rst.period = %s
            ) AS budget_summary
            WHERE ul.{designation} = %s
              AND ul.designation_id = %s;
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [work_area_t, period, work_area_t, next_designation_id])
            rows = cursor.fetchall()

        if not rows:
            return Response(
                {"success": False, "message": "No data found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        next_user_list = [row[0] for row in rows]
        budget_quantity = rows[0][1]
        budget_amount = rows[0][2]
        
        # ---------------------------
        # Fetch Brand Names
        # ---------------------------
        brand_query = f"""
            SELECT DISTINCT brand_name
            FROM rpl_material 
            WHERE team1=%s;
        """
        with connection.cursor() as cursor:
            cursor.execute(brand_query, [brand_name])
            brand_names = [row[0] for row in cursor.fetchall()]
        
        

        # ------------------------------
        # Step 4: Fetch current month sales
        # ------------------------------
        first_day = date.today().replace(day=1)
        today = date.today()

        sales_query = f"""
            SELECT rsis.territory_code AS work_area, rsis.billing_date,
                   (SUM(IF(billing_type != 'ZRE', tp*quantity,0)) - SUM(IF(billing_type = 'ZRE', tp*quantity,0))) AS sales_val,
                   (SUM(IF(billing_type != 'ZRE', quantity,0)) - SUM(IF(billing_type = 'ZRE', quantity,0))) AS sales_quantity
            FROM rpl_sales_info_sap rsis
            WHERE rsis.billing_date BETWEEN %s AND %s
              AND rsis.billing_type IN ('ZD1','ZD2','ZD3','ZD4','ZRE')
              AND rsis.cancel != 'X'
              AND rsis.territory_code IN (
                  SELECT work_area_t
                  FROM rpl_user_list
                  WHERE {designation} = %s
                    AND designation_id = 1
              )
            GROUP BY rsis.billing_date, rsis.billing_type, rsis.territory_code;
        """
        with connection.cursor() as cursor:
            cursor.execute(sales_query, [first_day, today, work_area_t])
            sales_rows = cursor.fetchall()

        # Aggregate total sales 
        sales_quantity = sum(row[3] for row in sales_rows)
        sales_amount = sum(row[2] for row in sales_rows)

        # ------------------------------
        # Step 5: Prepare response data
        # ------------------------------
        data = {
            "territory_code": territory_code,
            "name": name,
            "designation_id": designation_id,
            "next_designation_id": next_designation_id,
            "budget_quantity": budget_quantity,
            "budget_amount": round(budget_amount),
            "sales_quantity": sales_quantity,
            "sales_amount": round(sales_amount),
            "brand_names": brand_names
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

        return Response(
            {"success": True, "message": "Login successful.", "data": data},
            status=status.HTTP_200_OK
        )
