from django.db import migrations

TRIGGER_SQL = """
-- Attach delete protection to credit notes and line items
DROP TRIGGER IF EXISTS trg_no_delete_creditnote ON accounting_creditnote;
CREATE TRIGGER trg_no_delete_creditnote
BEFORE DELETE ON accounting_creditnote
FOR EACH ROW EXECUTE FUNCTION prevent_financial_deletion();

DROP TRIGGER IF EXISTS trg_no_delete_creditnoteitem ON accounting_creditnoteitem;
CREATE TRIGGER trg_no_delete_creditnoteitem
BEFORE DELETE ON accounting_creditnoteitem
FOR EACH ROW EXECUTE FUNCTION prevent_financial_deletion();

-- Function to prevent tampering with credit note figures
CREATE OR REPLACE FUNCTION prevent_creditnote_tampering()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.credit_note_number <> NEW.credit_note_number) OR
       (OLD.taxable_subtotal <> NEW.taxable_subtotal) OR
       (OLD.tax_rate <> NEW.tax_rate) OR
       (OLD.tax_amount <> NEW.tax_amount) OR
       (OLD.grand_total <> NEW.grand_total) OR
       (OLD.customer_id <> NEW.customer_id) OR
       (OLD.original_invoice_id <> NEW.original_invoice_id) OR
       (OLD.date <> NEW.date) THEN
        RAISE EXCEPTION 'IRD Nepal E-Billing Compliance Violation: Modifying credit note financial amounts or invoice linkage is strictly forbidden.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_no_tamper_creditnote ON accounting_creditnote;
CREATE TRIGGER trg_no_tamper_creditnote
BEFORE UPDATE ON accounting_creditnote
FOR EACH ROW EXECUTE FUNCTION prevent_creditnote_tampering();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_no_delete_creditnote ON accounting_creditnote;
DROP TRIGGER IF EXISTS trg_no_delete_creditnoteitem ON accounting_creditnoteitem;
DROP TRIGGER IF EXISTS trg_no_tamper_creditnote ON accounting_creditnote;
DROP FUNCTION IF EXISTS prevent_creditnote_tampering();
"""

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0005_creditnote_creditnoteitem'),
    ]

    operations = [
        migrations.RunSQL(TRIGGER_SQL, reverse_sql=REVERSE_SQL),
    ]