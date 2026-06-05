# Hóa đơn sắp đến hạn trong 7 ngày

## Complexity: medium

## Tables Used: bills, customer_biller_accounts, billers

## Question (Vietnamese)
Tìm hóa đơn nào sắp đến hạn thanh toán trong 7 ngày tới của khách hàng CIF000001.

## Join Logic
- Cần `bills` để check due_date + status.
- Cần `customer_biller_accounts` để filter theo cif_no.
- Cần `billers` để lấy biller_name.
- **JOIN path**: same as 106
- Filter: `bills.status = 'UNPAID'` + `bills.due_date <= CURRENT_DATE + 7 days`

## SQL
```sql
SELECT
    bl.biller_name,
    bl.biller_type,
    cba.alias,
    b.bill_period,
    b.amount_due,
    b.due_date,
    b.due_date - CURRENT_DATE AS days_remaining
FROM bills b
JOIN customer_biller_accounts cba ON b.customer_bill_code = cba.customer_bill_code
JOIN billers bl ON b.biller_code = bl.biller_code
WHERE cba.cif_no = 'CIF000001'
  AND b.status = 'UNPAID'
  AND b.due_date <= CURRENT_DATE + INTERVAL '7 days'
ORDER BY b.due_date ASC;
```

## Expected Behavior
Returns unpaid bills due within 7 days, sorted by urgency. Includes days_remaining for user clarity.
