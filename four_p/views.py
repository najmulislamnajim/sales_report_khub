from rest_framework.views import APIView
from collections import defaultdict
from rest_framework.response import Response
from django.db import connection
from rest_framework import status
from datetime import date, datetime
from .sqls import get_fourP_details_query
# Create your views here.
def fmt(d):
    return d.strftime("%d %B %Y").lstrip("0") if d else ""
class GetFourPDetails(APIView):
    def get(self, request):
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
                "radiant_share": round((radiant / len(results) if len(results) > 0 else 0) * 100 , 2),
                "brand_share": round((brand / len(results) if len(results) > 0 else 0) * 100 , 2),
                "four_p_id" : phy_id,
                "rpl_dr_id" : results[0]['dr_child_id'],
                "dr_name" : results[0]['dr_name'],
            }
        
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
                "radiant_share": round(_radiant / len(rows) if len(rows) > 0 else 0 , 2) * 100,
                "brand_share": round(_brand / len(rows) if len(rows) > 0 else 0 , 2) * 100
            },
            "selected_brands": brand_name,
            "start_date": fmt(start_date),
            "end_date": fmt(end_date)
        }

        return Response({"success": True, "data": data}, status=status.HTTP_200_OK)
    