/* =====================================================================
   MODELO v2 – ESQUEMA (18 tablas en 3FN)
   Proyecto : Sistema de Control de Acceso con Códigos QR – Grupo Solutions
   Materia  : Taller de Bases de Datos – ITVH (Equipo 6 Magenta)
   SGBD     : PostgreSQL 18 (compatible con 15 o superior)

   Cambios respecto al modelo v1 (9 tablas):
   - ubicaciones: la ubicación física deja de repetirse como texto en
     departamentos y puntos de acceso.
   - dias_semana + horario_dias: los días de cada turno quedan en una
     relación N:M en lugar de un texto 'Lunes a Viernes'.
   - empresas y tipos_identificacion: catálogos que antes eran texto libre.
   - visitantes + visitas: la persona se registra una sola vez y cada
     regreso es una visita nueva (elimina la redundancia del v1).
   - estados_credencial: catálogo en lugar de un CHECK de texto.
   - permisos_rol_punto: qué rol de acceso puede pasar por qué punto.
   - usuarios_sistema: liga cada cuenta de PostgreSQL con un colaborador.
   - registro_accesos ahora guarda también los intentos DENEGADOS.
   ===================================================================== */

DROP TABLE IF EXISTS registro_accesos, usuarios_sistema, credenciales, estados_credencial,
                     permisos_rol_punto, puntos_acceso, roles_acceso, visitas, visitantes,
                     colaboradores, empresas, tipos_identificacion, horario_dias,
                     horarios_laborales, dias_semana, puestos, departamentos, ubicaciones CASCADE;

-- ---------------------------------------------------------------------
-- 1. CATÁLOGOS DE ESTRUCTURA ORGANIZACIONAL
-- ---------------------------------------------------------------------

-- Lugares físicos del edificio (piso, ala, área)
CREATE TABLE ubicaciones (
    id_ubicacion SERIAL PRIMARY KEY,
    nombre       VARCHAR(80)  NOT NULL UNIQUE,
    piso         SMALLINT     NOT NULL CONSTRAINT ck_ubicacion_piso CHECK (piso BETWEEN -5 AND 50),
    descripcion  VARCHAR(200)
);

-- Áreas de la empresa
CREATE TABLE departamentos (
    id_departamento SERIAL PRIMARY KEY,
    nombre          VARCHAR(60) NOT NULL UNIQUE,
    id_ubicacion    INT NOT NULL REFERENCES ubicaciones(id_ubicacion)
);

-- Puestos de trabajo, cada uno dentro de un departamento
CREATE TABLE puestos (
    id_puesto       SERIAL PRIMARY KEY,
    nombre          VARCHAR(80) NOT NULL,
    id_departamento INT NOT NULL REFERENCES departamentos(id_departamento),
    CONSTRAINT uq_puesto_departamento UNIQUE (nombre, id_departamento)
);

-- ---------------------------------------------------------------------
-- 2. HORARIOS
-- ---------------------------------------------------------------------

-- Días de la semana (1 = lunes ... 7 = domingo, ISO 8601)
CREATE TABLE dias_semana (
    id_dia      SMALLINT PRIMARY KEY CONSTRAINT ck_dia_rango CHECK (id_dia BETWEEN 1 AND 7),
    nombre      VARCHAR(10) NOT NULL UNIQUE,
    abreviatura CHAR(3)     NOT NULL UNIQUE
);

-- Turnos del personal
CREATE TABLE horarios_laborales (
    id_horario   SERIAL PRIMARY KEY,
    nombre_turno VARCHAR(40) NOT NULL UNIQUE,
    hora_entrada TIME NOT NULL,
    hora_salida  TIME NOT NULL,
    CONSTRAINT ck_horario_horas CHECK (hora_salida > hora_entrada)
);

-- Días en que aplica cada turno (N:M)
CREATE TABLE horario_dias (
    id_horario INT      NOT NULL REFERENCES horarios_laborales(id_horario) ON DELETE CASCADE,
    id_dia     SMALLINT NOT NULL REFERENCES dias_semana(id_dia),
    PRIMARY KEY (id_horario, id_dia)
);

-- ---------------------------------------------------------------------
-- 3. PERSONAS
-- ---------------------------------------------------------------------

-- Tipos de documento con que se identifican los visitantes
CREATE TABLE tipos_identificacion (
    id_tipo_identificacion SERIAL PRIMARY KEY,
    clave                  VARCHAR(5)  NOT NULL UNIQUE,
    nombre                 VARCHAR(60) NOT NULL UNIQUE
);

-- Empresas de procedencia de los visitantes
CREATE TABLE empresas (
    id_empresa SERIAL PRIMARY KEY,
    nombre     VARCHAR(100) NOT NULL UNIQUE,
    rfc        VARCHAR(13)  UNIQUE,
    telefono   VARCHAR(15)
);

-- Personal interno: empleados y contratistas (baja lógica)
CREATE TABLE colaboradores (
    id_colaborador   SERIAL PRIMARY KEY,
    numero_empleado  VARCHAR(15)  NOT NULL UNIQUE,
    nombre           VARCHAR(60)  NOT NULL,
    apellido_paterno VARCHAR(60)  NOT NULL,
    apellido_materno VARCHAR(60),
    tipo_colaborador VARCHAR(15)  NOT NULL
                     CONSTRAINT ck_colab_tipo CHECK (tipo_colaborador IN ('empleado', 'contratista')),
    id_puesto        INT NOT NULL REFERENCES puestos(id_puesto),
    id_horario       INT NOT NULL REFERENCES horarios_laborales(id_horario),
    telefono         VARCHAR(15)  NOT NULL,
    correo           VARCHAR(100) NOT NULL UNIQUE
                     CONSTRAINT ck_colab_correo CHECK (correo ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
    fecha_ingreso    DATE NOT NULL,
    activo           BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_baja       DATE,
    CONSTRAINT ck_colab_fecha_baja CHECK (fecha_baja IS NULL OR fecha_baja >= fecha_ingreso),
    CONSTRAINT ck_colab_baja_con_fecha CHECK (activo OR fecha_baja IS NOT NULL)   -- toda baja lleva fecha
);

-- Personas externas (se registran una sola vez)
CREATE TABLE visitantes (
    id_visitante           SERIAL PRIMARY KEY,
    nombre                 VARCHAR(60) NOT NULL,
    apellido_paterno       VARCHAR(60) NOT NULL,
    apellido_materno       VARCHAR(60),
    id_tipo_identificacion INT NOT NULL REFERENCES tipos_identificacion(id_tipo_identificacion),
    numero_identificacion  VARCHAR(25) NOT NULL,
    id_empresa             INT REFERENCES empresas(id_empresa),   -- NULL = particular
    telefono               VARCHAR(15),
    CONSTRAINT uq_visitante_identificacion UNIQUE (id_tipo_identificacion, numero_identificacion)
);

-- Cada visita de un visitante (evita repetir sus datos personales)
CREATE TABLE visitas (
    id_visita                SERIAL PRIMARY KEY,
    id_visitante             INT NOT NULL REFERENCES visitantes(id_visitante),
    id_colaborador_anfitrion INT NOT NULL REFERENCES colaboradores(id_colaborador),
    fecha_visita             DATE NOT NULL,
    motivo                   VARCHAR(150) NOT NULL,
    estado                   VARCHAR(12) NOT NULL DEFAULT 'programada'
                             CONSTRAINT ck_visita_estado CHECK (estado IN ('programada', 'realizada', 'cancelada'))
);

-- ---------------------------------------------------------------------
-- 4. CONTROL DE ACCESO
-- ---------------------------------------------------------------------

-- Niveles de permiso de las credenciales
CREATE TABLE roles_acceso (
    id_rol_acceso SERIAL PRIMARY KEY,
    nombre        VARCHAR(60)  NOT NULL UNIQUE,
    descripcion   VARCHAR(200) NOT NULL
);

-- Lectores QR / puertas
CREATE TABLE puntos_acceso (
    id_punto_acceso SERIAL PRIMARY KEY,
    nombre          VARCHAR(70) NOT NULL UNIQUE,
    id_ubicacion    INT NOT NULL REFERENCES ubicaciones(id_ubicacion),
    tipo_punto      VARCHAR(10) NOT NULL DEFAULT 'mixto'
                    CONSTRAINT ck_punto_tipo CHECK (tipo_punto IN ('entrada', 'salida', 'mixto')),
    activo          BOOLEAN NOT NULL DEFAULT TRUE
);

-- Qué rol de acceso puede pasar por qué punto (N:M)
CREATE TABLE permisos_rol_punto (
    id_rol_acceso   INT NOT NULL REFERENCES roles_acceso(id_rol_acceso) ON DELETE CASCADE,
    id_punto_acceso INT NOT NULL REFERENCES puntos_acceso(id_punto_acceso) ON DELETE CASCADE,
    PRIMARY KEY (id_rol_acceso, id_punto_acceso)
);

-- Estados posibles de una credencial
CREATE TABLE estados_credencial (
    id_estado      SMALLINT PRIMARY KEY,
    clave          VARCHAR(12)  NOT NULL UNIQUE,
    descripcion    VARCHAR(100) NOT NULL,
    permite_acceso BOOLEAN NOT NULL DEFAULT FALSE
);

-- Códigos QR: de un colaborador O de una visita, nunca de ambos
CREATE TABLE credenciales (
    id_credencial  SERIAL PRIMARY KEY,
    codigo_qr      VARCHAR(40) NOT NULL UNIQUE
                   DEFAULT 'QR-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 16)),
    id_rol_acceso  INT NOT NULL REFERENCES roles_acceso(id_rol_acceso),
    id_colaborador INT REFERENCES colaboradores(id_colaborador),
    id_visita      INT REFERENCES visitas(id_visita),
    fecha_emision  DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_vigencia DATE NOT NULL,
    id_estado      SMALLINT NOT NULL DEFAULT 1 REFERENCES estados_credencial(id_estado),
    CONSTRAINT ck_cred_fechas CHECK (fecha_vigencia >= fecha_emision),
    CONSTRAINT ck_cred_titular CHECK ((id_colaborador IS NOT NULL AND id_visita IS NULL)
        OR (id_colaborador IS NULL AND id_visita IS NOT NULL))
);

-- Bitácora: cada escaneo, permitido o denegado
CREATE TABLE registro_accesos (
    id_registro     BIGSERIAL PRIMARY KEY,
    id_credencial   INT NOT NULL REFERENCES credenciales(id_credencial) ON DELETE CASCADE,
    id_punto_acceso INT NOT NULL REFERENCES puntos_acceso(id_punto_acceso),
    fecha_hora      TIMESTAMP NOT NULL DEFAULT LOCALTIMESTAMP,
    tipo_evento     VARCHAR(7)  CHECK (tipo_evento IN ('entrada', 'salida')),
    resultado       VARCHAR(9)  NOT NULL DEFAULT 'permitido'
                    CHECK (resultado IN ('permitido', 'denegado')),
    motivo          VARCHAR(120),
    registrado_por  NAME NOT NULL DEFAULT session_user,
    -- permitido => lleva tipo de evento;  denegado => lleva motivo
    CONSTRAINT ck_registro_coherencia CHECK ((resultado = 'permitido' AND tipo_evento IS NOT NULL AND motivo IS NULL)
        OR (resultado = 'denegado'  AND tipo_evento IS NULL     AND motivo IS NOT NULL))
);

-- Cuentas de PostgreSQL que usan la aplicación (la contraseña la guarda
-- PostgreSQL con SCRAM-SHA-256; aquí NO se almacena ninguna contraseña)
CREATE TABLE usuarios_sistema (
    id_usuario_sistema SERIAL PRIMARY KEY,
    cuenta             VARCHAR(63) NOT NULL UNIQUE,
    rol_aplicacion     VARCHAR(20) NOT NULL
                       CHECK (rol_aplicacion IN ('rol_admin_bd', 'rol_seguridad', 'rol_recepcion',
                                                 'rol_rrhh', 'rol_consulta', 'rol_lector_qr')),
    id_colaborador     INT UNIQUE REFERENCES colaboradores(id_colaborador),  -- NULL = cuenta de servicio
    activo             BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta         TIMESTAMP NOT NULL DEFAULT LOCALTIMESTAMP,
    creado_por         NAME NOT NULL DEFAULT session_user
);

-- ---------------------------------------------------------------------
-- 5. ÍNDICES
-- ---------------------------------------------------------------------
CREATE INDEX idx_registro_credencial_fecha ON registro_accesos (id_credencial, fecha_hora DESC);
CREATE INDEX idx_registro_fecha            ON registro_accesos (fecha_hora);
CREATE INDEX idx_registro_punto            ON registro_accesos (id_punto_acceso);
CREATE INDEX idx_credencial_colaborador    ON credenciales (id_colaborador);
CREATE INDEX idx_credencial_visita         ON credenciales (id_visita);
CREATE INDEX idx_visita_visitante          ON visitas (id_visitante);
CREATE INDEX idx_visita_fecha              ON visitas (fecha_visita);
CREATE INDEX idx_colaborador_puesto        ON colaboradores (id_puesto);

-- Un colaborador solo puede tener UNA credencial activa a la vez
CREATE UNIQUE INDEX ux_credencial_activa_colaborador
    ON credenciales (id_colaborador) WHERE id_estado = 1 AND id_colaborador IS NOT NULL;

-- Verificación: deben listarse 18 tablas
SELECT COUNT(*) AS total_tablas
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
