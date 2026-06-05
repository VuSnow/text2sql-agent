# Tổng tiền hóa đơn đã thanh toán theo loại dịch vụ

## Complexity: medium

## Tables Used: bills, customer_biller_accounts, billers

## Question (Vietnamese)
Tổng tiền hóa đơn đã thanh toán theo từng loại dịch vụ (điện, nước, internet, điện thoại) của khách hàng CIF000002 trong 3 tháng qua.

## Join Logic
- Cần `bills` cho amount_due + paid_at + status.
- Cần `customer_biller_accounts` để filter theo cif_no.
- Cần `billers` để GROUP BY biller_type.
- **JOIN path**: `bills.customer_bill_code = customer_biller_accounts.customer_bill_code` + `bills.biller_code = billers.biller_code`
- Filter: `bills.status = 'PAID'` + `bills.paid_at >= 3 months ago`

## SQL
```sql
SELECT
    bl.biller_type,
    COUNT(*) AS bill_count,
    SUM(b.amount_due) AS total_paid
FROM bills b
JOIN customer_biller_accounts cba ON b.customer_bill_code = cba.customer_bill_code
JOIN billers bl ON b.biller_code = bl.biller_code
WHERE cba.cif_no = 'CIF000002'
  AND b.status = 'PAID'
  AND b.paid_at >= CURRENT_DATE - INTERVAL '3 months'
GROUP BY bl.biller_type
ORDER BY total_paid DESC;
```

## Expected Behavior
Returns aggregated payment amounts grouped by service type. Useful for spending analysis on utilities.
