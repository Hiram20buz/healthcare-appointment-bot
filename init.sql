DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS service_recommendations CASCADE;
DROP TABLE IF EXISTS post_consultation_instructions CASCADE;
DROP TABLE IF EXISTS services CASCADE;
DROP TABLE IF EXISTS patients CASCADE;

-- ======================================================
-- TABLE: patients
-- ======================================================

CREATE TABLE patients (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    birth_date DATE NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(20) NOT NULL
        CHECK (gender IN ('Male', 'Female', 'Other')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_patients_gender ON patients(gender);
CREATE INDEX idx_patients_age ON patients(age);

-- ======================================================
-- TABLE: services
-- ======================================================

CREATE TABLE services (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    duration_minutes INT NOT NULL,
    modality VARCHAR(20) NOT NULL
        CHECK (modality IN ('Onsite', 'Virtual')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ======================================================
-- TABLE: service_recommendations
-- ======================================================

CREATE TABLE service_recommendations (
    id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    display_order INT DEFAULT 1,
    FOREIGN KEY (service_id)
        REFERENCES services(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_service_recommendations_service
ON service_recommendations(service_id);

-- ======================================================
-- TABLE: post_consultation_instructions
-- ======================================================

CREATE TABLE post_consultation_instructions (
    id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    FOREIGN KEY (service_id)
        REFERENCES services(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_post_consultation_service
ON post_consultation_instructions(service_id);

-- ======================================================
-- TABLE: appointments
-- ======================================================

CREATE TABLE appointments (
    id BIGSERIAL PRIMARY KEY,
    patient_id BIGINT NOT NULL,
    service_id BIGINT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status VARCHAR(20) DEFAULT 'Pending'
        CHECK (status IN (
            'Pending',
            'Confirmed',
            'Cancelled',
            'Rescheduled',
            'No_Show'
        )),
    reason TEXT NOT NULL,
    reschedule_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)
        REFERENCES patients(id)
        ON DELETE CASCADE,
    FOREIGN KEY (service_id)
        REFERENCES services(id)
        ON DELETE RESTRICT,
    CONSTRAINT unique_appointment_slot
        UNIQUE (appointment_date, appointment_time)
);

CREATE INDEX idx_appointments_date
ON appointments(appointment_date);

CREATE INDEX idx_appointments_status
ON appointments(status);

CREATE INDEX idx_appointments_patient
ON appointments(patient_id);