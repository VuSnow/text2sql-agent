# Hóa đơn chưa thanh toán của khách hàng

## Complexity: medium

## Tables Used: bills, customer_biller_accounts, billers

## Question (Vietnamese)
Liệt kê tất cả hóa đơn chưa thanh toán của khách hàng CIF000001, bao gồm tên nhà cung cấp, kỳ, số tiền và hạn thanh toán.

## Join Logic
- Cần `bills` để lấy thông tin hóa đơn (amount_due, due_date, status).
- Cần `customer_biller_accounts` để filter theo cif_no (bills không có cif_no trực tiếp).
- Cần `billers` để lấy biller_name và biller_type.
- **JOIN path**: `bills.customer_bill_code = customer_biller_accounts.customer_bill_code` + `bills.biller_code = billers.biller_code`
- Filter: `bills.status = 'UNPAID'` + `customer_biller_accounts.cif_no = ?`

## SQL
```sql
SELECT
    bl.biller_name,
    bl.biller_type,
    cba.alias,
    b.bill_period,
    b.amount_due,
    b.due_date
FROM bills b
JOIN customer_biller_accounts cba ON b.customer_bill_code = cba.customer_bill_code
JOIN billers bl ON b.biller_code = bl.biller_code
WHERE cba.cif_no = 'CIF000001'
  AND b.status = 'UNPAID'
ORDER BY b.due_date ASC;
```

## Expected Behavior
Returns all unpaid bills with biller details and alias. Sorted by due_date so most urgent bills appear first.
