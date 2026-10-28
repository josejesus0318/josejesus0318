/* =====================================================================
   SCRIPT 01 – CREACIÓN DE TABLAS (DDL)
   Proyecto : Sistema de Control de Acceso con Códigos QR – Grupo Solutions
   Materia  : Taller de Bases de Datos – ITVH (Equipo 6 Magenta)
   SGBD     : PostgreSQL 18 (compatible con 15 o superior)
   Crea las 9 tablas en 3FN con PK, FK, UNIQUE, CHECK e índices.
   Ejecutar:  psql -U postgres -d grupo_solutions -f sql/01_tablas.sql
   ===================================================================== */

-- Reconstrucción completa del esquema (elimina tablas previas si existen)
DROP TABLE IF EXISTS registro_accesos, credenciales, visitantes, colaboradores,
                     puestos, puntos_acceso, horarios_laborales, roles_acceso,
                     departamentos CASCADE;
 
-- Catálogo de áreas de la empresa
CREATE TABLE departamentos (
    id_departamento     SERIAL PRIMARY KEY,
    nombre_departamento VARCHAR(60) NOT NULL UNIQUE,
    ubicacion           VARCHAR(80) NOT NULL
);
 
-- Catálogo de niveles de permiso de las credenciales
CREATE TABLE roles_acceso (
    id_rol_acceso SERIAL PRIMARY KEY,
    nombre_rol    VARCHAR(60)  NOT NULL UNIQUE,
    descripcion   VARCHAR(200) NOT NULL
);
 
-- Catálogo de turnos del personal interno
CREATE TABLE horarios_laborales (
    id_horario      SERIAL PRIMARY KEY,
    nombre_turno    VARCHAR(40) NOT NULL UNIQUE,
    hora_entrada    TIME NOT NULL,
    hora_salida     TIME NOT NULL,
    dias_aplicables VARCHAR(40) NOT NULL,
    CHECK (hora_salida > hora_entrada)
);
 
-- Lectores QR / puertas físicas del edificio
CREATE TABLE puntos_acceso (
    id_punto_acceso SERIAL PRIMARY KEY,
    nombre_punto    VARCHAR(60) NOT NULL UNIQUE,
    ubicacion       VARCHAR(80) NOT NULL,
    tipo_punto      VARCHAR(20) NOT NULL,
    CHECK (tipo_punto IN ('entrada', 'salida', 'mixto'))
);
 
-- Puestos: cada uno pertenece a un departamento (evita dependencia transitiva)
CREATE TABLE puestos (
    id_puesto       SERIAL PRIMARY KEY,
    nombre_puesto   VARCHAR(80) NOT NULL,
    id_departamento INT NOT NULL REFERENCES departamentos(id_departamento),
    UNIQUE (nombre_puesto, id_departamento)
);
 
-- Personal interno: empleados y contratistas (baja lógica mediante "activo")
CREATE TABLE colaboradores (
    id_colaborador   SERIAL PRIMARY KEY,
    nombre_completo  VARCHAR(120) NOT NULL,
    numero_empleado  VARCHAR(15)  NOT NULL UNIQUE,
    tipo_colaborador VARCHAR(15)  NOT NULL,
    id_puesto        INT NOT NULL REFERENCES puestos(id_puesto),
    id_horario       INT NOT NULL REFERENCES horarios_laborales(id_horario),
    telefono         VARCHAR(15)  NOT NULL,
    correo           VARCHAR(100) NOT NULL UNIQUE,
    fecha_ingreso    DATE NOT NULL,
    activo           BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (tipo_colaborador IN ('empleado', 'contratista'))
);
 
-- Visitantes externos, cada uno con un colaborador anfitrión
CREATE TABLE visitantes (
    id_visitante             SERIAL PRIMARY KEY,
    nombre_completo          VARCHAR(120) NOT NULL,
    identificacion           VARCHAR(20)  NOT NULL,
    empresa_procedencia      VARCHAR(100),
    motivo_visita            VARCHAR(150) NOT NULL,
    id_colaborador_anfitrion INT NOT NULL REFERENCES colaboradores(id_colaborador),
    fecha_visita             DATE NOT NULL,
    activo                   BOOLEAN NOT NULL DEFAULT TRUE
);
 
-- Credenciales QR: pertenecen a un colaborador O a un visitante, nunca a ambos
CREATE TABLE credenciales (
    id_credencial  SERIAL PRIMARY KEY,
    codigo_qr      VARCHAR(50) NOT NULL UNIQUE,
    id_rol_acceso  INT NOT NULL REFERENCES roles_acceso(id_rol_acceso),
    id_colaborador INT REFERENCES colaboradores(id_colaborador),
    id_visitante   INT REFERENCES visitantes(id_visitante),
    fecha_emision  DATE NOT NULL,
    fecha_vigencia DATE NOT NULL,
    estado         VARCHAR(15) NOT NULL DEFAULT 'activa',
    CHECK (estado IN ('activa', 'vencida', 'revocada')),
    CHECK (fecha_vigencia >= fecha_emision),
    CHECK ((id_colaborador IS NOT NULL AND id_visitante IS NULL)
        OR (id_colaborador IS NULL AND id_visitante IS NOT NULL))
);
 
-- Bitácora de eventos de acceso (CASCADE hacia credenciales)
CREATE TABLE registro_accesos (
    id_registro     BIGSERIAL PRIMARY KEY,
    id_credencial   INT NOT NULL REFERENCES credenciales(id_credencial) ON DELETE CASCADE,
    id_punto_acceso INT NOT NULL REFERENCES puntos_acceso(id_punto_acceso),
    fecha_hora      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo_evento     VARCHAR(10) NOT NULL,
    CHECK (tipo_evento IN ('entrada', 'salida'))
);
 
-- Índices de apoyo para las consultas más frecuentes
CREATE INDEX idx_registro_credencial_fecha ON registro_accesos (id_credencial, fecha_hora);
CREATE INDEX idx_registro_punto            ON registro_accesos (id_punto_acceso);
CREATE INDEX idx_credencial_colaborador    ON credenciales (id_colaborador);
CREATE INDEX idx_credencial_visitante      ON credenciales (id_visitante);
