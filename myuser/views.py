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
    """

    def post(self, request):
        work_area_t = request.data.get('id')
        password = request.data.get('password')
        
        # ------------------------------
        # Step 1: Authenticate user
        # ------------------------------
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT designation_id, work_area_t, name, group_name, address FROM rpl_user_list WHERE work_area_t = %s AND password = %s",
                [work_area_t, password]
            )
            row = cursor.fetchone()
            
        if not row:
            return Response(
                {"success": False, "message": "Invalid work_area or password"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        data = {
            "designation_id": row[0],
            "work_area_t": row[1],
            "name": row[2],
            "group_name": row[3],
            "address": row[4]
        }

        return Response(
            {"success": True, "message": "Login successful.", "data":data},
            status=status.HTTP_200_OK
        )

class GetBrands(APIView):
    def get(self,request):
        group_name = request.query_params.get('group_name')
        # ---------------------------
        # Fetch Brand Names
        # ---------------------------
        brand_query = f"""
            SELECT DISTINCT brand_name
            FROM rpl_material 
            WHERE team1=%s;
        """
        with connection.cursor() as cursor:
            cursor.execute(brand_query, [group_name])
            brand_names = [row[0] for row in cursor.fetchall()]
            
        return Response(
            {"success": True, "message": "Brand names fetched successfully.", "data": brand_names},
            status=status.HTTP_200_OK
        )
        
class GetNextUserList(APIView):
    def get(self, request):
        work_area_t = request.query_params.get('work_area_t')
        designation_id = int(request.query_params.get('designation_id'))
        designation_mapping = {
            1: "work_area_t",
            2: "rm_code",
            3: "zm_code",
            4: "sm_code",
            5: "gm_code"
        }
        next_designation_id = max(designation_id - 1, 1)
        query = f"""
            SELECT
                ul.work_area_t,
                ul.name
            FROM rpl_user_list ul 
            WHERE ul.{designation_mapping[designation_id]} = %s AND ul.designation_id = %s;
        """
        print(work_area_t, designation_id, next_designation_id)
        with connection.cursor() as cursor:
            cursor.execute(query, [work_area_t, next_designation_id])
            rows = cursor.fetchall()

        if not rows:
            return Response(
                {"success": False, "message": "No data found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        next_user_list = [f"{row[0]} - {row[1]}" for row in rows]
        data = {
            "work_area_t": work_area_t,
            "current_designation_id": designation_id,
            "user_list": next_user_list,
            "next_designation_id": next_designation_id
        }

        return Response(
            {"success": True, "message": "Next user list fetched successfully.", "data": data},
            status=status.HTTP_200_OK
        )
        
