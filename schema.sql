-- =====================================================================
-- ESQUEMA POSTGRES — Evaluación Integral de Admisión a Rehabilitación
-- Centro de rehabilitación · Estudio de sobrevida (cruce por DNI)
-- Compatible con Supabase / Postgres 14+
-- Autor de referencia: Ismael Calandri
-- =====================================================================
-- Convenciones:
--   * snake_case en español
--   * 1 paciente (DNI único) -> N admisiones (evaluaciones en el tiempo)
--   * Campos de opción cerrada -> tipos ENUM
--   * Secciones repetidas -> tablas hijas
--   * Catálogos (cat_*) -> precargan las filas fijas del formulario
--   * Campos "Observaciones/Detalle" libres -> text
-- =====================================================================

-- Reproducibilidad: borrar y recrear (CUIDADO en producción)
-- DROP SCHEMA IF EXISTS rehab CASCADE;
CREATE SCHEMA IF NOT EXISTS rehab;
SET search_path TO rehab, public;

-- ---------------------------------------------------------------------
-- 0. TIPOS ENUM (opciones cerradas del formulario)
-- ---------------------------------------------------------------------
CREATE TYPE modalidad_entrevista  AS ENUM ('presencial','telefonica','videollamada');
CREATE TYPE tipo_informante       AS ENUM ('paciente_solo','con_acompanante','solo_acompanante');
CREATE TYPE tipo_residencia       AS ENUM ('domicilio_propio','familiar','geriatrico','otro');
CREATE TYPE disponibilidad_cuid   AS ENUM ('permanente','parcial','ninguna');
CREATE TYPE nivel_actividad_fisica AS ENUM ('sedentario','leve','moderada','intensa');
CREATE TYPE nivel_independencia   AS ENUM ('independiente','asistido','dependiente');
CREATE TYPE deambulacion_tipo     AS ENUM ('independiente','no','con_ayuda_tecnica');
CREATE TYPE escaleras_tipo        AS ENUM ('si','no','con_ayuda');
CREATE TYPE si_no_nosabe          AS ENUM ('si','no','no_sabe');
CREATE TYPE orientacion_tipo      AS ENUM ('conservada','parcial','ausente');
CREATE TYPE audicion_tipo         AS ENUM ('normal','hipoacusia_con_audifono','hipoacusia_sin_compensar');
CREATE TYPE vision_tipo           AS ENUM ('normal','reducida_compensada','reducida_sin_compensar');
CREATE TYPE estado_problema       AS ENUM ('estable','seguimiento','descompensado');
CREATE TYPE tipo_alergia          AS ENUM ('medicamentosa','alimentaria','otras');
CREATE TYPE anticoag_tipo         AS ENUM ('avk','naco');           -- AVK=warfarina/acenocumarol
CREATE TYPE insulina_esquema      AS ENUM ('basal','basal_bolo','bomba');
CREATE TYPE rol_usuario           AS ENUM ('admin','cargador','lector');

-- ---------------------------------------------------------------------
-- 1. USUARIOS (login del formulario — control de acceso)
-- ---------------------------------------------------------------------
CREATE TABLE usuarios (
    id              bigserial PRIMARY KEY,
    usuario         text NOT NULL UNIQUE,
    nombre          text NOT NULL,
    password_hash   text NOT NULL,          -- bcrypt/argon2; NUNCA texto plano
    rol             rol_usuario NOT NULL DEFAULT 'cargador',
    activo          boolean NOT NULL DEFAULT true,
    creado_en       timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2. PACIENTES (maestro — clave del estudio de sobrevida)
--    El DNI es el identificador de cruce. Único.
-- ---------------------------------------------------------------------
CREATE TABLE pacientes (
    id                bigserial PRIMARY KEY,
    dni               text NOT NULL UNIQUE,
    apellido_nombre   text NOT NULL,
    fecha_nacimiento  date,                 -- opcional; útil para sobrevida
    sexo              text,                  -- libre; no figura en el form, opcional
    creado_en         timestamptz NOT NULL DEFAULT now(),
    actualizado_en    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dni_no_vacio CHECK (length(trim(dni)) > 0)
);
CREATE INDEX idx_pacientes_dni ON pacientes (dni);

-- ---------------------------------------------------------------------
-- 3. ADMISIONES (1 evaluación de admisión = 1 fila)
--    Contiene todos los campos de valor único de los 7 módulos.
-- ---------------------------------------------------------------------
CREATE TABLE admisiones (
    id                      bigserial PRIMARY KEY,
    paciente_id             bigint NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,

    -- ---- MÓDULO 0 · Datos de la entrevista (tabla cabecera) ----
    fecha_entrevista        date,
    profesional             text,
    modalidad               modalidad_entrevista,
    informante              tipo_informante,
    relacion_acompanante    text,

    -- ---- MÓDULO 1.1 · Datos personales ----
    edad                    smallint CHECK (edad >= 0 AND edad <= 130),
    residencia              tipo_residencia,
    residencia_otro         text,           -- detalle si residencia='otro'

    -- ---- MÓDULO 1.2 · Red de soporte ----
    vive_solo               boolean,
    cuidador_nombre         text,
    cuidador_vinculo        text,
    cuidador_disponibilidad disponibilidad_cuid,
    cuidador_formal         boolean,        -- servicio formal domiciliario

    -- ---- MÓDULO 1.3 · Nivel educativo y actividad previa ----
    anios_escolaridad       smallint CHECK (anios_escolaridad >= 0),
    actividad_laboral_previa text,
    actividad_fisica        nivel_actividad_fisica,

    -- ---- MÓDULO 3 · Cribado farmacológico adicional ----
    anticoagulado           boolean,
    anticoag_tipo           anticoag_tipo,
    anticoag_control_rin    boolean,
    toma_insulina           boolean,
    insulina_esquema        insulina_esquema,
    corticoides_cronicos    boolean,
    corticoides_detalle     text,           -- dosis y duración
    medicacion_memoria_conducta boolean,    -- anticolinesterásicos/memantina/antipsicóticos
    dificultad_autoadministracion text,     -- ¿maneja su medicación de forma autónoma?

    -- ---- MÓDULO 4.1 · Motivo principal de rehabilitación ----
    motivo_descripcion      text,
    motivo_fecha_inicio     text,           -- fecha o evento desencadenante (libre)
    motivo_internacion_previa boolean,

    -- ---- MÓDULO 4.3 · Hospitalizaciones últimos 12 meses ----
    hosp_12m_numero         smallint,
    hosp_12m_motivos        text,
    hosp_12m_uci            boolean,
    hosp_12m_uci_duracion   text,

    -- ---- MÓDULO 4.4 · Consultas a guardia últimos 3 meses ----
    guardia_3m_numero       smallint,
    guardia_3m_motivos      text,

    -- ---- MÓDULO 5.1 · Movilidad ----
    deambulacion            deambulacion_tipo,
    ayuda_tecnica           text[],         -- {baston, andador, silla_ruedas}
    sube_escaleras          escaleras_tipo,
    distancia_marcha        text,           -- ej. "50 mtrs"

    -- ---- MÓDULO 5.2 · Barthel referido — independencia PREVIA al evento ----
    avd_alimentacion        nivel_independencia,
    avd_higiene             nivel_independencia,
    avd_vestido             nivel_independencia,
    avd_continencia         nivel_independencia,
    avd_traslados           nivel_independencia,
    avd_observaciones       text,           -- matices (ej. continencia urinaria ocasional)

    -- ---- MÓDULO 5.3 · Cognición basal ----
    olvidos_previos         si_no_nosabe,
    dx_cognitivo_previo     boolean,
    dx_cognitivo_cual       text,
    mmse_puntaje            smallint CHECK (mmse_puntaje >= 0 AND mmse_puntaje <= 30),
    orientacion_basal       orientacion_tipo,

    -- ---- MÓDULO 5.4 · Comunicación y sensopercepción ----
    idioma_principal        text,
    dificultad_comunicacion boolean,
    dificultad_comunicacion_detalle text,
    audicion                audicion_tipo,
    vision                  vision_tipo,

    -- ---- MÓDULO 7 · Cierre y observaciones ----
    observaciones           text,

    -- ---- Metadatos ----
    creado_por              bigint REFERENCES usuarios(id),
    creado_en               timestamptz NOT NULL DEFAULT now(),
    actualizado_en          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_admisiones_paciente ON admisiones (paciente_id);
CREATE INDEX idx_admisiones_fecha    ON admisiones (fecha_entrevista);

-- ---------------------------------------------------------------------
-- 4. CATÁLOGOS (filas fijas del formulario; alimentan los desplegables)
-- ---------------------------------------------------------------------

-- 4.a Catálogo de antecedentes (Módulo 2) — categoría + ítem
CREATE TABLE cat_antecedentes (
    id          bigserial PRIMARY KEY,
    categoria   text NOT NULL,      -- ej. 'Neurológicos'
    item        text NOT NULL,      -- ej. 'ACV / AIT'
    alta_prioridad boolean NOT NULL DEFAULT false,
    orden       smallint NOT NULL,
    UNIQUE (categoria, item)
);

-- 4.b Catálogo de factores de riesgo (Módulo 6) — lista fija de 10
CREATE TABLE cat_factores_riesgo (
    id          bigserial PRIMARY KEY,
    factor      text NOT NULL UNIQUE,
    orden       smallint NOT NULL
);

-- ---------------------------------------------------------------------
-- 5. TABLAS HIJAS (secciones repetidas, FK a admisiones)
-- ---------------------------------------------------------------------

-- 5.1 MÓDULO 2 · Antecedentes médicos (un registro por ítem marcado)
CREATE TABLE adm_antecedentes (
    id                bigserial PRIMARY KEY,
    admision_id       bigint NOT NULL REFERENCES admisiones(id) ON DELETE CASCADE,
    cat_antecedente_id bigint REFERENCES cat_antecedentes(id),
    categoria         text,           -- denormalizado para consulta rápida
    item              text,
    presente          boolean NOT NULL DEFAULT true,
    detalle           text,           -- campos inline: fecha, territorio, secuelas, tipo, etc.
    observaciones     text
);
CREATE INDEX idx_antec_admision ON adm_antecedentes (admision_id);

-- 5.2 MÓDULO 2.10 · Cirugías relevantes
CREATE TABLE adm_cirugias (
    id            bigserial PRIMARY KEY,
    admision_id   bigint NOT NULL REFERENCES admisiones(id) ON DELETE CASCADE,
    orden         smallint,
    tipo_cirugia  text,
    fecha_aprox   text
);
CREATE INDEX idx_cirugias_admision ON adm_cirugias (admision_id);

-- 5.3 MÓDULO 2.11 · Alergias e intolerancias
CREATE TABLE adm_alergias (
    id            bigserial PRIMARY KEY,
    admision_id   bigint NOT NULL REFERENCES admisiones(id) ON DELETE CASCADE,
    tipo          tipo_alergia NOT NULL,
    descripcion   text          -- agente + tipo de reacción
);
CREATE INDEX idx_alergias_admision ON adm_alergias (admision_id);

-- 5.4 MÓDULO 3 · Medicación habitual (incluye automedicación y suplementos)
CREATE TABLE adm_medicacion (
    id            bigserial PRIMARY KEY,
    admision_id   bigint NOT NULL REFERENCES admisiones(id) ON DELETE CASCADE,
    orden         smallint,
    medicamento   text,          -- nombre genérico
    dosis         text,
    frecuencia    text,
    via           text,
    prescriptor   text,
    indicacion    text
);
CREATE INDEX idx_medicacion_admision ON adm_medicacion (admision_id);

-- 5.5 MÓDULO 4.2 · Problemas de salud activos secundarios
CREATE TABLE adm_problemas_activos (
    id                bigserial PRIMARY KEY,
    admision_id       bigint NOT NULL REFERENCES admisiones(id) ON DELETE CASCADE,
    problema          text,
    descripcion       text,        -- descripción / evolución
    estado            estado_problema,
    medico_responsable text
);
CREATE INDEX idx_problemas_admision ON adm_problemas_activos (admision_id);

-- 5.6 MÓDULO 6 · Factores de riesgo para la rehabilitación (banderas rojas)
CREATE TABLE adm_factores_riesgo (
    id                  bigserial PRIMARY KEY,
    admision_id         bigint NOT NULL REFERENCES admisiones(id) ON DELETE CASCADE,
    cat_factor_id       bigint REFERENCES cat_factores_riesgo(id),
    factor              text,       -- denormalizado
    presente            boolean NOT NULL DEFAULT false,
    detalle             text
);
CREATE INDEX idx_factores_admision ON adm_factores_riesgo (admision_id);

-- ---------------------------------------------------------------------
-- 6. TRIGGER · actualizar 'actualizado_en' automáticamente
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_actualizado_en()
RETURNS trigger AS $$
BEGIN
    NEW.actualizado_en = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pacientes_upd  BEFORE UPDATE ON pacientes
    FOR EACH ROW EXECUTE FUNCTION set_actualizado_en();
CREATE TRIGGER trg_admisiones_upd BEFORE UPDATE ON admisiones
    FOR EACH ROW EXECUTE FUNCTION set_actualizado_en();

-- ---------------------------------------------------------------------
-- 7. VISTA PLANA (1 fila por admisión) — cómoda para análisis en R/Python
--    Las secciones repetidas se agregan como conteos/listas.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_admisiones_plano AS
SELECT
    a.*,
    p.dni,
    p.apellido_nombre,
    p.fecha_nacimiento,
    (SELECT count(*) FROM adm_medicacion m       WHERE m.admision_id = a.id) AS n_medicamentos,
    (SELECT count(*) FROM adm_antecedentes an    WHERE an.admision_id = a.id AND an.presente) AS n_antecedentes,
    (SELECT count(*) FROM adm_problemas_activos pr WHERE pr.admision_id = a.id) AS n_problemas_activos,
    (SELECT count(*) FROM adm_factores_riesgo fr WHERE fr.admision_id = a.id AND fr.presente) AS n_factores_riesgo
FROM admisiones a
JOIN pacientes p ON p.id = a.paciente_id;

-- =====================================================================
-- 8. SEED · Catálogos (precargados desde el formulario)
-- =====================================================================

-- 8.a Antecedentes (Módulo 2)
INSERT INTO cat_antecedentes (categoria, item, alta_prioridad, orden) VALUES
('Neurológicos','ACV / AIT', true, 1),
('Neurológicos','Enfermedad de Parkinson u otro trastorno del movimiento', true, 2),
('Neurológicos','Demencia / deterioro cognitivo', true, 3),
('Neurológicos','Epilepsia', true, 4),
('Neurológicos','Neuropatía periférica', true, 5),
('Neurológicos','TCE previo', true, 6),
('Neurológicos','Otro (neurológico)', true, 7),
('Cardiovasculares','Cardiopatía isquémica (IAM, angina)', false, 8),
('Cardiovasculares','Insuficiencia cardíaca', false, 9),
('Cardiovasculares','Fibrilación auricular', false, 10),
('Cardiovasculares','Hipertensión arterial', false, 11),
('Cardiovasculares','Arritmia relevante', false, 12),
('Cardiovasculares','Portador de marcapasos / CDI / stent coronario', false, 13),
('Metabólicos y endocrinos','Diabetes mellitus', false, 14),
('Metabólicos y endocrinos','Dislipemia', false, 15),
('Metabólicos y endocrinos','Hipotiroidismo / Hipertiroidismo', false, 16),
('Metabólicos y endocrinos','Obesidad', false, 17),
('Respiratorios','EPOC', false, 18),
('Respiratorios','Asma', false, 19),
('Respiratorios','SAHOS', false, 20),
('Respiratorios','Insuficiencia respiratoria crónica', false, 21),
('Osteoarticular','Osteoporosis', false, 22),
('Osteoarticular','Artrosis', false, 23),
('Osteoarticular','Artritis reumatoidea u otra enfermedad autoinmune', false, 24),
('Osteoarticular','Amputación', false, 25),
('Osteoarticular','Fracturas previas', false, 26),
('Genitourinario','Insuficiencia renal crónica', false, 27),
('Genitourinario','Incontinencia urinaria', false, 28),
('Genitourinario','Incontinencia fecal', false, 29),
('Genitourinario','Catéter urinario', false, 30),
('Digestivo / Deglución','Disfagia', false, 31),
('Digestivo / Deglución','Gastrostomía', false, 32),
('Digestivo / Deglución','Hepatopatía crónica', false, 33),
('Oncológico','Neoplasia activa', false, 34),
('Oncológico','Antecedente oncológico resuelto', false, 35),
('Psiquiátrico y conductual','Depresión', false, 36),
('Psiquiátrico y conductual','Trastorno de ansiedad', false, 37),
('Psiquiátrico y conductual','Psicosis / Esquizofrenia', false, 38),
('Psiquiátrico y conductual','Trastorno de conducta en contexto de demencia', false, 39),
('Psiquiátrico y conductual','Abuso de alcohol u otras sustancias', false, 40);

-- 8.b Factores de riesgo (Módulo 6)
INSERT INTO cat_factores_riesgo (factor, orden) VALUES
('Úlceras por presión activas', 1),
('Dolor crónico severo (EVA > 7)', 2),
('Pérdida de peso > 5% en 3 meses o desnutrición', 3),
('Caídas en los últimos 6 meses', 4),
('Síndrome confusional reciente', 5),
('Insomnio severo', 6),
('Riesgo de aspiración', 7),
('Dispositivos invasivos activos', 8),
('Úlceras vasculares o heridas activas', 9),
('Rigidez severa / espasticidad', 10);

-- =====================================================================
-- FIN DEL ESQUEMA
-- =====================================================================
                                                                                                   