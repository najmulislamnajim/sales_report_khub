def get_4p_query(designation):
    return f"""
            SELECT
                fp.work_area_t, fp.`year`, fp.`month`, fp.total, fp.radiant 
            FROM
                rpl_4p_summary fp 
            WHERE
                fp.work_area_t IN ( SELECT work_area_t FROM rpl_user_list WHERE {designation} = %s AND designation_id = 1 ) 
                AND fp.`year` = YEAR ( CURRENT_DATE )
            GROUP BY fp.`month`
            ;
        """