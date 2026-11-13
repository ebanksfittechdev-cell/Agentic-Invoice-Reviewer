# History Import JSON Schema

`POST /api/history/import` accepts a JSON file with this shape.
Use this same format when seeding data manually or importing from a spreadsheet export.

```json
{
  "vendors": [
    {
      "name": "Lakeshore Beverages",
      "account_no": "LSB-0042",
      "terms": "Net 30. Deposits: $0.10/bottle."
    }
  ],
  "agreed_costs": [
    {
      "vendor_name": "Lakeshore Beverages",
      "item_code": "LB-SPARKLING-12",
      "description": "Sparkling Water 12-pk",
      "unit": "case",
      "pack_size": 12,
      "cost": 8.40
    }
  ],
  "promotions": [
    {
      "vendor_name": "Lakeshore Beverages",
      "item_code": "LB-SPARKLING-12",
      "description": "Fall display allowance",
      "allowance_per_case": 1.20,
      "start_date": "2026-10-01",
      "end_date": "2026-11-30"
    }
  ],
  "vendor_notices": [
    {
      "vendor_name": "Summit Foods",
      "notice_date": "2026-11-08",
      "subject": "Price update: BBQ Chips",
      "body": "Effective immediately, BBQ Chips 1oz will be priced at $0.80/bag."
    }
  ]
}
```

## Rules

- `vendors` are upserted by `name` (case-insensitive). If a vendor with the same name already exists for this store, its `account_no` and `terms` are updated.
- `agreed_costs` are upserted by `vendor_name` + `item_code`. Existing costs are updated with the new `cost` and `updated_at`.
- `promotions` are upserted by `vendor_name` + `item_code` + `start_date`. Existing rows are updated.
- `vendor_notices` are upserted by `vendor_name` + `notice_date` + `subject`. Existing rows are updated.
- All four sections are optional — omit any you don't have.
- `vendor_name` must match a vendor in the `vendors` array (or one already in the DB for this store).

## Response

```json
{
  "vendors": 2,
  "agreed_costs": 8,
  "promotions": 1,
  "vendor_notices": 1
}
```
