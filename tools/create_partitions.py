# create_partitions.py
import psycopg2
from datetime import datetime
from dateutil.relativedelta import relativedelta

DB_CONN = "dbname=mcp_demo user=postgres"
start = datetime(2023,1,1)
end = datetime(2025,12,1)

conn = psycopg2.connect(DB_CONN)
cur = conn.cursor()

current = start
while current <= end:
    next_month = current + relativedelta(months=1)
    part_orders = f"orders_{current.year}_{current.month:02d}"
    part_items = f"order_items_{current.year}_{current.month:02d}"

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {part_orders}
        PARTITION OF orders
        FOR VALUES FROM ('{current.strftime('%Y-%m-01')}')
                     TO ('{next_month.strftime('%Y-%m-01')}');
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {part_items}
        PARTITION OF order_items
        FOR VALUES FROM ('{current.strftime('%Y-%m-01')}')
                     TO ('{next_month.strftime('%Y-%m-01')}');
    """)

    print(f"Created partitions: {part_orders}, {part_items}")
    current = next_month

conn.commit()
cur.close()
conn.close()
print("All partitions created successfully.")