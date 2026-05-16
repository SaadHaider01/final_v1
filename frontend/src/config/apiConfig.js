export const API_BASE_URL = 'http://127.0.0.1:5000';

export const API_ENDPOINTS = {
  INGEST_SYLLABUS: '/ingest_syllabus',
  ANALYZE_QUESTION: '/analyze_question',
  LIST_SYLLABI: '/list_syllabi',
  DELETE_SYLLABUS: '/delete_syllabus',
  // Feature 4 — BOS endpoints
  BOS: '/bos',
  DEPARTMENTS: '/departments',
  SUBJECTS: '/subjects',
  // Upgrade B — URL ingestion
  INGEST_FROM_URL: '/ingest_from_url',
  PURGE_ALL: '/purge_all',
  DETECT_SUBJECT: '/detect_subject',
  // Curriculum-driven architecture (new)
  PARSE_CURRICULUM: '/parse_curriculum',
  INGEST_SELECTED: '/ingest_selected',
  CURRICULUM_HIERARCHY: '/curriculum_hierarchy',
  RESET_VECTOR_DB: '/reset_vector_db',
};
