📦 PostgreSQL 20GB Data Load Guide

This guide explains how to generate a 20GB+ e-commerce dataset, create monthly partitions, bulk import data into PostgreSQL, and prepare the environment for AI + SQL workloads using your MCP Server.

⸻

✅ Overview

You will:
	1.	Create monthly partitions for orders and order_items
	2.	Generate 20GB synthetic e-commerce CSV data
	3.	Bulk-import data using optimized COPY operations
	4.	Run ANALYZE for performance
	5.	Verify tables, partitions, and row counts

⸻

🧩 Step 1 — Create Monthly Partitions

Run the Python script:

python3 create_partitions.py

You should see output like:

Created partitions: orders_2023_01, order_items_2023_01
Created partitions: orders_2023_02, order_items_2023_02
...
Created partitions: orders_2025_12, order_items_2025_12
All partitions created successfully.

This ensures your partitioned tables are ready to accept data.

⸻

🧩 Step 2 — Generate 20GB CSV Data

The generator script is located at:

tools/generate_20gb.py

Install dependencies:

pip3 install faker python-dateutil

Generate dataset:

python3 tools/generate_20gb.py --out /tmp/mcp_data \
  --customers 2000000 --categories 1000 --products 100000 \
  --orders 10000000 --chunk 100000

This creates:

/tmp/mcp_data/customers.csv
/tmp/mcp_data/categories.csv
/tmp/mcp_data/products.csv
/tmp/mcp_data/orders_1_100000.csv
/tmp/mcp_data/order_items_1_100000.csv
...
/tmp/mcp_data/payments.csv
/tmp/mcp_data/shipments.csv
/tmp/mcp_data/inventory.csv


⸻

🧩 Step 3 — Bulk Import Into PostgreSQL

Use the import script included in your project:

import_all.sh

Make executable:

chmod +x import_all.sh

Run import:

bash import_all.sh /tmp/mcp_data

What the script does:
	•	Imports customers, categories, products
	•	Imports orders + order_items chunk-by-chunk
	•	Imports payments, shipments, inventory
	•	Runs ANALYZE on the database

⸻

🧩 Step 4 — Verify Data Load

Row counts

SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM order_items;
SELECT COUNT(*) FROM payments;
SELECT COUNT(*) FROM shipments;

Check partitions

SELECT inhrelid::regclass AS partition
FROM pg_inherits
WHERE inhparent = 'orders'::regclass;

Random samples

SELECT * FROM orders LIMIT 10;
SELECT * FROM order_items LIMIT 10;


⸻

🚀 Query Performance Examples

Try these analytics queries:

Top Customers by Spending

SELECT c.name, SUM(o.total_amount) AS total_spent
FROM customers c
JOIN orders o ON c.id = o.customer_id
GROUP BY c.id
ORDER BY total_spent DESC
LIMIT 10;

Monthly Revenue Trend

SELECT date_trunc('month', order_date) AS month,
       SUM(total_amount)
FROM orders
GROUP BY 1
ORDER BY 1;

Shipment Carrier Performance

SELECT carrier, COUNT(*)
FROM shipments
GROUP BY carrier
ORDER BY COUNT(*) DESC;


⸻

🛠 Troubleshooting

⚠ COPY: relation does not exist

You likely missed schema or partitions.
Run:

\i schema_20gb.sql
python3 create_partitions.py

⚠ COPY: invalid input syntax for type numeric

Check for manual edits to CSV files.

⚠ Out of disk space

20GB dataset may expand to 40–60GB with indexes.
Ensure you have enough free space:
	•	/tmp/mcp_data
	•	PostgreSQL data directory

⸻

🎉 Everything Ready!

You now have:
	•	A 20GB partitioned PostgreSQL e-commerce database
	•	Realistic multi-table dataset for analytics & AI
	•	MCP Server ready for advanced natural-language-to-SQL workloads

If you want, I can also generate:
	•	Benchmark scripts (pgbench custom)
	•	SQL workload simulator
	•	Grafana dashboards for DB monitoring
	•	AI-powered SQL QA datasets

Just ask! 🚀