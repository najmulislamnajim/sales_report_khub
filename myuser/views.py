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
                "SELECT designation_id, work_area_t, name, group_name FROM rpl_user_list WHERE work_area_t = %s AND password = %s",
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
            "group_name": row[3]
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
        