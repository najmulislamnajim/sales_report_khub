from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection
from rest_framework import status
from datetime import date
from .constant import *

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
        
        if group_name is None:
            return Response(
                {"success": False, "message": "Missing group_name in query parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if group_name.lower() == 'a':
            return Response(
                {"success": True, "message": "Brand names fetched successfully.", "data": GROUP_A_BRANDS},
                status=status.HTTP_200_OK
            )
        if group_name.lower() == 'b':
            return Response(
                {"success": True, "message": "Brand names fetched successfully.", "data": GROUP_B_BRANDS},
                status=status.HTTP_200_OK
            )
        if group_name.lower() == 'c':
            return Response(
                {"success": True, "message": "Brand names fetched successfully.", "data": GROUP_C_BRANDS},
                status=status.HTTP_200_OK
            )
        # ---------------------------
        # Fetch Brand Names
        # ---------------------------
        brand_query = f"""
            SELECT DISTINCT brand_name, brand_description 
            FROM rpl_material 
            WHERE team1=%s;
        """
        with connection.cursor() as cursor:
            cursor.execute(brand_query, [group_name])
            rows = [row[0] for row in cursor.fetchall()]
            
        brands = [] 
        for row in rows:
            brands.append({
                "brand": row[0],
                "brand_name": row[1]})
        return Response(
            {"success": True, "message": "Brand names fetched successfully.", "data": brands},
            status=status.HTTP_200_OK
        )
        
class GetNextUserList(APIView):
    def get(self, request):
        work_area_t = request.query_params.get('work_area_t')
        designation_id = int(request.query_params.get('designation_id'))
        user_type = request.query_params.get('type')
        designation_mapping = {
            1: "work_area_t",
            2: "rm_code",
            3: "zm_code",
            4: "sm_code",
            5: "gm_code"
        }
        user_type_mapping = {
            "mio":1,
            "rm":2,
            "zm":3,
            "sm":4,
            "gm":5
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
            cursor.execute(query, [work_area_t, user_type_mapping[user_type]])
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
            "next_designation_id": next_designation_id,
            "sm": "",
            "zm": "",
            "rm": ""
        }
        query = f"""
        SELECT work_area_t, name, designation_id
        FROM rpl_user_list
        WHERE work_area_t IN (
            SELECT rm_code FROM rpl_user_list WHERE work_area_t=%s
            UNION
            SELECT zm_code FROM rpl_user_list WHERE work_area_t=%s
            UNION
            SELECT sm_code FROM rpl_user_list WHERE work_area_t=%s
        );
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [work_area_t, work_area_t, work_area_t])
            rows = cursor.fetchall()
        for row in rows:
            if row[2] == 4:
                data["sm"] = f"{row[0]} - {row[1]}"
            elif row[2] == 3:
                data["zm"] = f"{row[0]} - {row[1]}"
            elif row[2] == 2:
                data["rm"] = f"{row[0]} - {row[1]}"

        return Response(
            {"success": True, "message": "Next user list fetched successfully.", "data": data},
            status=status.HTTP_200_OK
        )
        
class GetUserInfo(APIView):
    def get(self, request, work_area_t):
        query = f"""
            SELECT
                work_area_t,rm_code, rm_address, zm_code, zm_address, sm_code, sm_address, gm_code, gm_address, `name`, address, mobile_number, designation, group_name
            FROM rpl_user_list 
            WHERE work_area_t = %s;
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [work_area_t])
            row = cursor.fetchone()
            
        if not row:
            return Response(
                {"success": False, "message": "Invalid work_area_t"},
                status=status.HTTP_404_NOT_FOUND
            )
        data = {
            "work_area_t": row[0],
            "address": row[10],
            "name": row[9],
            "designation": row[12],
            "group_name": row[13],
            "mobile_number": row[11],
            "rm_code": row[1],
            "rm_address": row[2],
            "zm_code": row[3],
            "zm_address": row[4],
            "sm_code": row[5],
            "sm_address": row[6],
            "gm_code": row[7],
            "gm_address": row[8]
        }
        return Response(
            {"success": True, "message": "User info fetched successfully.", "data": data},
            status=status.HTTP_200_OK
        )
        
        
# class GetNextUserList(APIView):
#     def get(self, request):
#         work_area_t = request.query_params.get('work_area_t')
#         designation_id = int(request.query_params.get('designation_id'))
#         user_type = request.query_params.get('type')
        
#         if not work_area_t or not designation_id:
#             return Response(
#                 {"success": False, "message": "Missing work_area_t or designation_id in query parameters"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         designation_mapping = {
#             1: "work_area_t",
#             2: "rm_code",
#             3: "zm_code",
#             4: "sm_code",
#             5: "gm_code"
#         }
        
#         user_type_mapping = {
#             "mio":1,
#             "rm":2,
#             "zm":3,
#             "sm":4,
#             "gm":5
#         }
        
#         if user_type:
#             if user_type not in user_type_mapping:
#                 return Response(
#                     {"success": False, "message": "Invalid user type"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             if user_type_mapping[user_type] > designation_id:
#                 return Response(
#                     {"success": False, "message": "You can't fetch users of higher or equal designation"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
                
#             query = f"""
#                 SELECT work_area_t, name 
#                 FROM rpl_user_list 
#                 WHERE {designation_mapping[designation_id]} = %s AND designation_id = %s;
#             """
#             with connection.cursor() as cursor:
#                 cursor.execute(query, [work_area_t, user_type_mapping[user_type]])
#                 rows = cursor.fetchall()
                
#             data = []
#             for row in rows:
#                 data.append(f"{row[0]} - {row[1]}")
#             return Response(
#                 {"success": True, "message": "Users fetched successfully.", "data": data},
#                 status=status.HTTP_200_OK
#             )
                 
#         else:
#             query = f"""
#                 SELECT work_area_t, name, designation_id
#                 FROM rpl_user_list
#                 WHERE work_area_t IN (
#                     SELECT rm_code FROM rpl_user_list WHERE work_area_t= %s
#                     UNION
#                     SELECT zm_code FROM rpl_user_list WHERE work_area_t= %s
#                     UNION
#                     SELECT sm_code FROM rpl_user_list WHERE work_area_t= %s
#                 );
#             """
#             with connection.cursor() as cursor:
#                 cursor.execute(query, [work_area_t, work_area_t, work_area_t])
#                 rows = cursor.fetchall()
#             data = {
#                 "sm": "",
#                 "zm": "",
#                 "rm": ""
#             }
#             for row in rows:
#                 if row[2] == 4:
#                    data["sm"] = f"{row[0]} - {row[1]}"
#                 elif row[2] == 3:
#                     data["zm"] = f"{row[0]} - {row[1]}"
#                 elif row[2] == 2:
#                     data["rm"] = f"{row[0]} - {row[1]}"
#             return Response(
#                 {"success": True, "message": "User selected successfully.", "data": data},
#                 status=status.HTTP_200_OK
#             )
        
        
        
