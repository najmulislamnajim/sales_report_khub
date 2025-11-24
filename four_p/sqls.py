def get_fourP_details_query(designation):
    return f"""
        SELECT 
                p.round,
                p.pdate,
                p.phy_id,
                p.ing,
                p.vc2_1,
                p.name1,
                p.business_unit,
                p.product_brand,
                di.dr_child_id,
                di.dr_master_id,
                di.work_area_t,
                di.team,
                di.dr_name
        FROM rpl_prescription p 
        LEFT JOIN rpl_doctor_info di ON p.phy_id = di.pppp_id AND di.work_area_t IN (
                    SELECT work_area_t FROM rpl_user_list WHERE {designation} = %s AND designation_id=1
                )
        WHERE DATE(p.pdate) >= %s AND DATE(p.pdate) <= %s;
    """
    
    
def get_next_group_query(designation, next_designation):
    address = next_designation.split("_")[0]
    address = address + "_address"
    return f"""
        SELECT 
            {next_designation} as next_designation,
            {address} as address,
            GROUP_CONCAT(DISTINCT work_area_t) AS work_areas
        FROM rpl_user_list
        WHERE {designation} = %s AND designation_id = 1
        GROUP BY {next_designation};
    """