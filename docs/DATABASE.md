# Ngon-Ngon — Database Rules

## Tenant-scoped tables (có store_id qua TenantMixin)
categories, products, toppings, orders, order_items, customers,
time_deals, cross_sell_items, admin_users, feature_flags, events,
reviews, push_subscriptions, loyalty_rewards, referrals

## Platform tables (KHÔNG có store_id)
stores, product_sizes, product_toppings, alembic_version

## RLS Policies (viết sẵn, bật giai đoạn 2)
```sql
-- Pattern cho MỌI bảng tenant-scoped:
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    FOR ALL
    USING (store_id = current_setting('app.current_tenant', true)::int)
    WITH CHECK (store_id = current_setting('app.current_tenant', true)::int);
```

## Naming conventions
- Table: plural snake_case (products, order_items)
- Column: singular snake_case (store_id, created_at)
- FK column: {table_singular}_id (product_id, store_id)
- Index: ix_{table}_{columns} (ix_orders_store_status)

## Migration rules
- Mỗi migration làm 1 việc. Phải có upgrade + downgrade.
- RLS policies trong migration riêng, không trộn với schema.
