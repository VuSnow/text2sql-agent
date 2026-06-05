# Giao dịch chuyển khoản đến tài khoản ngoại cụ thể

## Complexity: complex

## Tables Used: transactions, external_bank_accounts, customers

## Question (Vietnamese)
Liệt kê tất cả giao dịch chuyển khoản liên ngân hàng đến tài khoản 90311860909 tại VCB, bao gồm thông tin người gửi.

## Join Logic
- Cần `transactions` cho dữ liệu giao dịch.
- Cần `external_bank_accounts` để xác nhận thông tin người nhận.
- Cần `customers` để lấy tên người gửi.
- **JOIN path 1**: `transactions.counterparty_account = external_bank_accounts.account_no AND transactions.counterparty_bank_code = external_bank_accounts.bank_code`
- **JOIN path 2**: `transactions.cif_no = customers.cif_no`

## SQL
```sql
SELECT
    t.transaction_ref,
    t.transaction_time,
    c.full_name AS sender_name,
    t.amount,
    e.account_holder_name AS receiver_name,
    e.bank_name AS receiver_bank,
    t.channel,
    t.status
FROM transactions t
JOIN customers c ON t.cif_no = c.cif_no
JOIN external_bank_accounts e
    ON t.counterparty_account = e.account_no
    AND t.counterparty_bank_code = e.bank_code
WHERE e.account_no = '90311860909'
  AND e.bank_code = 'VCB'
  AND t.transaction_type = 'BANK_TRANSFER'
  AND t.direction = 'OUT'
ORDER BY t.transaction_time DESC;
```

## Explanation
3-table JOIN. INNER JOIN external_bank_accounts vì ta biết chắc tài khoản tồn tại. Filter direction = 'OUT' vì đây là giao dịch chuyển đi. ORDER BY time DESC để thấy giao dịch gần nhất trước.
