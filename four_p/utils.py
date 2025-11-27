from django.db import connections
from collections import defaultdict

def fmt(d):
    return d.strftime("%d %B %Y").lstrip("0") if d else ""

def run_query(alias, query, params, output, key):
    with connections[alias].cursor() as cursor:
        cursor.execute("SET SESSION max_statement_time = 00") # 10 minutes
        cursor.execute(query, params)
        cols = [c[0] for c in cursor.description]
        output[key] = [dict(zip(cols, row)) for row in cursor.fetchall()]
        
def formatted_division(a,b):
    try:
        return a/b
    except:
        return 0.00

def process_current_four_p_data(rows, brand_list):
    grouped_rows = defaultdict(list)
    grouped_data = defaultdict(list)
    _total, _others, _radiant, _brand = len(rows), 0, 0, 0
    
    for row in rows:
        grouped_rows[row['phy_id']].append(row)
    
    for phy_id, results in grouped_rows.items():
        total, others, radiant, brand = len(results), 0, 0, 0
        for result in results:
            if result['vc2_1'].startswith('RDT'):
                _radiant += 1
                radiant += 1
                if brand_list and result['product_brand'] in brand_list:
                    _brand += 1
                    brand += 1
            else:
                _others += 1
                others += 1
        
        grouped_data[phy_id] = {
            'total': total,
            'others': others,
            'radiant': radiant,
            'brand': brand,
            'radiant_share' : round(formatted_division(radiant, total) * 100, 2),
            'brand_share' : round(formatted_division(brand, total) * 100, 2),
            'four_p_id' : phy_id,
            'rpl_dr_id' : results[0]['dr_child_id'],
            'dr_name' : results[0]['dr_name']
        }
        
    summary_data = {
        'total': _total,
        'others': _others,
        'radiant': _radiant,
        'brand': _brand,
        'radiant_share' : round(formatted_division(_radiant, _total) * 100, 2),
        'brand_share' : round(formatted_division(_brand, _total) * 100, 2)
    }
    return list(grouped_data.values()), summary_data


def process_four_p_data(rows, brand_list):
    _total, _others, _radiant, _brand = len(rows), 0, 0, 0
    
    for row in rows:
        if row['vc2_1'].startswith('RDT'):
            _radiant += 1
            if brand_list and row['product_brand'] in brand_list:
                _brand += 1
        else:
            _others += 1
            
    ytd_data = {
        'total': _total,
        'others': _others,
        'radiant': _radiant,
        'brand': _brand,
        'radiant_share' : round(formatted_division(_radiant, _total) * 100, 2),
        'brand_share' : round(formatted_division(_brand, _total) * 100, 2)
    }
    return ytd_data

def process_four_p_data_for_graph(rows, user_data, radiant):
    user_group = defaultdict(dict)
    graph_data = []
    
    for d in user_data:
        user_group[d['next_designation']] = {
            'key' : d['work_areas'],
            'data' : [],
            'address' : d['address']
        }
        
    for row in rows:
        for key in user_group.keys():
            if row['vc2_1'].startswith('RDT') and row['work_area_t'] and row['work_area_t'] in user_group[key]['key']:
                user_group[key]['data'].append(row)
                break
            
    for key in user_group.keys():
        total = len(user_group[key]['data'])
        
        graph_data.append({
            'key' : key,
            'total' : total,
            'address' : user_group[key]['address'],
            'share' : round(formatted_division(total, radiant) * 100, 2)
        })
    
    graph_data.sort(key=lambda x: x['share'], reverse=True)
    graph_data = graph_data[:5]
    return graph_data