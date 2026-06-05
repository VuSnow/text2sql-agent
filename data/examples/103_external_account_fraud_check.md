# Kiểm tra tài khoản ngoại có bị báo cáo lừa đảo không

## Complexity: medium

## Tables Used: external_bank_accounts, reported_accounts

## Question (Vietnamese)
Kiểm tra tài khoản 0904298565 tại TCB: thông tin chủ tài khoản và xem có bị báo cáo lừa đảo không?

## Join Logic
- Cần `external_bank_accounts` để lấy thông tin cơ bản (tên chủ TK, trạng thái).
- LEFT JOIN `reported_accounts` để kiểm tra account có bị báo cáo fraud không.
- **JOIN path**: `external_bank_accounts.account_no = reported_accounts.account_no AND external_bank_accounts.bank_code = reported_accounts.bank_code`
- LEFT JOIN vì phần lớn tài khoản sẽ KHÔNG có trong reported_accounts (clean accounts).

## SQL
```sql
SELECT
    e.account_no,
    e.account_holder_name,
    e.bank_code,
    e.bank_name,
    e.status AS account_status,
    CASE WHEN r.reported_account_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_reported,
    r.risk_level,
    r.risk_score,
    r.valid_report_count,
    r.total_reported_amount
FROM external_bank_accounts e
LEFT JOIN reported_accounts r
    ON e.account_no = r.account_no
    AND e.bank_code = r.bank_code
WHERE e.account_no = '0904298565'
  AND e.bank_code = 'TCB';
```

## Explanation
LEFT JOIN để luôn trả kết quả từ external_bank_accounts dù có hoặc không có fraud report. CASE WHEN tạo flag is_reported rõ ràng. Nếu r.reported_account_id IS NULL → tài khoản sạch, chưa bị báo cáo.
