"""Create the complete initial Weave CBT database schema.

Revision ID: 0001_initial_schema
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

_UPGRADE_SQL = (
'CREATE TABLE academic_admins ( email VARCHAR(255) NOT NULL, status VARCHAR(64) NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_academic_admins PRIMARY KEY (id) )',
'CREATE INDEX ix_academic_admins_email ON academic_admins (email)',
'CREATE INDEX ix_academic_admins_source_deleted_at ON academic_admins (source_deleted_at)',
'CREATE INDEX ix_academic_admins_status ON academic_admins (status)',
'CREATE TABLE academic_levels ( name VARCHAR(255) NOT NULL, category VARCHAR(64) NOT NULL, position INTEGER NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_academic_levels PRIMARY KEY (id), CONSTRAINT ck_academic_levels_position_nonnegative CHECK (position >= 0) )',
'CREATE INDEX ix_academic_levels_category ON academic_levels (category)',
'CREATE INDEX ix_academic_levels_category_position ON academic_levels (category, position)',
'CREATE INDEX ix_academic_levels_source_deleted_at ON academic_levels (source_deleted_at)',
'CREATE TABLE academic_sessions ( name VARCHAR(255) NOT NULL, status VARCHAR(64) NOT NULL, is_current BOOLEAN DEFAULT false NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_academic_sessions PRIMARY KEY (id) )',
'CREATE INDEX ix_academic_sessions_current_status ON academic_sessions (is_current, status)',
'CREATE INDEX ix_academic_sessions_is_current ON academic_sessions (is_current)',
'CREATE INDEX ix_academic_sessions_source_deleted_at ON academic_sessions (source_deleted_at)',
'CREATE INDEX ix_academic_sessions_status ON academic_sessions (status)',
'CREATE TABLE academic_subjects ( name VARCHAR(255) NOT NULL, code VARCHAR(64), is_active BOOLEAN DEFAULT true NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_academic_subjects PRIMARY KEY (id) )',
'CREATE INDEX ix_academic_subjects_is_active ON academic_subjects (is_active)',
'CREATE INDEX ix_academic_subjects_source_deleted_at ON academic_subjects (source_deleted_at)',
'CREATE TABLE academic_teachers ( teacher_account_id UUID NOT NULL, first_name VARCHAR(255), last_name VARCHAR(255), staff_id VARCHAR(128), status VARCHAR(64) NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_academic_teachers PRIMARY KEY (id) )',
'CREATE INDEX ix_academic_teachers_source_deleted_at ON academic_teachers (source_deleted_at)',
'CREATE INDEX ix_academic_teachers_staff_id ON academic_teachers (staff_id)',
'CREATE INDEX ix_academic_teachers_status ON academic_teachers (status)',
'CREATE INDEX ix_academic_teachers_status_name ON academic_teachers (status, last_name, first_name)',
'CREATE INDEX ix_academic_teachers_teacher_account_id ON academic_teachers (teacher_account_id)',
'CREATE TABLE arm_labels ( label VARCHAR(64) NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_arm_labels PRIMARY KEY (id) )',
'CREATE INDEX ix_arm_labels_source_deleted_at ON arm_labels (source_deleted_at)',
'CREATE UNIQUE INDEX uq_arm_labels_current_label ON arm_labels (label) WHERE source_deleted_at IS NULL',
'CREATE TABLE assessment_schemes ( name VARCHAR(255) NOT NULL, status VARCHAR(64) NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_assessment_schemes PRIMARY KEY (id) )',
'CREATE INDEX ix_assessment_schemes_source_deleted_at ON assessment_schemes (source_deleted_at)',
'CREATE INDEX ix_assessment_schemes_status ON assessment_schemes (status)',
"CREATE TABLE audit_events ( actor_type VARCHAR(11) NOT NULL, actor_id UUID, actor_name VARCHAR(255), actor_role VARCHAR(64), action VARCHAR(128) NOT NULL, outcome VARCHAR(7) DEFAULT 'success' NOT NULL, entity_type VARCHAR(64), entity_id UUID, entity_label VARCHAR(255), reason TEXT, metadata_json JSONB, request_id VARCHAR(128), client_ip VARCHAR(45), created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_audit_events PRIMARY KEY (id), CONSTRAINT audit_actor_type CHECK (actor_type IN ('local_actor', 'candidate', 'system')), CONSTRAINT audit_outcome CHECK (outcome IN ('success', 'denied', 'failed')) )",
'CREATE INDEX ix_audit_events_action ON audit_events (action)',
'CREATE INDEX ix_audit_events_action_created ON audit_events (action, created_at)',
'CREATE INDEX ix_audit_events_actor_created ON audit_events (actor_type, actor_id, created_at)',
'CREATE INDEX ix_audit_events_actor_id ON audit_events (actor_id)',
'CREATE INDEX ix_audit_events_actor_type ON audit_events (actor_type)',
'CREATE INDEX ix_audit_events_entity_created ON audit_events (entity_type, entity_id, created_at)',
'CREATE INDEX ix_audit_events_entity_id ON audit_events (entity_id)',
'CREATE INDEX ix_audit_events_entity_type ON audit_events (entity_type)',
'CREATE INDEX ix_audit_events_outcome ON audit_events (outcome)',
'CREATE INDEX ix_audit_events_outcome_created ON audit_events (outcome, created_at)',
'CREATE INDEX ix_audit_events_request_id ON audit_events (request_id)',
'CREATE TABLE local_actors ( weave_actor_id VARCHAR(128) NOT NULL, weave_membership_id VARCHAR(128), role VARCHAR(64) NOT NULL, email VARCHAR(255) NOT NULL, display_name VARCHAR(255) NOT NULL, is_active BOOLEAN NOT NULL, last_weave_authenticated_at TIMESTAMP WITH TIME ZONE NOT NULL, last_weave_revalidated_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_local_actors PRIMARY KEY (id), CONSTRAINT uq_local_actors_weave_actor_role UNIQUE (weave_actor_id, role), CONSTRAINT ck_local_actors_role_not_blank CHECK (char_length(trim(role)) > 0), CONSTRAINT ck_local_actors_email_not_blank CHECK (char_length(trim(email)) > 0) )',
'CREATE INDEX ix_local_actors_email ON local_actors (email)',
'CREATE INDEX ix_local_actors_role ON local_actors (role)',
'CREATE INDEX ix_local_actors_role_active ON local_actors (role, is_active)',
'CREATE UNIQUE INDEX ix_local_actors_weave_membership_id ON local_actors (weave_membership_id)',
'CREATE TABLE school_profiles ( name VARCHAR(255) NOT NULL, institution_type VARCHAR(64), timezone VARCHAR(128) NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_school_profiles PRIMARY KEY (id) )',
'CREATE INDEX ix_school_profiles_source_deleted_at ON school_profiles (source_deleted_at)',
'CREATE TABLE sync_states ( scope VARCHAR(64) NOT NULL, schema_version INTEGER DEFAULT 2 NOT NULL, cursor BIGINT DEFAULT 0 NOT NULL, bootstrap_snapshot_id UUID, bootstrap_completed_at TIMESTAMP WITH TIME ZONE, last_attempted_at TIMESTAMP WITH TIME ZONE, last_successful_at TIMESTAMP WITH TIME ZONE, last_error TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_sync_states PRIMARY KEY (id), CONSTRAINT ck_sync_states_cursor_nonnegative CHECK (cursor >= 0), CONSTRAINT ck_sync_states_schema_version_positive CHECK (schema_version >= 1), CONSTRAINT ck_sync_states_error_length CHECK (last_error IS NULL OR char_length(last_error) <= 1024), CONSTRAINT uq_sync_states_scope UNIQUE (scope) )',
'CREATE TABLE academic_classes ( academic_level_id UUID NOT NULL, arm_label_id UUID NOT NULL, display_name VARCHAR(255) NOT NULL, is_active BOOLEAN DEFAULT true NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_academic_classes PRIMARY KEY (id), CONSTRAINT fk_academic_classes_academic_level_id_academic_levels FOREIGN KEY(academic_level_id) REFERENCES academic_levels (id) ON DELETE RESTRICT, CONSTRAINT fk_academic_classes_arm_label_id_arm_labels FOREIGN KEY(arm_label_id) REFERENCES arm_labels (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_academic_classes_academic_level_id ON academic_classes (academic_level_id)',
'CREATE INDEX ix_academic_classes_arm_label_id ON academic_classes (arm_label_id)',
'CREATE INDEX ix_academic_classes_is_active ON academic_classes (is_active)',
'CREATE INDEX ix_academic_classes_level_active ON academic_classes (academic_level_id, is_active)',
'CREATE INDEX ix_academic_classes_source_deleted_at ON academic_classes (source_deleted_at)',
'CREATE UNIQUE INDEX uq_academic_classes_current_level_arm_label ON academic_classes (academic_level_id, arm_label_id) WHERE source_deleted_at IS NULL',
'CREATE TABLE academic_terms ( academic_session_id UUID NOT NULL, name VARCHAR(255) NOT NULL, status VARCHAR(64) NOT NULL, is_current BOOLEAN DEFAULT false NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_academic_terms PRIMARY KEY (id), CONSTRAINT fk_academic_terms_academic_session_id_academic_sessions FOREIGN KEY(academic_session_id) REFERENCES academic_sessions (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_academic_terms_academic_session_id ON academic_terms (academic_session_id)',
'CREATE INDEX ix_academic_terms_is_current ON academic_terms (is_current)',
'CREATE INDEX ix_academic_terms_session_current ON academic_terms (academic_session_id, is_current)',
'CREATE INDEX ix_academic_terms_source_deleted_at ON academic_terms (source_deleted_at)',
'CREATE INDEX ix_academic_terms_status ON academic_terms (status)',
'CREATE TABLE assessment_components ( assessment_scheme_id UUID NOT NULL, name VARCHAR(255) NOT NULL, code VARCHAR(64), maximum_score NUMERIC(8, 2) NOT NULL, position INTEGER NOT NULL, is_active BOOLEAN DEFAULT true NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_assessment_components PRIMARY KEY (id), CONSTRAINT ck_assessment_components_maximum_positive CHECK (maximum_score > 0), CONSTRAINT ck_assessment_components_position_nonnegative CHECK (position >= 0), CONSTRAINT fk_assessment_components_assessment_scheme_id_assessmen_79e0 FOREIGN KEY(assessment_scheme_id) REFERENCES assessment_schemes (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_assessment_components_assessment_scheme_id ON assessment_components (assessment_scheme_id)',
'CREATE INDEX ix_assessment_components_is_active ON assessment_components (is_active)',
'CREATE INDEX ix_assessment_components_scheme_active ON assessment_components (assessment_scheme_id, is_active)',
'CREATE INDEX ix_assessment_components_source_deleted_at ON assessment_components (source_deleted_at)',
'CREATE UNIQUE INDEX uq_assessment_components_current_scheme_position ON assessment_components (assessment_scheme_id, position) WHERE source_deleted_at IS NULL',
'CREATE TABLE curricula ( academic_level_id UUID NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_curricula PRIMARY KEY (id), CONSTRAINT fk_curricula_academic_level_id_academic_levels FOREIGN KEY(academic_level_id) REFERENCES academic_levels (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_curricula_academic_level_id ON curricula (academic_level_id)',
'CREATE INDEX ix_curricula_source_deleted_at ON curricula (source_deleted_at)',
'CREATE UNIQUE INDEX uq_curricula_current_level ON curricula (academic_level_id) WHERE source_deleted_at IS NULL',
'CREATE TABLE departments ( academic_level_id UUID NOT NULL, name VARCHAR(255) NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_departments PRIMARY KEY (id), CONSTRAINT fk_departments_academic_level_id_academic_levels FOREIGN KEY(academic_level_id) REFERENCES academic_levels (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_departments_academic_level_id ON departments (academic_level_id)',
'CREATE INDEX ix_departments_level_name ON departments (academic_level_id, name)',
'CREATE INDEX ix_departments_source_deleted_at ON departments (source_deleted_at)',
'CREATE UNIQUE INDEX uq_departments_current_level_name ON departments (academic_level_id, name) WHERE source_deleted_at IS NULL',
'CREATE TABLE local_actor_sessions ( actor_id UUID NOT NULL, expires_at TIMESTAMP WITH TIME ZONE NOT NULL, last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, last_refreshed_at TIMESTAMP WITH TIME ZONE, revoked_at TIMESTAMP WITH TIME ZONE, revocation_reason VARCHAR(500), created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_local_actor_sessions PRIMARY KEY (id), CONSTRAINT ck_local_actor_sessions_valid_expiry CHECK (expires_at > created_at), CONSTRAINT ck_local_actor_sessions_valid_revocation CHECK (revoked_at IS NULL OR revoked_at >= created_at), CONSTRAINT fk_local_actor_sessions_actor_id_local_actors FOREIGN KEY(actor_id) REFERENCES local_actors (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_local_actor_sessions_actor_expiry ON local_actor_sessions (actor_id, expires_at)',
'CREATE INDEX ix_local_actor_sessions_actor_id ON local_actor_sessions (actor_id)',
'CREATE INDEX ix_local_actor_sessions_actor_revoked ON local_actor_sessions (actor_id, revoked_at)',
'CREATE INDEX ix_local_actor_sessions_expires_at ON local_actor_sessions (expires_at)',
'CREATE INDEX ix_local_actor_sessions_revoked_at ON local_actor_sessions (revoked_at)',
'CREATE TABLE class_term_departments ( class_id UUID NOT NULL, academic_term_id UUID NOT NULL, department_id UUID NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_class_term_departments PRIMARY KEY (id), CONSTRAINT fk_class_term_departments_class_id_academic_classes FOREIGN KEY(class_id) REFERENCES academic_classes (id) ON DELETE RESTRICT, CONSTRAINT fk_class_term_departments_academic_term_id_academic_terms FOREIGN KEY(academic_term_id) REFERENCES academic_terms (id) ON DELETE RESTRICT, CONSTRAINT fk_class_term_departments_department_id_departments FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_class_term_departments_academic_term_id ON class_term_departments (academic_term_id)',
'CREATE INDEX ix_class_term_departments_class_id ON class_term_departments (class_id)',
'CREATE INDEX ix_class_term_departments_department_id ON class_term_departments (department_id)',
'CREATE INDEX ix_class_term_departments_source_deleted_at ON class_term_departments (source_deleted_at)',
'CREATE INDEX ix_class_term_departments_term_department ON class_term_departments (academic_term_id, department_id)',
'CREATE UNIQUE INDEX uq_class_term_departments_current_class_term ON class_term_departments (class_id, academic_term_id) WHERE source_deleted_at IS NULL',
'CREATE TABLE curriculum_subjects ( curriculum_id UUID NOT NULL, subject_id UUID NOT NULL, is_elective BOOLEAN DEFAULT false NOT NULL, is_active BOOLEAN DEFAULT true NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_curriculum_subjects PRIMARY KEY (id), CONSTRAINT fk_curriculum_subjects_curriculum_id_curricula FOREIGN KEY(curriculum_id) REFERENCES curricula (id) ON DELETE RESTRICT, CONSTRAINT fk_curriculum_subjects_subject_id_academic_subjects FOREIGN KEY(subject_id) REFERENCES academic_subjects (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_curriculum_subjects_curriculum_active ON curriculum_subjects (curriculum_id, is_active)',
'CREATE INDEX ix_curriculum_subjects_curriculum_id ON curriculum_subjects (curriculum_id)',
'CREATE INDEX ix_curriculum_subjects_is_active ON curriculum_subjects (is_active)',
'CREATE INDEX ix_curriculum_subjects_is_elective ON curriculum_subjects (is_elective)',
'CREATE INDEX ix_curriculum_subjects_source_deleted_at ON curriculum_subjects (source_deleted_at)',
'CREATE INDEX ix_curriculum_subjects_subject_id ON curriculum_subjects (subject_id)',
'CREATE UNIQUE INDEX uq_curriculum_subjects_current_curriculum_subject ON curriculum_subjects (curriculum_id, subject_id) WHERE source_deleted_at IS NULL',
'CREATE TABLE local_refresh_tokens ( session_id UUID NOT NULL, token_hash VARCHAR(64) NOT NULL, expires_at TIMESTAMP WITH TIME ZONE NOT NULL, consumed_at TIMESTAMP WITH TIME ZONE, revoked_at TIMESTAMP WITH TIME ZONE, reuse_detected_at TIMESTAMP WITH TIME ZONE, replaced_by_token_id UUID, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_local_refresh_tokens PRIMARY KEY (id), CONSTRAINT ck_local_refresh_tokens_valid_expiry CHECK (expires_at > created_at), CONSTRAINT ck_local_refresh_tokens_valid_consumed_at CHECK (consumed_at IS NULL OR consumed_at >= created_at), CONSTRAINT ck_local_refresh_tokens_valid_revoked_at CHECK (revoked_at IS NULL OR revoked_at >= created_at), CONSTRAINT ck_local_refresh_tokens_valid_reuse_at CHECK (reuse_detected_at IS NULL OR reuse_detected_at >= created_at), CONSTRAINT ck_local_refresh_tokens_not_self_replaced CHECK (replaced_by_token_id IS NULL OR replaced_by_token_id <> id), CONSTRAINT fk_local_refresh_tokens_session_id_local_actor_sessions FOREIGN KEY(session_id) REFERENCES local_actor_sessions (id) ON DELETE CASCADE, CONSTRAINT fk_local_refresh_tokens_replaced_by_token_id_local_refr_64b4 FOREIGN KEY(replaced_by_token_id) REFERENCES local_refresh_tokens (id) ON DELETE SET NULL )',
'CREATE INDEX ix_local_refresh_tokens_expires_at ON local_refresh_tokens (expires_at)',
'CREATE INDEX ix_local_refresh_tokens_session_consumed ON local_refresh_tokens (session_id, consumed_at)',
'CREATE INDEX ix_local_refresh_tokens_session_expiry ON local_refresh_tokens (session_id, expires_at)',
'CREATE INDEX ix_local_refresh_tokens_session_id ON local_refresh_tokens (session_id)',
'CREATE UNIQUE INDEX ix_local_refresh_tokens_token_hash ON local_refresh_tokens (token_hash)',
'CREATE TABLE student_enrollments ( student_id UUID NOT NULL, admission_number VARCHAR(128) NOT NULL, first_name VARCHAR(255), last_name VARCHAR(255), academic_level_id UUID NOT NULL, class_id UUID, academic_session_id UUID NOT NULL, is_current BOOLEAN DEFAULT true NOT NULL, student_status VARCHAR(64) NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_student_enrollments PRIMARY KEY (id), CONSTRAINT fk_student_enrollments_academic_level_id_academic_levels FOREIGN KEY(academic_level_id) REFERENCES academic_levels (id) ON DELETE RESTRICT, CONSTRAINT fk_student_enrollments_class_id_academic_classes FOREIGN KEY(class_id) REFERENCES academic_classes (id) ON DELETE RESTRICT, CONSTRAINT fk_student_enrollments_academic_session_id_academic_sessions FOREIGN KEY(academic_session_id) REFERENCES academic_sessions (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_student_enrollments_academic_level_id ON student_enrollments (academic_level_id)',
'CREATE INDEX ix_student_enrollments_academic_session_id ON student_enrollments (academic_session_id)',
'CREATE INDEX ix_student_enrollments_admission_number ON student_enrollments (admission_number)',
'CREATE INDEX ix_student_enrollments_class_current ON student_enrollments (class_id, is_current)',
'CREATE INDEX ix_student_enrollments_class_id ON student_enrollments (class_id)',
'CREATE INDEX ix_student_enrollments_is_current ON student_enrollments (is_current)',
'CREATE INDEX ix_student_enrollments_session_current ON student_enrollments (academic_session_id, is_current)',
'CREATE INDEX ix_student_enrollments_source_deleted_at ON student_enrollments (source_deleted_at)',
'CREATE INDEX ix_student_enrollments_student_id ON student_enrollments (student_id)',
'CREATE INDEX ix_student_enrollments_student_status ON student_enrollments (student_status)',
'CREATE UNIQUE INDEX uq_student_enrollments_current_student ON student_enrollments (student_id) WHERE is_current = true AND source_deleted_at IS NULL',
"CREATE TABLE exams ( session_id UUID NOT NULL, term_id UUID NOT NULL, curriculum_subject_id UUID NOT NULL, assessment_scheme_id UUID NOT NULL, assessment_component_id UUID NOT NULL, title VARCHAR(255) NOT NULL, instructions TEXT, status VARCHAR(9) DEFAULT 'draft' NOT NULL, duration_minutes INTEGER NOT NULL, maximum_score NUMERIC(8, 2) NOT NULL, opens_at TIMESTAMP WITH TIME ZONE, closes_at TIMESTAMP WITH TIME ZONE, shuffle_questions BOOLEAN DEFAULT true NOT NULL, shuffle_options BOOLEAN DEFAULT true NOT NULL, created_by_actor_id UUID NOT NULL, submitted_by_actor_id UUID, submitted_at TIMESTAMP WITH TIME ZONE, sealed_at TIMESTAMP WITH TIME ZONE, activated_at TIMESTAMP WITH TIME ZONE, closed_at TIMESTAMP WITH TIME ZONE, cancelled_at TIMESTAMP WITH TIME ZONE, source_assessment_scheme_id UUID, source_assessment_component_id UUID, source_assessment_component_name VARCHAR(255), source_assessment_component_code VARCHAR(64), source_assessment_component_maximum_score NUMERIC(8, 2), weave_calendar_event_id VARCHAR(128), calendar_synced_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exams PRIMARY KEY (id), CONSTRAINT ck_exams_duration_positive CHECK (duration_minutes > 0), CONSTRAINT ck_exams_maximum_score_positive CHECK (maximum_score > 0), CONSTRAINT ck_exams_source_component_maximum_positive CHECK (source_assessment_component_maximum_score IS NULL OR source_assessment_component_maximum_score > 0), CONSTRAINT ck_exams_valid_schedule CHECK (closes_at IS NULL OR opens_at IS NULL OR closes_at > opens_at), CONSTRAINT ck_exams_submission_actor_required CHECK (submitted_at IS NULL OR submitted_by_actor_id IS NOT NULL), CONSTRAINT fk_exams_session_id_academic_sessions FOREIGN KEY(session_id) REFERENCES academic_sessions (id) ON DELETE RESTRICT, CONSTRAINT fk_exams_term_id_academic_terms FOREIGN KEY(term_id) REFERENCES academic_terms (id) ON DELETE RESTRICT, CONSTRAINT fk_exams_curriculum_subject_id_curriculum_subjects FOREIGN KEY(curriculum_subject_id) REFERENCES curriculum_subjects (id) ON DELETE RESTRICT, CONSTRAINT fk_exams_assessment_scheme_id_assessment_schemes FOREIGN KEY(assessment_scheme_id) REFERENCES assessment_schemes (id) ON DELETE RESTRICT, CONSTRAINT fk_exams_assessment_component_id_assessment_components FOREIGN KEY(assessment_component_id) REFERENCES assessment_components (id) ON DELETE RESTRICT, CONSTRAINT exam_status CHECK (status IN ('draft', 'submitted', 'sealed', 'active', 'closed', 'cancelled')), CONSTRAINT fk_exams_created_by_actor_id_local_actors FOREIGN KEY(created_by_actor_id) REFERENCES local_actors (id) ON DELETE RESTRICT, CONSTRAINT fk_exams_submitted_by_actor_id_local_actors FOREIGN KEY(submitted_by_actor_id) REFERENCES local_actors (id) ON DELETE RESTRICT )",
'CREATE INDEX ix_exams_assessment_component_id ON exams (assessment_component_id)',
'CREATE INDEX ix_exams_assessment_scheme_id ON exams (assessment_scheme_id)',
'CREATE INDEX ix_exams_component_status ON exams (assessment_component_id, status)',
'CREATE INDEX ix_exams_created_by_actor_id ON exams (created_by_actor_id)',
'CREATE INDEX ix_exams_curriculum_subject_id ON exams (curriculum_subject_id)',
'CREATE INDEX ix_exams_curriculum_subject_status ON exams (curriculum_subject_id, status)',
'CREATE INDEX ix_exams_session_id ON exams (session_id)',
'CREATE INDEX ix_exams_session_term_status ON exams (session_id, term_id, status)',
'CREATE INDEX ix_exams_status ON exams (status)',
'CREATE INDEX ix_exams_submitted_by_actor_id ON exams (submitted_by_actor_id)',
'CREATE INDEX ix_exams_term_id ON exams (term_id)',
'CREATE UNIQUE INDEX ix_exams_weave_calendar_event_id ON exams (weave_calendar_event_id)',
'CREATE UNIQUE INDEX uq_exams_term_curriculum_subject_title_lower ON exams (term_id, curriculum_subject_id, lower(title))',
'CREATE TABLE question_banks ( curriculum_subject_id UUID NOT NULL, name VARCHAR(255) NOT NULL, description TEXT, created_by_actor_id UUID NOT NULL, is_active BOOLEAN DEFAULT true NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_question_banks PRIMARY KEY (id), CONSTRAINT uq_question_banks_curriculum_subject_name UNIQUE (curriculum_subject_id, name), CONSTRAINT fk_question_banks_curriculum_subject_id_curriculum_subjects FOREIGN KEY(curriculum_subject_id) REFERENCES curriculum_subjects (id) ON DELETE RESTRICT, CONSTRAINT fk_question_banks_created_by_actor_id_local_actors FOREIGN KEY(created_by_actor_id) REFERENCES local_actors (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_question_banks_created_by_actor_id ON question_banks (created_by_actor_id)',
'CREATE INDEX ix_question_banks_curriculum_subject_active ON question_banks (curriculum_subject_id, is_active)',
'CREATE INDEX ix_question_banks_curriculum_subject_id ON question_banks (curriculum_subject_id)',
'CREATE TABLE subject_offerings ( curriculum_subject_id UUID NOT NULL, academic_term_id UUID NOT NULL, department_id UUID, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_subject_offerings PRIMARY KEY (id), CONSTRAINT fk_subject_offerings_curriculum_subject_id_curriculum_subjects FOREIGN KEY(curriculum_subject_id) REFERENCES curriculum_subjects (id) ON DELETE RESTRICT, CONSTRAINT fk_subject_offerings_academic_term_id_academic_terms FOREIGN KEY(academic_term_id) REFERENCES academic_terms (id) ON DELETE RESTRICT, CONSTRAINT fk_subject_offerings_department_id_departments FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_subject_offerings_academic_term_id ON subject_offerings (academic_term_id)',
'CREATE INDEX ix_subject_offerings_curriculum_subject_id ON subject_offerings (curriculum_subject_id)',
'CREATE INDEX ix_subject_offerings_department_id ON subject_offerings (department_id)',
'CREATE INDEX ix_subject_offerings_source_deleted_at ON subject_offerings (source_deleted_at)',
'CREATE INDEX ix_subject_offerings_term_subject ON subject_offerings (academic_term_id, curriculum_subject_id)',
'CREATE UNIQUE INDEX uq_subject_offerings_department ON subject_offerings (curriculum_subject_id, academic_term_id, department_id) WHERE department_id IS NOT NULL AND source_deleted_at IS NULL',
'CREATE UNIQUE INDEX uq_subject_offerings_general ON subject_offerings (curriculum_subject_id, academic_term_id) WHERE department_id IS NULL AND source_deleted_at IS NULL',
'CREATE TABLE teacher_assignments ( teacher_membership_id UUID NOT NULL, class_id UUID NOT NULL, curriculum_subject_id UUID NOT NULL, is_active BOOLEAN DEFAULT true NOT NULL, synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, source_deleted_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_teacher_assignments PRIMARY KEY (id), CONSTRAINT fk_teacher_assignments_teacher_membership_id_academic_teachers FOREIGN KEY(teacher_membership_id) REFERENCES academic_teachers (id) ON DELETE RESTRICT, CONSTRAINT fk_teacher_assignments_class_id_academic_classes FOREIGN KEY(class_id) REFERENCES academic_classes (id) ON DELETE RESTRICT, CONSTRAINT fk_teacher_assignments_curriculum_subject_id_curriculum_5da4 FOREIGN KEY(curriculum_subject_id) REFERENCES curriculum_subjects (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_teacher_assignments_class_id ON teacher_assignments (class_id)',
'CREATE INDEX ix_teacher_assignments_class_subject_active ON teacher_assignments (class_id, curriculum_subject_id, is_active)',
'CREATE INDEX ix_teacher_assignments_curriculum_subject_id ON teacher_assignments (curriculum_subject_id)',
'CREATE INDEX ix_teacher_assignments_is_active ON teacher_assignments (is_active)',
'CREATE INDEX ix_teacher_assignments_source_deleted_at ON teacher_assignments (source_deleted_at)',
'CREATE INDEX ix_teacher_assignments_teacher_active ON teacher_assignments (teacher_membership_id, is_active)',
'CREATE INDEX ix_teacher_assignments_teacher_membership_id ON teacher_assignments (teacher_membership_id)',
'CREATE UNIQUE INDEX uq_teacher_assignments_active_scope ON teacher_assignments (class_id, curriculum_subject_id) WHERE is_active = true AND source_deleted_at IS NULL',
"CREATE TABLE exam_candidates ( exam_id UUID NOT NULL, enrollment_id UUID NOT NULL, student_id UUID NOT NULL, admission_number VARCHAR(128) NOT NULL, display_name VARCHAR(255) NOT NULL, status VARCHAR(9) DEFAULT 'eligible' NOT NULL, status_reason VARCHAR(500), created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exam_candidates PRIMARY KEY (id), CONSTRAINT uq_exam_candidates_exam_enrollment UNIQUE (exam_id, enrollment_id), CONSTRAINT uq_exam_candidates_exam_student UNIQUE (exam_id, student_id), CONSTRAINT uq_exam_candidates_exam_admission_number UNIQUE (exam_id, admission_number), CONSTRAINT fk_exam_candidates_exam_id_exams FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE RESTRICT, CONSTRAINT fk_exam_candidates_enrollment_id_student_enrollments FOREIGN KEY(enrollment_id) REFERENCES student_enrollments (id) ON DELETE RESTRICT, CONSTRAINT candidate_status CHECK (status IN ('eligible', 'blocked', 'withdrawn')) )",
'CREATE INDEX ix_exam_candidates_admission_number ON exam_candidates (admission_number)',
'CREATE INDEX ix_exam_candidates_enrollment_id ON exam_candidates (enrollment_id)',
'CREATE INDEX ix_exam_candidates_exam_id ON exam_candidates (exam_id)',
'CREATE INDEX ix_exam_candidates_status ON exam_candidates (status)',
'CREATE INDEX ix_exam_candidates_student_id ON exam_candidates (student_id)',
'CREATE TABLE exam_invigilators ( exam_id UUID NOT NULL, teacher_id UUID NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exam_invigilators PRIMARY KEY (id), CONSTRAINT uq_exam_invigilators_exam_teacher UNIQUE (exam_id, teacher_id), CONSTRAINT fk_exam_invigilators_exam_id_exams FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE CASCADE, CONSTRAINT fk_exam_invigilators_teacher_id_academic_teachers FOREIGN KEY(teacher_id) REFERENCES academic_teachers (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_exam_invigilators_exam_id ON exam_invigilators (exam_id)',
'CREATE INDEX ix_exam_invigilators_teacher_exam ON exam_invigilators (teacher_id, exam_id)',
'CREATE INDEX ix_exam_invigilators_teacher_id ON exam_invigilators (teacher_id)',
'CREATE TABLE exam_target_classes ( exam_id UUID NOT NULL, class_id UUID NOT NULL, subject_offering_id UUID, teacher_assignment_id UUID, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exam_target_classes PRIMARY KEY (id), CONSTRAINT uq_exam_target_classes_exam_class UNIQUE (exam_id, class_id), CONSTRAINT fk_exam_target_classes_exam_id_exams FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE CASCADE, CONSTRAINT fk_exam_target_classes_class_id_academic_classes FOREIGN KEY(class_id) REFERENCES academic_classes (id) ON DELETE RESTRICT, CONSTRAINT fk_exam_target_classes_subject_offering_id_subject_offerings FOREIGN KEY(subject_offering_id) REFERENCES subject_offerings (id) ON DELETE RESTRICT, CONSTRAINT fk_exam_target_classes_teacher_assignment_id_teacher_as_c830 FOREIGN KEY(teacher_assignment_id) REFERENCES teacher_assignments (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_exam_target_classes_assignment ON exam_target_classes (teacher_assignment_id)',
'CREATE INDEX ix_exam_target_classes_class_exam ON exam_target_classes (class_id, exam_id)',
'CREATE INDEX ix_exam_target_classes_class_id ON exam_target_classes (class_id)',
'CREATE INDEX ix_exam_target_classes_exam_id ON exam_target_classes (exam_id)',
'CREATE INDEX ix_exam_target_classes_offering ON exam_target_classes (subject_offering_id)',
'CREATE INDEX ix_exam_target_classes_subject_offering_id ON exam_target_classes (subject_offering_id)',
'CREATE INDEX ix_exam_target_classes_teacher_assignment_id ON exam_target_classes (teacher_assignment_id)',
"CREATE TABLE questions ( bank_id UUID NOT NULL, question_type VARCHAR(15) DEFAULT 'single_choice' NOT NULL, prompt TEXT NOT NULL, instruction TEXT, image_url VARCHAR(2048), version INTEGER DEFAULT 1 NOT NULL, created_by_actor_id UUID NOT NULL, last_edited_by_actor_id UUID, is_active BOOLEAN DEFAULT true NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_questions PRIMARY KEY (id), CONSTRAINT ck_questions_version_positive CHECK (version >= 1), CONSTRAINT fk_questions_bank_id_question_banks FOREIGN KEY(bank_id) REFERENCES question_banks (id) ON DELETE RESTRICT, CONSTRAINT question_type CHECK (question_type IN ('single_choice', 'multiple_choice')), CONSTRAINT fk_questions_created_by_actor_id_local_actors FOREIGN KEY(created_by_actor_id) REFERENCES local_actors (id) ON DELETE RESTRICT, CONSTRAINT fk_questions_last_edited_by_actor_id_local_actors FOREIGN KEY(last_edited_by_actor_id) REFERENCES local_actors (id) ON DELETE RESTRICT )",
'CREATE INDEX ix_questions_bank_active ON questions (bank_id, is_active)',
'CREATE INDEX ix_questions_bank_id ON questions (bank_id)',
'CREATE INDEX ix_questions_created_by_actor_id ON questions (created_by_actor_id)',
'CREATE INDEX ix_questions_last_edited_by_actor_id ON questions (last_edited_by_actor_id)',
'CREATE TABLE subject_offering_eligibilities ( offering_id UUID NOT NULL, enrollment_id UUID NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_subject_offering_eligibilities PRIMARY KEY (id), CONSTRAINT uq_subject_offering_eligibility UNIQUE (offering_id, enrollment_id), CONSTRAINT fk_subject_offering_eligibilities_offering_id_subject_offerings FOREIGN KEY(offering_id) REFERENCES subject_offerings (id) ON DELETE CASCADE, CONSTRAINT fk_subject_offering_eligibilities_enrollment_id_student_e775 FOREIGN KEY(enrollment_id) REFERENCES student_enrollments (id) ON DELETE CASCADE )',
'CREATE INDEX ix_subject_offering_eligibilities_enrollment ON subject_offering_eligibilities (enrollment_id, offering_id)',
'CREATE INDEX ix_subject_offering_eligibilities_enrollment_id ON subject_offering_eligibilities (enrollment_id)',
'CREATE INDEX ix_subject_offering_eligibilities_offering_id ON subject_offering_eligibilities (offering_id)',
"CREATE TABLE candidate_credentials ( candidate_id UUID NOT NULL, pin_hash VARCHAR(512) NOT NULL, credential_version INTEGER DEFAULT '1' NOT NULL, issued_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, revoked_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_candidate_credentials PRIMARY KEY (id), CONSTRAINT ck_candidate_credentials_version_positive CHECK (credential_version >= 1), CONSTRAINT ck_candidate_credentials_valid_revocation CHECK (revoked_at IS NULL OR revoked_at >= issued_at), CONSTRAINT fk_candidate_credentials_candidate_id_exam_candidates FOREIGN KEY(candidate_id) REFERENCES exam_candidates (id) ON DELETE CASCADE )",
'CREATE UNIQUE INDEX ix_candidate_credentials_candidate_id ON candidate_credentials (candidate_id)',
"CREATE TABLE exam_attempts ( candidate_id UUID NOT NULL, status VARCHAR(11) DEFAULT 'in_progress' NOT NULL, started_at TIMESTAMP WITH TIME ZONE NOT NULL, time_limit_seconds INTEGER NOT NULL, elapsed_seconds INTEGER DEFAULT 0 NOT NULL, active_since TIMESTAMP WITH TIME ZONE, last_heartbeat_at TIMESTAMP WITH TIME ZONE NOT NULL, last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL, submitted_at TIMESTAMP WITH TIME ZONE, submission_reason VARCHAR(19), termination_reason VARCHAR(500), created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exam_attempts PRIMARY KEY (id), CONSTRAINT ck_exam_attempts_time_limit_positive CHECK (time_limit_seconds > 0), CONSTRAINT ck_exam_attempts_elapsed_nonnegative CHECK (elapsed_seconds >= 0), CONSTRAINT ck_exam_attempts_elapsed_within_limit CHECK (elapsed_seconds <= time_limit_seconds), CONSTRAINT ck_exam_attempts_valid_active_since CHECK (active_since IS NULL OR active_since >= started_at), CONSTRAINT ck_exam_attempts_valid_heartbeat CHECK (last_heartbeat_at >= started_at), CONSTRAINT ck_exam_attempts_valid_activity CHECK (last_activity_at >= started_at), CONSTRAINT ck_exam_attempts_valid_submission CHECK (submitted_at IS NULL OR submitted_at >= started_at), CONSTRAINT ck_exam_attempts_active_segment_matches_status CHECK ((status = 'in_progress' AND active_since IS NOT NULL) OR (status <> 'in_progress' AND active_since IS NULL)), CONSTRAINT fk_exam_attempts_candidate_id_exam_candidates FOREIGN KEY(candidate_id) REFERENCES exam_candidates (id) ON DELETE RESTRICT, CONSTRAINT attempt_status CHECK (status IN ('in_progress', 'interrupted', 'submitted', 'terminated')), CONSTRAINT attempt_submission_reason CHECK (submission_reason IN ('candidate_submitted', 'time_expired', 'exam_closed', 'admin_terminated')) )",
'CREATE UNIQUE INDEX ix_exam_attempts_candidate_id ON exam_attempts (candidate_id)',
'CREATE INDEX ix_exam_attempts_last_heartbeat_at ON exam_attempts (last_heartbeat_at)',
'CREATE INDEX ix_exam_attempts_status ON exam_attempts (status)',
'CREATE INDEX ix_exam_attempts_status_heartbeat ON exam_attempts (status, last_heartbeat_at)',
"CREATE TABLE exam_questions ( exam_id UUID NOT NULL, source_question_id UUID NOT NULL, source_question_version INTEGER NOT NULL, question_type VARCHAR(15) NOT NULL, position INTEGER NOT NULL, prompt TEXT NOT NULL, instruction TEXT, image_url VARCHAR(2048), points NUMERIC(8, 2) NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exam_questions PRIMARY KEY (id), CONSTRAINT uq_exam_questions_exam_source_question UNIQUE (exam_id, source_question_id), CONSTRAINT uq_exam_questions_exam_position UNIQUE (exam_id, position), CONSTRAINT ck_exam_questions_source_version_positive CHECK (source_question_version >= 1), CONSTRAINT ck_exam_questions_position_positive CHECK (position >= 1), CONSTRAINT ck_exam_questions_points_positive CHECK (points > 0), CONSTRAINT fk_exam_questions_exam_id_exams FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE CASCADE, CONSTRAINT fk_exam_questions_source_question_id_questions FOREIGN KEY(source_question_id) REFERENCES questions (id) ON DELETE RESTRICT, CONSTRAINT exam_question_type CHECK (question_type IN ('single_choice', 'multiple_choice')) )",
'CREATE INDEX ix_exam_questions_exam_id ON exam_questions (exam_id)',
'CREATE INDEX ix_exam_questions_exam_position ON exam_questions (exam_id, position)',
'CREATE INDEX ix_exam_questions_source_question_id ON exam_questions (source_question_id)',
'CREATE TABLE question_options ( question_id UUID NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL, is_correct BOOLEAN DEFAULT false NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_question_options PRIMARY KEY (id), CONSTRAINT uq_question_options_question_position UNIQUE (question_id, position), CONSTRAINT ck_question_options_position_positive CHECK (position >= 1), CONSTRAINT fk_question_options_question_id_questions FOREIGN KEY(question_id) REFERENCES questions (id) ON DELETE CASCADE )',
'CREATE INDEX ix_question_options_question_id ON question_options (question_id)',
'CREATE INDEX ix_question_options_question_position ON question_options (question_id, position)',
'CREATE TABLE attempt_interruptions ( attempt_id UUID NOT NULL, interrupted_at TIMESTAMP WITH TIME ZONE NOT NULL, remaining_seconds INTEGER NOT NULL, reason VARCHAR(500), resumed_at TIMESTAMP WITH TIME ZONE, resumed_by_actor_id UUID, resume_reason VARCHAR(500), created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_attempt_interruptions PRIMARY KEY (id), CONSTRAINT ck_attempt_interruptions_remaining_nonnegative CHECK (remaining_seconds >= 0), CONSTRAINT ck_attempt_interruptions_valid_resume CHECK (resumed_at IS NULL OR resumed_at >= interrupted_at), CONSTRAINT fk_attempt_interruptions_attempt_id_exam_attempts FOREIGN KEY(attempt_id) REFERENCES exam_attempts (id) ON DELETE CASCADE, CONSTRAINT fk_attempt_interruptions_resumed_by_actor_id_local_actors FOREIGN KEY(resumed_by_actor_id) REFERENCES local_actors (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_attempt_interruptions_attempt_id ON attempt_interruptions (attempt_id)',
'CREATE INDEX ix_attempt_interruptions_attempt_interrupted ON attempt_interruptions (attempt_id, interrupted_at)',
'CREATE INDEX ix_attempt_interruptions_resumed_by_actor_id ON attempt_interruptions (resumed_by_actor_id)',
'CREATE TABLE attempt_question_allocations ( attempt_id UUID NOT NULL, exam_question_id UUID NOT NULL, position INTEGER NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_attempt_question_allocations PRIMARY KEY (id), CONSTRAINT uq_attempt_questions_attempt_exam_question UNIQUE (attempt_id, exam_question_id), CONSTRAINT uq_attempt_questions_attempt_position UNIQUE (attempt_id, position), CONSTRAINT ck_attempt_questions_position_positive CHECK (position >= 1), CONSTRAINT fk_attempt_question_allocations_attempt_id_exam_attempts FOREIGN KEY(attempt_id) REFERENCES exam_attempts (id) ON DELETE CASCADE, CONSTRAINT fk_attempt_question_allocations_exam_question_id_exam_questions FOREIGN KEY(exam_question_id) REFERENCES exam_questions (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_attempt_question_allocations_attempt_id ON attempt_question_allocations (attempt_id)',
'CREATE INDEX ix_attempt_question_allocations_exam_question_id ON attempt_question_allocations (exam_question_id)',
'CREATE INDEX ix_attempt_questions_attempt_position ON attempt_question_allocations (attempt_id, position)',
'CREATE TABLE exam_question_options ( exam_question_id UUID NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL, is_correct BOOLEAN DEFAULT false NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exam_question_options PRIMARY KEY (id), CONSTRAINT uq_exam_question_options_question_position UNIQUE (exam_question_id, position), CONSTRAINT ck_exam_question_options_position_positive CHECK (position >= 1), CONSTRAINT fk_exam_question_options_exam_question_id_exam_questions FOREIGN KEY(exam_question_id) REFERENCES exam_questions (id) ON DELETE CASCADE )',
'CREATE INDEX ix_exam_question_options_exam_question_id ON exam_question_options (exam_question_id)',
'CREATE INDEX ix_exam_question_options_question_position ON exam_question_options (exam_question_id, position)',
"CREATE TABLE exam_results ( attempt_id UUID NOT NULL, candidate_id UUID NOT NULL, exam_id UUID NOT NULL, assessment_component_id UUID NOT NULL, score NUMERIC(8, 2) NOT NULL, maximum_score NUMERIC(8, 2) NOT NULL, calculated_at TIMESTAMP WITH TIME ZONE NOT NULL, sync_status VARCHAR(7) DEFAULT 'pending' NOT NULL, idempotency_key VARCHAR(128) NOT NULL, weave_result_id VARCHAR(128), sync_attempts INTEGER DEFAULT 0 NOT NULL, last_sync_attempt_at TIMESTAMP WITH TIME ZONE, synced_at TIMESTAMP WITH TIME ZONE, sync_error TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_exam_results PRIMARY KEY (id), CONSTRAINT uq_exam_results_candidate_exam UNIQUE (candidate_id, exam_id), CONSTRAINT ck_exam_results_score_nonnegative CHECK (score >= 0), CONSTRAINT ck_exam_results_maximum_score_positive CHECK (maximum_score > 0), CONSTRAINT ck_exam_results_score_within_maximum CHECK (score <= maximum_score), CONSTRAINT ck_exam_results_sync_attempts_nonnegative CHECK (sync_attempts >= 0), CONSTRAINT ck_exam_results_sync_error_length CHECK (sync_error IS NULL OR char_length(sync_error) <= 1024), CONSTRAINT fk_exam_results_attempt_id_exam_attempts FOREIGN KEY(attempt_id) REFERENCES exam_attempts (id) ON DELETE RESTRICT, CONSTRAINT fk_exam_results_candidate_id_exam_candidates FOREIGN KEY(candidate_id) REFERENCES exam_candidates (id) ON DELETE RESTRICT, CONSTRAINT fk_exam_results_exam_id_exams FOREIGN KEY(exam_id) REFERENCES exams (id) ON DELETE RESTRICT, CONSTRAINT fk_exam_results_assessment_component_id_assessment_components FOREIGN KEY(assessment_component_id) REFERENCES assessment_components (id) ON DELETE RESTRICT, CONSTRAINT result_sync_status CHECK (sync_status IN ('pending', 'syncing', 'synced', 'failed')) )",
'CREATE INDEX ix_exam_results_assessment_component_id ON exam_results (assessment_component_id)',
'CREATE UNIQUE INDEX ix_exam_results_attempt_id ON exam_results (attempt_id)',
'CREATE INDEX ix_exam_results_candidate_id ON exam_results (candidate_id)',
'CREATE INDEX ix_exam_results_component_sync_status ON exam_results (assessment_component_id, sync_status)',
'CREATE INDEX ix_exam_results_exam_id ON exam_results (exam_id)',
'CREATE INDEX ix_exam_results_exam_sync_status ON exam_results (exam_id, sync_status)',
'CREATE UNIQUE INDEX ix_exam_results_idempotency_key ON exam_results (idempotency_key)',
'CREATE INDEX ix_exam_results_sync_status ON exam_results (sync_status)',
'CREATE UNIQUE INDEX ix_exam_results_weave_result_id ON exam_results (weave_result_id)',
'CREATE TABLE attempt_answers ( attempt_question_id UUID NOT NULL, is_flagged BOOLEAN DEFAULT false NOT NULL, answered_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_attempt_answers PRIMARY KEY (id), CONSTRAINT fk_attempt_answers_attempt_question_id_attempt_question_2940 FOREIGN KEY(attempt_question_id) REFERENCES attempt_question_allocations (id) ON DELETE CASCADE )',
'CREATE UNIQUE INDEX ix_attempt_answers_attempt_question_id ON attempt_answers (attempt_question_id)',
'CREATE TABLE attempt_option_allocations ( attempt_question_id UUID NOT NULL, exam_question_option_id UUID NOT NULL, position INTEGER NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_attempt_option_allocations PRIMARY KEY (id), CONSTRAINT uq_attempt_options_question_option UNIQUE (attempt_question_id, exam_question_option_id), CONSTRAINT uq_attempt_options_question_position UNIQUE (attempt_question_id, position), CONSTRAINT ck_attempt_options_position_positive CHECK (position >= 1), CONSTRAINT fk_attempt_option_allocations_attempt_question_id_attem_3686 FOREIGN KEY(attempt_question_id) REFERENCES attempt_question_allocations (id) ON DELETE CASCADE, CONSTRAINT fk_attempt_option_allocations_exam_question_option_id_e_ea38 FOREIGN KEY(exam_question_option_id) REFERENCES exam_question_options (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_attempt_option_allocations_attempt_question_id ON attempt_option_allocations (attempt_question_id)',
'CREATE INDEX ix_attempt_option_allocations_exam_question_option_id ON attempt_option_allocations (exam_question_option_id)',
'CREATE INDEX ix_attempt_options_question_position ON attempt_option_allocations (attempt_question_id, position)',
'CREATE TABLE attempt_answer_selections ( answer_id UUID NOT NULL, attempt_option_id UUID NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, id UUID NOT NULL, CONSTRAINT pk_attempt_answer_selections PRIMARY KEY (id), CONSTRAINT uq_attempt_answer_selections_answer_option UNIQUE (answer_id, attempt_option_id), CONSTRAINT fk_attempt_answer_selections_answer_id_attempt_answers FOREIGN KEY(answer_id) REFERENCES attempt_answers (id) ON DELETE CASCADE, CONSTRAINT fk_attempt_answer_selections_attempt_option_id_attempt__6f32 FOREIGN KEY(attempt_option_id) REFERENCES attempt_option_allocations (id) ON DELETE RESTRICT )',
'CREATE INDEX ix_attempt_answer_selections_answer ON attempt_answer_selections (answer_id)',
'CREATE INDEX ix_attempt_answer_selections_answer_id ON attempt_answer_selections (answer_id)',
'CREATE INDEX ix_attempt_answer_selections_attempt_option_id ON attempt_answer_selections (attempt_option_id)',
)


def upgrade() -> None:
    for statement in _UPGRADE_SQL:
        op.execute(sa.text(statement))


def downgrade() -> None:
    op.drop_table('attempt_answer_selections')
    op.drop_table('attempt_option_allocations')
    op.drop_table('attempt_answers')
    op.drop_table('exam_results')
    op.drop_table('exam_question_options')
    op.drop_table('attempt_question_allocations')
    op.drop_table('attempt_interruptions')
    op.drop_table('question_options')
    op.drop_table('exam_questions')
    op.drop_table('exam_attempts')
    op.drop_table('candidate_credentials')
    op.drop_table('subject_offering_eligibilities')
    op.drop_table('questions')
    op.drop_table('exam_target_classes')
    op.drop_table('exam_invigilators')
    op.drop_table('exam_candidates')
    op.drop_table('teacher_assignments')
    op.drop_table('subject_offerings')
    op.drop_table('question_banks')
    op.drop_table('exams')
    op.drop_table('student_enrollments')
    op.drop_table('local_refresh_tokens')
    op.drop_table('curriculum_subjects')
    op.drop_table('class_term_departments')
    op.drop_table('local_actor_sessions')
    op.drop_table('departments')
    op.drop_table('curricula')
    op.drop_table('assessment_components')
    op.drop_table('academic_terms')
    op.drop_table('academic_classes')
    op.drop_table('sync_states')
    op.drop_table('school_profiles')
    op.drop_table('local_actors')
    op.drop_table('audit_events')
    op.drop_table('assessment_schemes')
    op.drop_table('arm_labels')
    op.drop_table('academic_teachers')
    op.drop_table('academic_subjects')
    op.drop_table('academic_sessions')
    op.drop_table('academic_levels')
    op.drop_table('academic_admins')
