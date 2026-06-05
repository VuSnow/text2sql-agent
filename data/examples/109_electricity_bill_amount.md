# Tiền điện tháng này bao nhiêu

## Complexity: simple

## Tables Used: bills, customer_biller_accounts, billers

## Question (Vietnamese)
Hóa đơn tiền điện tháng này của tôi (CIF000001) là bao nhiêu?

## Join Logic
- Cần `bills` để lấy amount_due cho kỳ hiện tại.
- Cần `customer_biller_accounts` để filter theo cif_no.
- Cần `billers` để filter biller_type = 'ELECTRICITY'.
- **JOIN path**: `bills.customer_bill_code = customer_biller_accounts.customer_bill_code` + `bills.biller_code = billers.biller_code`
- Filter: `bl.biller_type = 'ELECTRICITY'` + current bill_period

## SQL
```sql
SELECT
    bl.biller_name,
    cba.alias,
    b.bill_period,
    b.amount_due,
    b.due_date,
    b.status
FROM bills b
JOIN customer_biller_accounts cba ON b.customer_bill_code = cba.customer_bill_code
JOIN billers bl ON b.biller_code = bl.biller_code
WHERE cba.cif_no = 'CIF000001'
  AND bl.biller_type = 'ELECTRICITY'
  AND b.bill_period = TO_CHAR(CURRENT_DATE, 'YYYY-MM');
```

## Expected Behavior
Returns electricity bills for the current month. If user has multiple electricity accounts, returns all of them with alias for disambiguation.
