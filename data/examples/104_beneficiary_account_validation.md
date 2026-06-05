# Đối chiếu beneficiary đã lưu với tài khoản thực tế

## Complexity: medium

## Tables Used: beneficiaries, external_bank_accounts

## Question (Vietnamese)
Đối chiếu danh bạ người nhận đã lưu của khách hàng CIF000001 với thông tin tài khoản thực tế. Có tài khoản nào đã bị đóng hoặc khóa không?

## Join Logic
- Cần `beneficiaries` để lấy danh sách người nhận đã lưu.
- JOIN `external_bank_accounts` để kiểm tra trạng thái thực tế hiện tại.
- **JOIN path**: `beneficiaries.beneficiary_account_no = external_bank_accounts.account_no AND beneficiaries.beneficiary_bank_code = external_bank_accounts.bank_code`
- LEFT JOIN vì beneficiary có thể trỏ đến TK SHB (nằm trong bảng accounts, không phải external).

## SQL
```sql
SELECT
    b.beneficiary_name,
    b.beneficiary_account_no,
    b.beneficiary_bank_code,
    b.beneficiary_bank_name,
    b.nickname,
    e.account_holder_name AS actual_name,
    e.status AS current_status,
    CASE
        WHEN e.account_no IS NULL THEN 'INTERNAL_OR_UNKNOWN'
        WHEN e.status != 'ACTIVE' THEN 'INACTIVE'
        ELSE 'OK'
    END AS check_result
FROM beneficiaries b
LEFT JOIN external_bank_accounts e
    ON b.beneficiary_account_no = e.account_no
    AND b.beneficiary_bank_code = e.bank_code
WHERE b.cif_no = 'CIF000001'
  AND b.is_saved = TRUE
ORDER BY check_result DESC, b.last_used_at DESC;
```

## Explanation
LEFT JOIN vì beneficiary có thể là TK nội bộ SHB. CASE WHEN phân loại: NULL = TK nội bộ hoặc chưa có trong directory, INACTIVE = TK đã đóng/khóa. ORDER BY check_result DESC đưa vấn đề lên đầu.
