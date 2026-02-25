-- Insert test documents for different levels and subjects
INSERT INTO documents (id, filename, subject, level, year, ingestion_status, is_personal, is_shared, official_duration_minutes, instructions, created_at, updated_at) 
VALUES 
  ('doc-001', 'P6_Mathematics_2024.pdf', 'Mathematics', 'P6', 2024, 'COMPLETED', false, true, 120, 'Complete all sections', NOW(), NOW()),
  ('doc-002', 'P6_Science_2024.pdf', 'Science and Elementary Technology', 'P6', 2024, 'COMPLETED', false, true, 120, 'Show your work', NOW(), NOW()),
  ('doc-003', 'S3_English_2023.pdf', 'English Language', 'S3', 2023, 'COMPLETED', false, true, 180, 'Answer in full sentences', NOW(), NOW()),
  ('doc-004', 'S3_Mathematics_2023.pdf', 'Mathematics', 'S3', 2023, 'COMPLETED', false, true, 180, 'Show calculations', NOW(), NOW()),
  ('doc-005', 'S6_Physics_2024.pdf', 'Physics', 'S6', 2024, 'COMPLETED', false, true, 240, 'Show all working', NOW(), NOW()),
  ('doc-006', 'S6_Chemistry_2024.pdf', 'Chemistry', 'S6', 2024, 'COMPLETED', false, true, 240, 'Use IUPAC nomenclature', NOW(), NOW());

-- Select to confirm
SELECT id, filename, subject, level, ingestion_status FROM documents ORDER BY level, subject;
