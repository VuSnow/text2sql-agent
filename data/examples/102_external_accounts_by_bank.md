# Thống kê tài khoản ngoại theo ngân hàng

## Complexity: simple

## Tables Used: external_bank_accounts

## Question (Vietnamese)
Có bao nhiêu tài khoản ngoại đang hoạt động tại mỗi ngân hàng? Ngân hàng nào có nhiều tài khoản nhất?

## Join Logic
- Chỉ cần bảng `external_bank_accounts`.
- GROUP BY bank_code để đếm số lượng.

## SQL
```sql
SELECT
    bank_code,
    bank_name,
    COUNT(*) AS total_accounts,
    COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active_accounts
FROM external_bank_accounts
GROUP BY bank_code, bank_name
ORDER BY total_accounts DESC;
```

## Explanation
Thống kê đơn giản theo ngân hàng. Dùng FILTER clause để đếm riêng tài khoản active. ORDER BY DESC để thấy ngân hàng có nhiều tài khoản nhất lên đầu.
