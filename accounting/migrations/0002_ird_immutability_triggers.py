from django.db import migrations

TRIGGER_SQL = """
-- 1. Function to completely prevent DELETE operations on financial tables
CREATE OR REPLACE FUNCTION prevent_financial_deletion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'IRD Nepal E-Billing Compliance Violation: Deletion of records from % is strictly prohibited.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

-- 2. Function to block tampering with billing totals and tax data
CREATE OR REPLACE FUNCTION prevent_invoice_tampering()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow updating only print counter or cancellation state; block changes to financial figures
    IF (OLD.invoice_number <> NEW.invoice_number) OR
       (OLD.subtotal <> NEW.subtotal) OR
       (OLD.tax_rate <> NEW.tax_rate) OR
       (OLD.tax_amount <> NEW.tax_amount) OR
       (OLD.grand_total <> NEW.grand_total) OR
       (OLD.customer_id <> NEW.customer_id) OR
       (OLD.date <> NEW.date) THEN
        RAISE EXCEPTION 'IRD Nepal E-Billing Compliance Violation: Modifying financial figures or invoice numbers is strictly forbidden.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Attach DELETE protection triggers
DROP TRIGGER IF EXISTS trg_no_delete_invoice ON accounting_invoice;
CREATE TRIGGER trg_no_delete_invoice
BEFORE DELETE ON accounting_invoice
FOR EACH ROW EXECUTE FUNCTION prevent_financial_deletion();

DROP TRIGGER IF EXISTS trg_no_delete_invoiceitem ON accounting_invoiceitem;
CREATE TRIGGER trg_no_delete_invoiceitem
BEFORE DELETE ON accounting_invoiceitem
FOR EACH ROW EXECUTE FUNCTION prevent_financial_deletion();

DROP TRIGGER IF EXISTS trg_no_delete_transaction ON accounting_transaction;
CREATE TRIGGER trg_no_delete_transaction
BEFORE DELETE ON accounting_transaction
FOR EACH ROW EXECUTE FUNCTION prevent_financial_deletion();

DROP TRIGGER IF EXISTS trg_no_delete_journalentry ON accounting_journalentry;
CREATE TRIGGER trg_no_delete_journalentry
BEFORE DELETE ON accounting_journalentry
FOR EACH ROW EXECUTE FUNCTION prevent_financial_deletion();

-- 4. Attach UPDATE tampering triggers
DROP TRIGGER IF EXISTS trg_no_tamper_invoice ON accounting_invoice;
CREATE TRIGGER trg_no_tamper_invoice
BEFORE UPDATE ON accounting_invoice
FOR EACH ROW EXECUTE FUNCTION prevent_invoice_tampering();

DROP TRIGGER IF EXISTS trg_no_update_invoiceitem ON accounting_invoiceitem;
CREATE TRIGGER trg_no_update_invoiceitem
BEFORE UPDATE ON accounting_invoiceitem
FOR EACH ROW EXECUTE FUNCTION prevent_financial_deletion();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_no_delete_invoice ON accounting_invoice;
DROP TRIGGER IF EXISTS trg_no_delete_invoiceitem ON accounting_invoiceitem;
DROP TRIGGER IF EXISTS trg_no_delete_transaction ON accounting_transaction;
DROP TRIGGER IF EXISTS trg_no_delete_journalentry ON accounting_journalentry;
DROP TRIGGER IF EXISTS trg_no_tamper_invoice ON accounting_invoice;
DROP TRIGGER IF EXISTS trg_no_update_invoiceitem ON accounting_invoiceitem;
DROP FUNCTION IF EXISTS prevent_financial_deletion();
DROP FUNCTION IF EXISTS prevent_invoice_tampering();
"""

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),  # Change this to your previous migration name
    ]

    operations = [
        migrations.RunSQL(TRIGGER_SQL, reverse_sql=REVERSE_SQL),
    ]