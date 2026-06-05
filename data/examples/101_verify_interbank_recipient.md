# Tra cứu chủ tài khoản liên ngân hàng (verify recipient)

## Complexity: simple

## Tables Used: external_bank_accounts

## Question (Vietnamese)
Tra cứu chủ tài khoản số 90311860909 tại Vietcombank (VCB) để xác nhận trước khi chuyển tiền.

## Join Logic
- Chỉ cần bảng `external_bank_accounts` — lookup theo cặp (account_no, bank_code).
- Đây là use case chính: xác minh tên chủ tài khoản nhận trước khi thực hiện chuyển khoản liên ngân hàng.

## SQL
```sql
SELECT
    account_no,
    account_holder_name,
    bank_code,
    bank_name,
    status
FROM external_bank_accounts
WHERE account_no = '90311860909'
  AND bank_code = 'VCB';
```

## Explanation
Lookup đơn giản theo composite key (account_no, bank_code). Trả về tên chủ tài khoản và trạng thái. Nếu status != 'ACTIVE' thì không cho phép chuyển. Nếu không có row → tài khoản không tồn tại.
