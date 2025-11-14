#!/usr/bin/env python3
"""
generate_20gb.py - FINAL VERSION

Matches fixed schema_20gb.sql (no order_date required for payments & shipments)
"""

import os
import csv
import random
import argparse
from faker import Faker
from datetime import datetime
from dateutil.relativedelta import relativedelta

fake = Faker()
random.seed(42)

DEFAULT_OUT = "/tmp/mcp_data"

STATUS_CHOICES = ["completed", "pending", "cancelled", "returned"]
STATUS_WEIGHTS = [0.7, 0.15, 0.1, 0.05]


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def write_customers(path, n_customers):
    print(f"Generating {n_customers} customers -> {path}")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for cid in range(1, n_customers + 1):
            name = fake.name()
            email = fake.unique.email()
            country = fake.country()
            created_at = fake.date_time_between(start_date='-5y', end_date='now').strftime('%Y-%m-%d %H:%M:%S')
            w.writerow([cid, name, email, country, created_at])


def write_categories(path, n_categories):
    print(f"Generating {n_categories} categories -> {path}")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for i in range(1, n_categories + 1):
            w.writerow([i, f"Category {i}"])


def write_products(path, n_products, n_categories):
    print(f"Generating {n_products} products -> {path}")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for pid in range(1, n_products + 1):
            name = " ".join(fake.words(nb=3)).title()
            price = round(random.uniform(5, 2000), 2)
            cat = random.randint(1, n_categories)
            w.writerow([pid, name, price, cat])


def gen_order_chunk(out_dir, start_id, count, n_customers, product_count, order_date_start, order_date_end, global_item_counter):
    orders_fname = os.path.join(out_dir, f"orders_{start_id}_{start_id+count-1}.csv")
    items_fname = os.path.join(out_dir, f"order_items_{start_id}_{start_id+count-1}.csv")

    with open(orders_fname, "w", newline="") as of, open(items_fname, "w", newline="") as it:
        ow = csv.writer(of)
        iw = csv.writer(it)

        for i in range(count):
            oid = start_id + i
            customer_id = random.randint(1, n_customers)
            order_dt = fake.date_time_between(start_date=order_date_start, end_date=order_date_end).strftime('%Y-%m-%d %H:%M:%S')
            status = random.choices(STATUS_CHOICES, weights=STATUS_WEIGHTS, k=1)[0]
            total_amount = 0.0
            ow.writerow([oid, customer_id, order_dt, status, f"{total_amount:.2f}"])

            num_items = random.randint(1, 5)
            for _ in range(num_items):
                global_item_counter += 1
                product_id = random.randint(1, product_count)
                quantity = random.randint(1, 4)
                price = round(random.uniform(5, 500), 2)
                iw.writerow([global_item_counter, oid, order_dt, product_id, quantity, f"{price:.2f}"])

    print(f"Wrote chunk orders: {orders_fname} and items: {items_fname} (items so far: {global_item_counter})")
    return global_item_counter


def write_payments(path, n_orders):
    print(f"Generating payments -> {path}")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for oid in range(1, n_orders + 1):
            amount = round(random.uniform(5, 2000), 2)
            method = random.choice(["Credit Card", "UPI", "PayPal", "NetBanking"])
            paid_at = fake.date_time_between(start_date='-2y', end_date='now').strftime('%Y-%m-%d %H:%M:%S')
            w.writerow([oid, paid_at, amount, method])


def write_shipments(path, n_orders):
    print(f"Generating shipments -> {path}")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for oid in range(1, n_orders + 1):
            if random.random() < 0.85:
                shipped_at = fake.date_time_between(start_date='-2y', end_date='now').strftime('%Y-%m-%d %H:%M:%S')
                carrier = random.choice(['DHL','FedEx','BlueDart','Delhivery','Ecom'])
                tracking = fake.uuid4()
                w.writerow([oid, shipped_at, carrier, tracking])


def write_inventory(path, n_products):
    print(f"Generating inventory -> {path}")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for pid in range(1, n_products + 1):
            warehouse = f"WH-{random.randint(1,200)}"
            qty = random.randint(0, 1000)
            updated_at = fake.date_time_between(start_date='-2y', end_date='now').strftime('%Y-%m-%d %H:%M:%S')
            w.writerow([pid, warehouse, qty, updated_at])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--customers", type=int, default=2000000)
    ap.add_argument("--categories", type=int, default=1000)
    ap.add_argument("--products", type=int, default=100000)
    ap.add_argument("--orders", type=int, default=10000000)
    ap.add_argument("--chunk", type=int, default=100000)
    args = ap.parse_args()

    out = args.out
    ensure_dir(out)

    print("Output directory:", out)
    print("Counts:", args.customers, args.products, args.orders)

    write_customers(os.path.join(out, "customers.csv"), args.customers)
    write_categories(os.path.join(out, "categories.csv"), args.categories)
    write_products(os.path.join(out, "products.csv"), args.products, args.categories)

    total_orders = args.orders
    chunk = args.chunk
    start = 1
    global_item_counter = 0

    order_date_end = datetime.now()
    order_date_start = order_date_end - relativedelta(years=2)

    while start <= total_orders:
        cnt = min(chunk, total_orders - start + 1)
        global_item_counter = gen_order_chunk(out, start, cnt, args.customers, args.products, order_date_start, order_date_end, global_item_counter)
        start += cnt

    write_payments(os.path.join(out, "payments.csv"), args.orders)
    write_shipments(os.path.join(out, "shipments.csv"), args.orders)
    write_inventory(os.path.join(out, "inventory.csv"), args.products)

    print("Data generation complete:", out)


if __name__ == '__main__':
    main()