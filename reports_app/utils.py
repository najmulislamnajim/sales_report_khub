from datetime import datetime, timedelta

def get_period_list(start_date, end_date):
    periods = []
    current = start_date.replace(day=1)

    while current <= end_date:
        periods.append(current.strftime("%Y%m"))
        # move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)
    return periods

