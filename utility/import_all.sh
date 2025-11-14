#!/usr/bin/env bash
# import_all.sh
# Bulk import script for 20GB e-commerce dataset into PostgreSQL (partitioned)
# Usage:
#   bash import_all.sh /tmp/mcp_data

set -e

DATA_DIR="$1"
if [[ -z "$DATA_DIR" ]]; then
  echo "Usage: bash import_all.sh /path/to/data";
  exit 1;
fi

DB="mcp_demo"
USER="postgres"

echo "=== Importing into database: $DB ==="

# 1. Customers
echo "[1/8] Importing customers..."
psql -U $USER -d $DB -c "\COPY customers (id,name,email,country,created_at) FROM '$DATA_DIR/customers.csv' CSV";

# 2. Categories
echo "[2/8] Importing categories..."
psql -U $USER -d $DB -c "\COPY categories (id,name) FROM '$DATA_DIR/categories.csv' CSV";

# 3. Products
echo "[3/8] Importing products..."
psql -U $USER -d $DB -c "\COPY products (id,name,price,category_id) FROM '$DATA_DIR/products.csv' CSV";

# 4. Orders + Order Items (chunked)
echo "[4/8] Importing orders + order_items chunks..."
for f in $DATA_DIR/orders_*.csv; do
  ORDERS_FILE="$f"
  ITEMS_FILE="${f/orders_/order_items_}"
  echo "  -> Importing $ORDERS_FILE"
  psql -U $USER -d $DB -c "\COPY orders (id,customer_id,order_date,status,total_amount) FROM '$ORDERS_FILE' CSV";
  echo "  -> Importing $ITEMS_FILE"
  psql -U $USER -d $DB -c "\COPY order_items (id,order_id,order_date,product_id,quantity,price) FROM '$ITEMS_FILE' CSV";
done

# 5. Payments
echo "[5/8] Importing payments..."
psql -U $USER -d $DB -c "\COPY payments (order_id,paid_at,amount,method) FROM '$DATA_DIR/payments.csv' CSV";

# 6. Shipments
echo "[6/8] Importing shipments..."
psql -U $USER -d $DB -c "\COPY shipments (order_id,shipped_at,carrier,tracking_number) FROM '$DATA_DIR/shipments.csv' CSV";

# 7. Inventory
echo "[7/8] Importing inventory..."
psql -U $USER -d $DB -c "\COPY inventory (product_id,warehouse,quantity,updated_at) FROM '$DATA_DIR/inventory.csv' CSV";

# 8. Analyze
echo "[8/8] Running ANALYZE..."
psql -U $USER -d $DB -c "ANALYZE;";

echo "=== IMPORT COMPLETE ==="
