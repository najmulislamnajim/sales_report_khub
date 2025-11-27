from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import date, datetime, timedelta
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from . import utils
from .sqls import get_fourP_details_query, get_next_group_query
from .utils import formatted_division, fmt
# Create your views here.
class GetFourPDetails(APIView):
    def get(self, request):
        try:
            # ------------------------------
            # Get Query Parameters
            # ------------------------------
            work_area_t = request.query_params.get('work_area_t')
            designation_id = int(request.query_params.get('designation_id'))
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            brands = request.query_params.get('brands')
            brands = brands.split(',') if brands else ""
            brand_name = brands or []
            # ----------------------------
            # Validate Query Parameters
            # ----------------------------
            if not work_area_t or not designation_id:
                return Response({"success": False, "message": "Missing work_area_t or designation_id in query parameters"}, status=status.HTTP_400_BAD_REQUEST)
            
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
                1: ("work_area_t", "work_area", "territory"),
                2: ("rm_code", "region_code", "region"),
                3: ("zm_code", "zone_code", "zone"),
                4: ("sm_code", "sm_area_code", "sm_area"),
                5: ("gm_code", "gm_area_code", "gm_area")
            }
            designation, area, _ = designation_mapping.get(designation_id, (None, None))
            if not designation:
                return Response(
                    {"success": False, "message": "Invalid designation_id"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # ------------------------------
            # Query and get data
            # ------------------------------
            query = get_fourP_details_query(designation)

            with connection.cursor() as cursor:
                cursor.execute("SET SESSION max_statement_time = 00") # 10 minutes
                cursor.execute(query, [work_area_t, start_date, end_date])
                columns = [col[0] for col in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
            grouped_results = defaultdict(list)
            for row in rows:
                grouped_results[row['phy_id']].append(row)
            
            # ------------------------------
            # graph data
            # ------------------------------
            next_designation_id = max(designation_id - 1, 1)
            next_designation, _ , graph_title = designation_mapping.get(next_designation_id, (None, None, None))
            
            graph_query = get_next_group_query(designation, next_designation)
            with connection.cursor() as cursor:
                cursor.execute(graph_query, [work_area_t])
                graph_columns = [col[0] for col in cursor.description]
                graph_rows = [dict(zip(graph_columns, row)) for row in cursor.fetchall()]
            # ------------------------------
            # Calculation
            # ------------------------------
            grouped_data = defaultdict(dict)
            _others, _radiant, _brand = 0, 0, 0
            for phy_id, results in grouped_results.items():
                others, radiant, brand = 0, 0, 0
                for result in results:
                    if result['vc2_1'].startswith('RDT'):
                        radiant += 1
                        _radiant += 1
                        if brand_name and result['product_brand'] in brand_name:
                            brand += 1
                            _brand += 1
                    else:
                        others += 1
                        _others += 1
                grouped_data[phy_id] = {
                    "total" : len(results),
                    "others": others,
                    "radiant": radiant,
                    "brand": brand,
                    "radiant_share": round(formatted_division(radiant, len(results)) * 100 , 2),
                    "brand_share": round(formatted_division(brand, len(results)) * 100 , 2),
                    "four_p_id" : phy_id,
                    "rpl_dr_id" : results[0]['dr_child_id'],
                    "dr_name" : results[0]['dr_name'],
                }
            
            graph_data = defaultdict(dict)
            for row in graph_rows:
                graph_data[row['next_designation']] = {
                    "key": row['work_areas'],
                    "data" : [],
                    "address" : row['address']
                }
            for row in rows:
                for key in graph_data.keys():
                    if row['vc2_1'].startswith('RDT') and row['work_area_t'] and row['work_area_t'] in graph_data[key]['key']:
                        graph_data[key]['data'].append(row['phy_id'])
                        break
            
            graph_res = []
            for key in graph_data.keys():
                total = len(graph_data[key]['data'])
                graph_res.append({
                    "key": key,
                    "total" : total,
                    "address" : graph_data[key]['address'],
                    "share": round(formatted_division(total , _radiant) * 100 , 2)
                }
                )
            
            graph_res.sort(key=lambda x: x['share'], reverse=True)
            graph_res = graph_res[:5]
            # ------------------------------
            # Response
            # ------------------------------
            grouped_data = list(grouped_data.values())
            
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('per_page', 10))
            # Validate pagination params
            if page <= 0 or page_size <= 0:
                return Response({
                    "success": False,
                    "message": "Invalid 'page' or 'per_page'. Must be positive integers."
                }, status=status.HTTP_400_BAD_REQUEST)
                
            sort_by = request.query_params.get('sort')
            sort_order = request.query_params.get('dir')
            if sort_by == 'radiant':
                grouped_data.sort(key=lambda x: x['radiant'], reverse=True if sort_order == 'desc' else False)
            if sort_by == 'brand':
                grouped_data.sort(key=lambda x: x['brand'], reverse=True if sort_order == 'desc' else False)

            total_items = len(grouped_data)
            total_pages = (total_items + page_size - 1) // page_size

            start_index = (page - 1) * page_size
            end_index = start_index + page_size

            paginated_data = grouped_data[start_index:end_index]

            data = {
                "page": page,
                "per_page": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "data": paginated_data,
                "summary": {
                    "total": len(rows),
                    "others": _others,
                    "radiant": _radiant,
                    "brand": _brand,
                    "radiant_share": round(formatted_division(_radiant, len(rows)) * 100 , 2),
                    "brand_share": round(formatted_division(_brand, len(rows)) * 100 , 2)
                },
                "selected_brands": brand_name,
                "start_date": fmt(start_date),
                "end_date": fmt(end_date),
                "graph_data": graph_res,
                "graph_title" : graph_title
            }

            return Response({"success": True, "data": data}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class GetFourPData(APIView):
    def get(self, request):
        try:
            # ------------------------------
            # Get Query Parameters
            # ------------------------------
            work_area_t = request.query_params.get('work_area_t')
            designation_id = int(request.query_params.get('designation_id'))
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            brands = request.query_params.get('brands')
            brands = brands.split(',') if brands else ""
            brand_name = brands or []
            
            # ----------------------------
            # Validate Query Parameters
            # ----------------------------
            if not work_area_t or not designation_id:
                return Response({"success": False, "message": "Missing work_area_t or designation_id in query parameters"}, status=status.HTTP_400_BAD_REQUEST)
            
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
                
            date1 = date(start_date.year,1,1)
            date2 = datetime.today().replace(day=1) - timedelta(days=1)
            
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
                1: ("work_area_t", "work_area", "territory"),
                2: ("rm_code", "region_code", "region"),
                3: ("zm_code", "zone_code", "zone"),
                4: ("sm_code", "sm_area_code", "sm_area"),
                5: ("gm_code", "gm_area_code", "gm_area")
            }
            designation, area, _ = designation_mapping.get(designation_id, (None, None, None))
            if not designation:
                return Response(
                    {"success": False, "message": "Invalid designation_id"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            next_designation_id = max(designation_id - 1, 1)
            next_designation, _ , graph_title = designation_mapping.get(next_designation_id, (None, None, None))
            
            # ------------------------------
            # Queries
            # ------------------------------
            c_query = get_fourP_details_query(designation)
            c_params = [work_area_t, start_date, end_date]
            g_query = get_next_group_query(designation, next_designation)
            g_params = [work_area_t]
            f_query = get_fourP_details_query(designation)
            f_params = [work_area_t, date1, date2]
            
            # ------------------------------
            # Get db results
            # ------------------------------
            output = {}
            t1 = Thread(
                target= utils.run_query,
                args=("default", c_query, c_params, output, 'current_data')
            )
            t2 = Thread(
                target= utils.run_query,
                args=("default", g_query, g_params, output, 'group_data')
            )
            t3 = Thread(
                target= utils.run_query,
                args=("default", f_query, f_params, output, 'full_data')
            )
            t1.start()
            t2.start()
            t3.start()
            t1.join()
            t2.join()
            t3.join()
            
            current_rows = output['current_data']
            group_rows = output['group_data']
            full_rows = output['full_data']
            
            # ------------------------------
            # process row data
            # ------------------------------
            with ThreadPoolExecutor() as executor:
                future1 = executor.submit(utils.process_current_four_p_data, current_rows, brand_name)
                future2 = executor.submit(utils.process_four_p_data, full_rows, brand_name)

                table_data, summary_data = future1.result()
                ytd_data = future2.result()

            graph_data = utils.process_four_p_data_for_graph(current_rows,group_rows, summary_data['radiant'])
            
            # ------------------------------
            # Sorting
            # ------------------------------
            sort_by = request.query_params.get('sort')
            sort_order = request.query_params.get('dir')
            if sort_by == 'radiant':
                table_data.sort(key=lambda x: x['radiant'], reverse=True if sort_order == 'desc' else False)
            elif sort_by == 'brand':
                table_data.sort(key=lambda x: x['brand'], reverse=True if sort_order == 'desc' else False)
            
            # ------------------------------
            # pagination setup
            # ------------------------------
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('per_page', 10))
            if page <= 0 or page_size <= 0:
                return Response({
                    "success": False,
                    "message": "Invalid 'page' or 'per_page'. Must be positive integers."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ------------------------------
            # Paginate data
            # ------------------------------
            total_items = len(table_data)
            total_pages = (total_items + page_size - 1) // page_size
            if page > total_pages and total_pages != 0:
                page = total_pages
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_table_data = table_data[start_index:end_index]
            
            data = {
                "page": page,
                "per_page": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "data": paginated_table_data,
                "summary" : summary_data,
                "ytd" : ytd_data,
                "graph_data" : graph_data,
                "graph_title" : graph_title,
                "selected_brands" : brand_name,
                "start_date" : fmt(start_date),
                "end_date" : fmt(end_date),
                "sort_by" : sort_by,
                "sort_order" : sort_order
            }
            
            return Response({"success": True, "data": data}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)