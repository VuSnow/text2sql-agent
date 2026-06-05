-- ============================================================
-- external_bank_accounts - Tài khoản tại ngân hàng bên ngoài
-- Simulates Napas/IBFT directory for inter-bank transfers
-- ============================================================

INSERT INTO external_bank_accounts (id, account_no, account_holder_name, bank_code, bank_name, id_number, phone, status, created_at)
SELECT
    id::INTEGER,
    account_no,
    account_holder_name,
    bank_code,
    bank_name,
    id_number,
    phone,
    status,
    created_at::TIMESTAMP
FROM csv_import_external_bank_accounts;
