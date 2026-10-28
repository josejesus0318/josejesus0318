/* =====================================================================
   SCRIPT 04 – VISTAS (Actividad 2.3)
   Proyecto : Sistema de Control de Acceso con Códigos QR – Grupo Solutions
   Materia  : Taller de Bases de Datos – ITVH (Equipo 6 Magenta)
   SGBD     : PostgreSQL 18 (compatible con 15 o superior)
   13 vistas: simples, multitabla, subconsultas, funciones, agrupamiento y SET.
   ===================================================================== */

CREATE OR REPLACE VIEW vw_directorio_colaboradores AS
SELECT numero_empleado, nombre_completo, tipo_colaborador, correo, telefono
FROM colaboradores
WHERE activo = TRUE;

CREATE OR REPLACE VIEW vw_credenciales_activas AS
SELECT id_credencial, codigo_qr, id_rol_acceso, id_colaborador, id_visitante,
       fecha_emision, fecha_vigencia, estado
FROM credenciales
WHERE estado = 'activa'
WITH CHECK OPTION;

CREATE OR REPLACE VIEW vw_expediente_colaborador AS
SELECT c.id_colaborador, c.numero_empleado, c.nombre_completo, c.tipo_colaborador, c.activo,
       p.nombre_puesto, d.nombre_departamento, d.ubicacion AS ubicacion_area,
       h.nombre_turno, h.hora_entrada, h.hora_salida
FROM colaboradores c
INNER JOIN puestos p            ON c.id_puesto       = p.id_puesto
INNER JOIN departamentos d      ON p.id_departamento = d.id_departamento
INNER JOIN horarios_laborales h ON c.id_horario      = h.id_horario;

CREATE OR REPLACE VIEW vw_bitacora_detallada AS
SELECT r.id_registro,
       r.fecha_hora,
       TO_CHAR(r.fecha_hora, 'DD/MM/YYYY HH24:MI')     AS fecha_hora_texto,
       COALESCE(co.nombre_completo, v.nombre_completo) AS persona,
       CASE WHEN co.id_colaborador IS NOT NULL
            THEN 'Colaborador' ELSE 'Visitante' END    AS tipo_persona,
       cr.codigo_qr, ra.nombre_rol, pa.nombre_punto, r.tipo_evento
FROM registro_accesos r
INNER JOIN credenciales  cr ON r.id_credencial   = cr.id_credencial
INNER JOIN roles_acceso  ra ON cr.id_rol_acceso  = ra.id_rol_acceso
INNER JOIN puntos_acceso pa ON r.id_punto_acceso = pa.id_punto_acceso
LEFT  JOIN colaboradores co ON cr.id_colaborador = co.id_colaborador
LEFT  JOIN visitantes    v  ON cr.id_visitante   = v.id_visitante;

CREATE OR REPLACE VIEW vw_colaboradores_sin_acceso AS
SELECT c.id_colaborador, c.numero_empleado, c.nombre_completo, c.tipo_colaborador
FROM colaboradores c
WHERE c.activo = TRUE
  AND NOT EXISTS (SELECT 1
                  FROM credenciales cr
                  JOIN registro_accesos r ON r.id_credencial = cr.id_credencial
                  WHERE cr.id_colaborador = c.id_colaborador);

CREATE OR REPLACE VIEW vw_indicadores_colaborador AS
SELECT c.id_colaborador,
       c.nombre_completo,
       (SELECT COUNT(*) FROM credenciales cr
          JOIN registro_accesos r ON r.id_credencial = cr.id_credencial
         WHERE cr.id_colaborador = c.id_colaborador)          AS total_eventos,
       (SELECT MAX(r.fecha_hora) FROM credenciales cr
          JOIN registro_accesos r ON r.id_credencial = cr.id_credencial
         WHERE cr.id_colaborador = c.id_colaborador)          AS ultimo_registro,
       (SELECT COUNT(*) FROM visitantes v
         WHERE v.id_colaborador_anfitrion = c.id_colaborador) AS visitantes_recibidos
FROM colaboradores c;

CREATE OR REPLACE VIEW vw_antiguedad_colaboradores AS
SELECT nombre_completo, tipo_colaborador, fecha_ingreso,
       CURRENT_DATE - fecha_ingreso                        AS dias_en_empresa,
       AGE(CURRENT_DATE, fecha_ingreso)                    AS antiguedad,
       EXTRACT(YEAR FROM AGE(CURRENT_DATE, fecha_ingreso)) AS anios_cumplidos
FROM colaboradores;

CREATE OR REPLACE VIEW vw_ficha_visitantes AS
SELECT id_visitante,
       UPPER(nombre_completo)                                    AS visitante,
       COALESCE(empresa_procedencia, 'Particular (sin empresa)') AS procedencia,
       SPLIT_PART(identificacion, '-', 1)                        AS tipo_documento,
       LENGTH(motivo_visita)                                     AS caracteres_motivo,
       'Visita del ' || TO_CHAR(fecha_visita, 'DD/MM/YYYY')      AS fecha_formateada
FROM visitantes;

CREATE OR REPLACE VIEW vw_afluencia_diaria AS
SELECT CAST(fecha_hora AS DATE)                        AS dia,
       COUNT(*)                                        AS total_eventos,
       COUNT(*) FILTER (WHERE tipo_evento = 'entrada') AS entradas,
       COUNT(*) FILTER (WHERE tipo_evento = 'salida')  AS salidas
FROM registro_accesos
GROUP BY CAST(fecha_hora AS DATE);

CREATE OR REPLACE VIEW vw_departamentos_concentrados AS
SELECT d.nombre_departamento,
       COUNT(c.id_colaborador)          AS total_colaboradores,
       COUNT(*) FILTER (WHERE c.activo) AS colaboradores_activos
FROM departamentos d
JOIN puestos p       ON p.id_departamento = d.id_departamento
JOIN colaboradores c ON c.id_puesto       = p.id_puesto
GROUP BY d.nombre_departamento
HAVING COUNT(c.id_colaborador) >= 2;

CREATE OR REPLACE VIEW vw_directorio_unificado AS
SELECT 'Colaborador' AS tipo_persona, c.nombre_completo,
       c.numero_empleado AS identificador, d.nombre_departamento AS area_o_empresa
FROM colaboradores c
JOIN puestos p       ON p.id_puesto       = c.id_puesto
JOIN departamentos d ON d.id_departamento = p.id_departamento
WHERE c.activo = TRUE
UNION
SELECT 'Visitante', v.nombre_completo, v.identificacion,
       COALESCE(v.empresa_procedencia, 'Particular')
FROM visitantes v;

CREATE OR REPLACE VIEW vw_puntos_compartidos AS
SELECT pa.nombre_punto
FROM registro_accesos r
JOIN credenciales  cr ON cr.id_credencial   = r.id_credencial
JOIN puntos_acceso pa ON pa.id_punto_acceso = r.id_punto_acceso
WHERE cr.id_colaborador IS NOT NULL
INTERSECT
SELECT pa.nombre_punto
FROM registro_accesos r
JOIN credenciales  cr ON cr.id_credencial   = r.id_credencial
JOIN puntos_acceso pa ON pa.id_punto_acceso = r.id_punto_acceso
WHERE cr.id_visitante IS NOT NULL;

CREATE OR REPLACE VIEW vw_activos_sin_registro AS
SELECT c.numero_empleado, c.nombre_completo
FROM colaboradores c
WHERE c.activo = TRUE
EXCEPT
SELECT c.numero_empleado, c.nombre_completo
FROM colaboradores c
JOIN credenciales cr    ON cr.id_colaborador = c.id_colaborador
JOIN registro_accesos r ON r.id_credencial   = cr.id_credencial;

-- Verificación: deben aparecer 13 vistas
SELECT table_name AS vista
FROM information_schema.views
WHERE table_schema = 'public'
ORDER BY table_name;
