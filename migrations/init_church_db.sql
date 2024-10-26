-- Drop existing table if it exists
DROP TABLE IF EXISTS church_partner_records;

-- Create church_partner_records table with proper schema
CREATE TABLE church_partner_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL,
    record_data TEXT NOT NULL,
    submission_date DATETIME NOT NULL
);
