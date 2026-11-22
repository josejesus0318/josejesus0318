-- =============================================================================
-- Control de Acceso Campus ITVH  ·  01_esquema.sql
-- Tablas en 3FN dentro del esquema "campus".
-- Se puede volver a ejecutar: borra el esquema y lo crea de nuevo.
-- Compatible con PostgreSQL 15+ (Neon, Supabase, Render o local).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;          -- gen_random_bytes(), crypt()

DROP SCHEMA IF EXISTS campus CASCADE;
CREATE SCHEMA campus;
SET search_path TO campus, public;

-- -----------------------------------------------------------------------------
-- Configuración general (zona horaria del campus, intentos de NIP, etc.)
-- -----------------------------------------------------------------------------
CREATE TABLE configuracion (
    clave        VARCHAR(40) PRIMARY KEY,
    valor        TEXT        NOT NULL,
    descripcion  TEXT
);

-- -----------------------------------------------------------------------------
-- Catálogos
-- -----------------------------------------------------------------------------
CREATE TABLE tipos_persona (
    id_tipo      SMALLSERIAL PRIMARY KEY,
    clave        VARCHAR(3)  NOT NULL UNIQUE,        -- ALU, DOC, ADM, PRV, VIS
    nombre       VARCHAR(40) NOT NULL UNIQUE
);

CREATE TABLE carreras (
    id_carrera   SMALLSERIAL PRIMARY KEY,
    clave        VARCHAR(10)  NOT NULL UNIQUE,
    nombre       VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE departamentos (
    id_departamento SMALLSERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE empresas (
    id_empresa   SERIAL PRIMARY KEY,
    nombre       VARCHAR(120) NOT NULL UNIQUE,
    rfc          VARCHAR(13)  UNIQUE,
    telefono     VARCHAR(15),
    giro         VARCHAR(80)
);

-- -----------------------------------------------------------------------------
-- Horarios (nivel de acceso programado)
-- Un horario es un conjunto de franjas: día de la semana + hora de inicio y fin.
-- -----------------------------------------------------------------------------
CREATE TABLE horarios (
    id_horario   SERIAL PRIMARY KEY,
    nombre       VARCHAR(60) NOT NULL UNIQUE,
    descripcion  TEXT
);

CREATE TABLE horario_franjas (
    id_franja    SERIAL PRIMARY KEY,
    id_horario   INT      NOT NULL REFERENCES horarios(id_horario) ON DELETE CASCADE,
    dia_semana   SMALLINT NOT NULL,                  -- 1 = lunes … 7 = domingo (ISO)
    hora_inicio  TIME     NOT NULL,
    hora_fin     TIME     NOT NULL,
    CONSTRAINT ck_franja_dia   CHECK (dia_semana BETWEEN 1 AND 7),
    CONSTRAINT ck_franja_horas CHECK (hora_fin > hora_inicio),
    CONSTRAINT uq_franja UNIQUE (id_horario, dia_semana, hora_inicio)
);

-- -----------------------------------------------------------------------------
-- Puntos de acceso y perfiles (qué puertas puede usar cada perfil)
-- -----------------------------------------------------------------------------
CREATE TABLE puntos_acceso (
    id_punto     SMALLSERIAL PRIMARY KEY,
    nombre       VARCHAR(80)  NOT NULL UNIQUE,
    ubicacion    VARCHAR(120),
    sentido      VARCHAR(7)   NOT NULL DEFAULT 'ambos',
    perimetral   BOOLEAN      NOT NULL DEFAULT TRUE,  -- TRUE = entrada/salida del campus; FALSE = área interna
    activo       BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_punto_sentido CHECK (sentido IN ('entrada', 'salida', 'ambos'))
);

CREATE TABLE perfiles_acceso (
    id_perfil    SMALLSERIAL PRIMARY KEY,
    nombre       VARCHAR(60) NOT NULL UNIQUE,
    descripcion  TEXT,
    id_horario   INT REFERENCES horarios(id_horario) ON DELETE SET NULL   -- horario por omisión
);

CREATE TABLE perfil_puntos (
    id_perfil    SMALLINT NOT NULL REFERENCES perfiles_acceso(id_perfil) ON DELETE CASCADE,
    id_punto     SMALLINT NOT NULL REFERENCES puntos_acceso(id_punto)   ON DELETE CASCADE,
    PRIMARY KEY (id_perfil, id_punto)
);

-- -----------------------------------------------------------------------------
-- Personas: datos comunes + una tabla por tipo con sus datos propios
-- -----------------------------------------------------------------------------
CREATE TABLE personas (
    id_persona       SERIAL PRIMARY KEY,
    id_tipo          SMALLINT     NOT NULL REFERENCES tipos_persona(id_tipo),
    nombre           VARCHAR(60)  NOT NULL,
    apellido_paterno VARCHAR(40)  NOT NULL,
    apellido_materno VARCHAR(40),
    correo           VARCHAR(120),
    telefono         VARCHAR(15),
    identificacion   VARCHAR(40),                    -- INE, pasaporte… (visitantes/proveedores)
    activo           BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_alta       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_persona_correo CHECK (correo IS NULL OR correo ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);
CREATE INDEX ix_personas_nombre ON personas (lower(nombre || ' ' || apellido_paterno || ' ' || coalesce(apellido_materno, '')));

CREATE TABLE alumnos (
    id_persona      INT         PRIMARY KEY REFERENCES personas(id_persona) ON DELETE CASCADE,
    numero_control  VARCHAR(10) NOT NULL UNIQUE,
    id_carrera      SMALLINT    NOT NULL REFERENCES carreras(id_carrera),
    semestre        SMALLINT    NOT NULL,
    CONSTRAINT ck_alumno_semestre CHECK (semestre BETWEEN 1 AND 14)
);

CREATE TABLE empleados (                            -- docentes y personal administrativo
    id_persona      INT         PRIMARY KEY REFERENCES personas(id_persona) ON DELETE CASCADE,
    numero_empleado VARCHAR(10) NOT NULL UNIQUE,
    id_departamento SMALLINT    NOT NULL REFERENCES departamentos(id_departamento),
    puesto          VARCHAR(80) NOT NULL
);

CREATE TABLE proveedores (                          -- persona que acude en nombre de una empresa
    id_persona      INT PRIMARY KEY REFERENCES personas(id_persona) ON DELETE CASCADE,
    id_empresa      INT NOT NULL REFERENCES empresas(id_empresa)
);

-- -----------------------------------------------------------------------------
-- Eventos (para pases genéricos) y visitas programadas
-- -----------------------------------------------------------------------------
CREATE TABLE eventos (
    id_evento    SERIAL PRIMARY KEY,
    nombre       VARCHAR(120) NOT NULL,
    lugar        VARCHAR(120),
    inicio       TIMESTAMPTZ  NOT NULL,
    fin          TIMESTAMPTZ  NOT NULL,
    cupo         INT,
    CONSTRAINT ck_evento_fechas CHECK (fin > inicio),
    CONSTRAINT ck_evento_cupo   CHECK (cupo IS NULL OR cupo > 0)
);

CREATE TABLE visitas (
    id_visita        SERIAL PRIMARY KEY,
    id_persona       INT         NOT NULL REFERENCES personas(id_persona),    -- visitante o proveedor
    id_anfitrion     INT         REFERENCES empleados(id_persona),            -- a quién visita
    motivo           VARCHAR(200) NOT NULL,
    fecha            DATE        NOT NULL,
    estado           VARCHAR(10) NOT NULL DEFAULT 'programada',
    CONSTRAINT ck_visita_estado CHECK (estado IN ('programada', 'realizada', 'cancelada'))
);

-- -----------------------------------------------------------------------------
-- Usuarios de la aplicación web (contraseña cifrada con bcrypt por pgcrypto)
-- -----------------------------------------------------------------------------
CREATE TABLE usuarios (
    id_usuario     SERIAL PRIMARY KEY,
    usuario        VARCHAR(30)  NOT NULL UNIQUE,
    password_hash  TEXT         NOT NULL,
    nombre         VARCHAR(100) NOT NULL,
    rol            VARCHAR(10)  NOT NULL,
    activo         BOOLEAN      NOT NULL DEFAULT TRUE,
    ultimo_acceso  TIMESTAMPTZ,
    CONSTRAINT ck_usuario_rol    CHECK (rol IN ('admin', 'vigilancia', 'recepcion', 'consulta')),
    CONSTRAINT ck_usuario_nombre CHECK (usuario ~ '^[a-z0-9_.]{3,30}$')
);

-- -----------------------------------------------------------------------------
-- Credenciales: QR personal o genérico, con vigencia, horario y número de usos
-- -----------------------------------------------------------------------------
CREATE TABLE credenciales (
    id_credencial    SERIAL PRIMARY KEY,
    token            VARCHAR(40)  NOT NULL UNIQUE
                     DEFAULT 'ITVH-' || upper(encode(gen_random_bytes(12), 'hex')),  -- contenido del QR
    tipo             VARCHAR(8)   NOT NULL,          -- personal | generica
    id_persona       INT          REFERENCES personas(id_persona),
    descripcion      VARCHAR(120),                   -- obligatoria en las genéricas
    id_perfil        SMALLINT     NOT NULL REFERENCES perfiles_acceso(id_perfil),
    id_horario       INT          REFERENCES horarios(id_horario) ON DELETE SET NULL,  -- sustituye al del perfil
    id_evento        INT          REFERENCES eventos(id_evento) ON DELETE CASCADE,
    id_visita        INT          REFERENCES visitas(id_visita) ON DELETE CASCADE,
    nip_hash         TEXT,                           -- NIP para entrar sin QR (solo personales)
    vigencia_inicio  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    vigencia_fin     TIMESTAMPTZ,                    -- NULL = sin caducidad
    usos_maximos     INT,                            -- NULL = ilimitado; 1 = un solo uso
    usos_realizados  INT          NOT NULL DEFAULT 0,
    activa           BOOLEAN      NOT NULL DEFAULT TRUE,
    creada_por       INT          REFERENCES usuarios(id_usuario),
    creada_en        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_cred_tipo      CHECK (tipo IN ('personal', 'generica')),
    CONSTRAINT ck_cred_titular   CHECK (
        (tipo = 'personal' AND id_persona IS NOT NULL) OR
        (tipo = 'generica' AND id_persona IS NULL AND descripcion IS NOT NULL)),
    CONSTRAINT ck_cred_nip       CHECK (nip_hash IS NULL OR tipo = 'personal'),
    CONSTRAINT ck_cred_vigencia  CHECK (vigencia_fin IS NULL OR vigencia_fin > vigencia_inicio),
    CONSTRAINT ck_cred_usos      CHECK (usos_maximos IS NULL OR usos_maximos > 0),
    CONSTRAINT ck_cred_consumo   CHECK (usos_realizados >= 0 AND
                                        (usos_maximos IS NULL OR usos_realizados <= usos_maximos))
);
CREATE INDEX ix_credenciales_persona ON credenciales (id_persona);
CREATE INDEX ix_credenciales_evento  ON credenciales (id_evento);

-- -----------------------------------------------------------------------------
-- Bitácora de accesos: entradas, salidas e intentos denegados (no se modifica)
-- -----------------------------------------------------------------------------
CREATE TABLE registro_accesos (
    id_registro    BIGSERIAL PRIMARY KEY,
    fecha_hora     TIMESTAMPTZ NOT NULL DEFAULT now(),
    id_punto       SMALLINT    NOT NULL REFERENCES puntos_acceso(id_punto),
    id_credencial  INT         REFERENCES credenciales(id_credencial),
    id_persona     INT         REFERENCES personas(id_persona),
    metodo         VARCHAR(6)  NOT NULL,             -- qr | nip | manual
    evento         VARCHAR(7),                       -- entrada | salida (NULL si se negó)
    resultado      VARCHAR(9)  NOT NULL,             -- permitido | denegado
    motivo         VARCHAR(120),
    dato_leido     VARCHAR(60),                      -- lo que se leyó cuando no coincide nada
    id_usuario     INT         REFERENCES usuarios(id_usuario),   -- quién operó la caseta
    CONSTRAINT ck_reg_metodo    CHECK (metodo IN ('qr', 'nip', 'manual')),
    CONSTRAINT ck_reg_evento    CHECK (evento IS NULL OR evento IN ('entrada', 'salida')),
    CONSTRAINT ck_reg_resultado CHECK (resultado IN ('permitido', 'denegado')),
    CONSTRAINT ck_reg_permitido CHECK (resultado = 'denegado' OR evento IS NOT NULL)
);
CREATE INDEX ix_registro_fecha       ON registro_accesos (fecha_hora DESC);
CREATE INDEX ix_registro_persona     ON registro_accesos (id_persona, fecha_hora DESC);
CREATE INDEX ix_registro_credencial  ON registro_accesos (id_credencial, fecha_hora DESC);

-- -----------------------------------------------------------------------------
-- Auditoría de cambios importantes (activar/desactivar, altas, bajas)
-- -----------------------------------------------------------------------------
CREATE TABLE auditoria (
    id_auditoria   BIGSERIAL PRIMARY KEY,
    fecha_hora     TIMESTAMPTZ NOT NULL DEFAULT now(),
    id_usuario     INT REFERENCES usuarios(id_usuario),
    accion         VARCHAR(40) NOT NULL,
    tabla          VARCHAR(40) NOT NULL,
    id_afectado    INT,
    detalle        TEXT
);
CREATE INDEX ix_auditoria_fecha ON auditoria (fecha_hora DESC);

-- -----------------------------------------------------------------------------
-- Valores por omisión de la base de datos: así funciona también a través del
-- "connection pooler" de Neon, que no conserva los SET de cada conexión.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET search_path = campus, public', current_database());
    EXECUTE format('ALTER DATABASE %I SET timezone = %L', current_database(), 'America/Mexico_City');
END $$;
