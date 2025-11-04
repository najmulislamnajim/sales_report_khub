from datetime import date

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
        
        
def get_budget_data_query(designation, brand):
    return f"""
        SELECT
            rst.period, 
            SUM(rst.budget) AS budget_quantity,
            SUM(rst.budget_amount) AS budget_amount,
            SUM(rst.sales) AS sales_quantity,
            SUM(rst.sales_amount) AS sales_amount
        FROM rpl_sales_tty rst 
        WHERE rst.work_area IN (
                SELECT work_area_t 
                FROM rpl_user_list 
                WHERE {designation} = %s AND designation_id=1
            )
            AND rst.period IN %s 
            {brand}
        GROUP BY rst.period
        ORDER BY rst.period ASC;
    """