/* =====================================================================
   SCRIPT 03 – CONSULTAS AVANZADAS (Actividad 2.2)
   Proyecto : Sistema de Control de Acceso con Códigos QR – Grupo Solutions
   Materia  : Taller de Bases de Datos – ITVH (Equipo 6 Magenta)
   SGBD     : PostgreSQL 18 (compatible con 15 o superior)
   Consultas de solo lectura; requieren 01_tablas.sql y 02_datos.sql.
   ===================================================================== */


-- =====================================================================
-- 2. CONSULTAS SIMPLES Y COLUMNAS CALCULADAS
-- =====================================================================

-- 2.1 Directorio de colaboradores activos (proyección y alias)
SELECT numero_empleado  AS "No. Empleado",
       nombre_completo  AS "Colaborador",
       tipo_colaborador AS "Tipo",
       correo           AS "Correo institucional",
       telefono         AS "Teléfono"
FROM colaboradores
WHERE activo = TRUE
ORDER BY nombre_completo;

-- 2.2 Antigüedad laboral de los colaboradores (columnas calculadas con fechas)
SELECT nombre_completo                                     AS colaborador,
       fecha_ingreso,
       CURRENT_DATE - fecha_ingreso                        AS dias_en_empresa,
       AGE(CURRENT_DATE, fecha_ingreso)                    AS antiguedad,
       EXTRACT(YEAR FROM AGE(CURRENT_DATE, fecha_ingreso)) AS anios_cumplidos
FROM colaboradores
ORDER BY fecha_ingreso;   -- del más antiguo al más reciente

-- 2.3 Duración de la jornada por turno (operaciones aritméticas con TIME)
SELECT nombre_turno,
       hora_entrada,
       hora_salida,
       hora_salida - hora_entrada AS duracion_jornada,
       ROUND((EXTRACT(EPOCH FROM (hora_salida - hora_entrada)) / 3600)::numeric, 2)     AS horas_diarias,
       ROUND((EXTRACT(EPOCH FROM (hora_salida - hora_entrada)) / 3600 * 5)::numeric, 2) AS horas_semanales
FROM horarios_laborales
ORDER BY hora_entrada;

-- 2.4 Días de vigencia restantes de las credenciales del personal (expresión CASE)
SELECT codigo_qr,
       estado,
       fecha_emision,
       fecha_vigencia,
       fecha_vigencia - CURRENT_DATE AS dias_restantes,
       CASE
           WHEN fecha_vigencia < CURRENT_DATE        THEN 'Vencida'
           WHEN fecha_vigencia - CURRENT_DATE <= 180 THEN 'Renovar pronto'
           ELSE 'Vigente'
       END AS alerta
FROM credenciales
WHERE id_colaborador IS NOT NULL
ORDER BY dias_restantes;

-- 2.5 Ficha de visitantes identificados con INE (funciones de texto y COALESCE)
SELECT id_visitante,
       UPPER(nombre_completo)                                    AS visitante,
       COALESCE(empresa_procedencia, 'Particular (sin empresa)') AS procedencia,
       SPLIT_PART(identificacion, '-', 1)                        AS tipo_documento,
       'Visita del ' || TO_CHAR(fecha_visita, 'DD/MM/YYYY')      AS fecha_formateada
FROM visitantes
WHERE identificacion LIKE 'INE-%'
ORDER BY fecha_visita;

-- 2.6 Entradas posteriores a las 09:00 en un rango de fechas (BETWEEN y filtros compuestos)
SELECT id_registro,
       id_credencial,
       id_punto_acceso,
       fecha_hora::date   AS fecha,
       fecha_hora::time   AS hora,
       UPPER(tipo_evento) AS evento
FROM registro_accesos
WHERE fecha_hora::date BETWEEN '2026-09-15' AND '2026-09-17'
  AND fecha_hora::time > '09:00'
  AND tipo_evento = 'entrada'
ORDER BY fecha_hora;

-- =====================================================================
-- 3. FUNCIONES, CONVERSIÓN, AGRUPAMIENTO Y ORDENAMIENTO
-- =====================================================================

-- 3.1 Resumen estadístico de la bitácora de accesos (funciones de agregación)
SELECT COUNT(*)                                        AS total_eventos,
       COUNT(*) FILTER (WHERE tipo_evento = 'entrada') AS entradas,
       COUNT(*) FILTER (WHERE tipo_evento = 'salida')  AS salidas,
       COUNT(DISTINCT id_credencial)                   AS credenciales_utilizadas,
       MIN(fecha_hora)                                 AS primer_evento,
       MAX(fecha_hora)                                 AS ultimo_evento
FROM registro_accesos;

-- 3.2 Afluencia diaria de accesos (CAST, GROUP BY y ORDER BY)
SELECT CAST(fecha_hora AS DATE)                        AS dia,
       COUNT(*)                                        AS total_eventos,
       COUNT(*) FILTER (WHERE tipo_evento = 'entrada') AS entradas,
       COUNT(*) FILTER (WHERE tipo_evento = 'salida')  AS salidas
FROM registro_accesos
GROUP BY CAST(fecha_hora AS DATE)
ORDER BY dia;

-- 3.3 Antigüedad promedio por tipo de colaborador (AVG, SUM y conversión de tipos)
SELECT tipo_colaborador,
       COUNT(*)                                                              AS total_personas,
       SUM(CURRENT_DATE - fecha_ingreso)                                     AS dias_acumulados,
       ROUND(AVG(CURRENT_DATE - fecha_ingreso), 1)                           AS promedio_dias,
       ROUND(CAST(AVG(CURRENT_DATE - fecha_ingreso) / 365.25 AS NUMERIC), 2) AS promedio_anios,
       MIN(fecha_ingreso)                                                    AS ingreso_mas_antiguo
FROM colaboradores
GROUP BY tipo_colaborador
ORDER BY promedio_anios DESC;

-- 3.4 Departamentos con dos o más colaboradores (HAVING)
SELECT d.nombre_departamento,
       COUNT(c.id_colaborador)          AS total_colaboradores,
       COUNT(*) FILTER (WHERE c.activo) AS colaboradores_activos
FROM departamentos d
JOIN puestos p       ON p.id_departamento = d.id_departamento
JOIN colaboradores c ON c.id_puesto       = p.id_puesto
GROUP BY d.nombre_departamento
HAVING COUNT(c.id_colaborador) >= 2
ORDER BY total_colaboradores DESC, d.nombre_departamento;

-- 3.5 Distribución porcentual de credenciales por titular y estado (función de ventana y conversión a texto)
SELECT CASE WHEN id_colaborador IS NOT NULL THEN 'Colaborador' ELSE 'Visitante' END AS titular,
       estado,
       COUNT(*) AS total,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)::VARCHAR || ' %' AS porcentaje
FROM credenciales
GROUP BY CASE WHEN id_colaborador IS NOT NULL THEN 'Colaborador' ELSE 'Visitante' END,
         estado
ORDER BY total DESC;

-- =====================================================================
-- 4. CONSULTAS MULTITABLA (JOINS)
-- =====================================================================

-- 4.1 Expediente laboral del personal activo (INNER JOIN de cuatro tablas)
SELECT c.numero_empleado,
       c.nombre_completo,
       p.nombre_puesto,
       d.nombre_departamento,
       d.ubicacion AS ubicacion_area,
       h.nombre_turno,
       h.hora_entrada,
       h.hora_salida
FROM colaboradores c
INNER JOIN puestos p            ON c.id_puesto       = p.id_puesto
INNER JOIN departamentos d      ON p.id_departamento = d.id_departamento
INNER JOIN horarios_laborales h ON c.id_horario      = h.id_horario
WHERE c.activo = TRUE
ORDER BY d.nombre_departamento, c.nombre_completo;

-- 4.2 Bitácora de accesos legible (INNER JOIN combinado con LEFT JOIN)
SELECT r.id_registro,
       TO_CHAR(r.fecha_hora, 'DD/MM/YYYY HH24:MI')     AS fecha_hora,
       COALESCE(co.nombre_completo, v.nombre_completo) AS persona,
       CASE WHEN co.id_colaborador IS NOT NULL
            THEN 'Colaborador' ELSE 'Visitante' END    AS tipo_persona,
       cr.codigo_qr,
       ra.nombre_rol,
       pa.nombre_punto,
       r.tipo_evento
FROM registro_accesos r
INNER JOIN credenciales  cr ON r.id_credencial   = cr.id_credencial
INNER JOIN roles_acceso  ra ON cr.id_rol_acceso  = ra.id_rol_acceso
INNER JOIN puntos_acceso pa ON r.id_punto_acceso = pa.id_punto_acceso
LEFT  JOIN colaboradores co ON cr.id_colaborador = co.id_colaborador
LEFT  JOIN visitantes    v  ON cr.id_visitante   = v.id_visitante
ORDER BY r.fecha_hora;

-- 4.3 Uso de cada punto de acceso, incluidos los que no registran tráfico (LEFT JOIN)
SELECT pa.nombre_punto,
       pa.ubicacion,
       COUNT(r.id_registro) AS total_eventos,
       MAX(r.fecha_hora)    AS ultimo_evento
FROM puntos_acceso pa
LEFT JOIN registro_accesos r ON pa.id_punto_acceso = r.id_punto_acceso
GROUP BY pa.id_punto_acceso, pa.nombre_punto, pa.ubicacion
ORDER BY total_eventos DESC;

-- 4.4 Visitantes, anfitrión y área visitada (JOIN encadenado)
SELECT v.nombre_completo                             AS visitante,
       COALESCE(v.empresa_procedencia, 'Particular') AS empresa,
       v.fecha_visita,
       a.nombre_completo                             AS anfitrion,
       p.nombre_puesto                               AS puesto_anfitrion,
       d.nombre_departamento                         AS area_visitada,
       d.ubicacion
FROM visitantes v
JOIN colaboradores a ON v.id_colaborador_anfitrion = a.id_colaborador
JOIN puestos p       ON a.id_puesto       = p.id_puesto
JOIN departamentos d ON p.id_departamento = d.id_departamento
ORDER BY v.fecha_visita;

-- 4.5 Credenciales emitidas que nunca se han utilizado (RIGHT JOIN)
SELECT cr.codigo_qr,
       co.nombre_completo,
       co.activo AS colaborador_activo,
       cr.estado AS estado_credencial
FROM registro_accesos r
RIGHT JOIN credenciales  cr ON r.id_credencial   = cr.id_credencial
LEFT  JOIN colaboradores co ON cr.id_colaborador = co.id_colaborador
WHERE r.id_registro IS NULL
ORDER BY cr.codigo_qr;

-- 4.6 Tiempo de permanencia por jornada (SELF JOIN)
SELECT cr.codigo_qr,
       e.fecha_hora::date          AS dia,
       e.fecha_hora::time          AS hora_entrada,
       s.fecha_hora::time          AS hora_salida,
       s.fecha_hora - e.fecha_hora AS tiempo_permanencia
FROM registro_accesos e
JOIN registro_accesos s
     ON  s.id_credencial    = e.id_credencial
     AND s.fecha_hora::date = e.fecha_hora::date
     AND s.tipo_evento      = 'salida'
     AND s.fecha_hora       > e.fecha_hora
JOIN credenciales cr ON cr.id_credencial = e.id_credencial
WHERE e.tipo_evento = 'entrada'
ORDER BY tiempo_permanencia DESC;

-- =====================================================================
-- 5. SUBCONSULTAS
-- =====================================================================

-- 5.1 Colaboradores que han fungido como anfitriones (subconsulta con IN)
SELECT c.numero_empleado,
       c.nombre_completo,
       c.correo
FROM colaboradores c
WHERE c.id_colaborador IN (SELECT v.id_colaborador_anfitrion
                           FROM visitantes v)
ORDER BY c.nombre_completo;

-- 5.2 Colaboradores activos sin ningún acceso registrado (subconsulta correlacionada con NOT EXISTS)
SELECT c.numero_empleado,
       c.nombre_completo,
       c.tipo_colaborador
FROM colaboradores c
WHERE c.activo = TRUE
  AND NOT EXISTS (SELECT 1
                  FROM credenciales cr
                  JOIN registro_accesos r ON r.id_credencial = cr.id_credencial
                  WHERE cr.id_colaborador = c.id_colaborador)   -- correlación
ORDER BY c.nombre_completo;

-- 5.3 Indicadores por colaborador (subconsultas escalares en la lista SELECT)
SELECT c.nombre_completo,
       (SELECT COUNT(*)
          FROM credenciales cr
          JOIN registro_accesos r ON r.id_credencial = cr.id_credencial
         WHERE cr.id_colaborador = c.id_colaborador)          AS total_eventos,
       (SELECT MAX(r.fecha_hora)
          FROM credenciales cr
          JOIN registro_accesos r ON r.id_credencial = cr.id_credencial
         WHERE cr.id_colaborador = c.id_colaborador)          AS ultimo_registro,
       (SELECT COUNT(*)
          FROM visitantes v
         WHERE v.id_colaborador_anfitrion = c.id_colaborador) AS visitantes_recibidos
FROM colaboradores c
ORDER BY total_eventos DESC, c.nombre_completo;

-- 5.4 Permanencia promedio por departamento (subconsulta en FROM / tabla derivada)
SELECT d.nombre_departamento,
       COUNT(*)                        AS jornadas_registradas,
       ROUND(AVG(t.horas)::numeric, 2) AS promedio_horas
FROM (
        SELECT e.id_credencial,
               EXTRACT(EPOCH FROM (s.fecha_hora - e.fecha_hora)) / 3600 AS horas
        FROM registro_accesos e
        JOIN registro_accesos s
             ON  s.id_credencial    = e.id_credencial
             AND s.fecha_hora::date = e.fecha_hora::date
             AND s.tipo_evento      = 'salida'
             AND s.fecha_hora       > e.fecha_hora
        WHERE e.tipo_evento = 'entrada'
     ) AS t
JOIN credenciales  cr ON cr.id_credencial  = t.id_credencial
JOIN colaboradores c  ON c.id_colaborador  = cr.id_colaborador
JOIN puestos       p  ON p.id_puesto       = c.id_puesto
JOIN departamentos d  ON d.id_departamento = p.id_departamento
GROUP BY d.nombre_departamento
ORDER BY promedio_horas DESC;

-- 5.5 Credenciales con uso superior al promedio (subconsulta en HAVING)
SELECT cr.codigo_qr,
       COUNT(*) AS eventos,
       (SELECT ROUND(AVG(t.n), 2)
          FROM (SELECT COUNT(*) AS n
                  FROM registro_accesos
                 GROUP BY id_credencial) t) AS promedio_general
FROM registro_accesos r
JOIN credenciales cr ON cr.id_credencial = r.id_credencial
GROUP BY cr.codigo_qr
HAVING COUNT(*) > (SELECT AVG(t.n)
                     FROM (SELECT COUNT(*) AS n
                             FROM registro_accesos
                            GROUP BY id_credencial) t)
ORDER BY eventos DESC;

-- =====================================================================
-- 6. OPERADORES SET
-- =====================================================================

-- 6.1 Directorio unificado de personas con acceso al edificio (UNION)
SELECT 'Colaborador'         AS tipo_persona,
       c.nombre_completo,
       c.numero_empleado     AS identificador,
       d.nombre_departamento AS area_o_empresa
FROM colaboradores c
JOIN puestos p       ON p.id_puesto       = c.id_puesto
JOIN departamentos d ON d.id_departamento = p.id_departamento
WHERE c.activo = TRUE
 
UNION
 
SELECT 'Visitante',
       v.nombre_completo,
       v.identificacion,
       COALESCE(v.empresa_procedencia, 'Particular')
FROM visitantes v
 
ORDER BY tipo_persona, nombre_completo;

-- 6.2 Puntos de acceso compartidos por personal y visitantes (INTERSECT)
-- Puntos utilizados por colaboradores
SELECT pa.nombre_punto
FROM registro_accesos r
JOIN credenciales  cr ON cr.id_credencial   = r.id_credencial
JOIN puntos_acceso pa ON pa.id_punto_acceso = r.id_punto_acceso
WHERE cr.id_colaborador IS NOT NULL
 
INTERSECT
 
-- Puntos utilizados por visitantes
SELECT pa.nombre_punto
FROM registro_accesos r
JOIN credenciales  cr ON cr.id_credencial   = r.id_credencial
JOIN puntos_acceso pa ON pa.id_punto_acceso = r.id_punto_acceso
WHERE cr.id_visitante IS NOT NULL;

-- 6.3 Colaboradores activos que no han registrado accesos (EXCEPT)
-- Todos los colaboradores activos
SELECT c.numero_empleado, c.nombre_completo
FROM colaboradores c
WHERE c.activo = TRUE
 
EXCEPT
 
-- Colaboradores con al menos un evento de acceso
SELECT c.numero_empleado, c.nombre_completo
FROM colaboradores c
JOIN credenciales cr    ON cr.id_colaborador = c.id_colaborador
JOIN registro_accesos r ON r.id_credencial   = cr.id_credencial
 
ORDER BY nombre_completo;

-- 6.4 Tablero ejecutivo del sistema de control de acceso (UNION ALL y conversión de tipos)
SELECT 1 AS orden, 'Colaboradores activos' AS indicador, COUNT(*)::text AS valor
FROM colaboradores WHERE activo = TRUE
UNION ALL
SELECT 2, 'Colaboradores dados de baja', COUNT(*)::text
FROM colaboradores WHERE activo = FALSE
UNION ALL
SELECT 3, 'Visitantes registrados', COUNT(*)::text
FROM visitantes
UNION ALL
SELECT 4, 'Credenciales activas', COUNT(*)::text
FROM credenciales WHERE estado = 'activa'
UNION ALL
SELECT 5, 'Credenciales vencidas', COUNT(*)::text
FROM credenciales WHERE estado = 'vencida'
UNION ALL
SELECT 6, 'Eventos de acceso registrados', COUNT(*)::text
FROM registro_accesos
UNION ALL
SELECT 7, 'Punto de acceso con mayor tráfico',
       (SELECT pa.nombre_punto
          FROM registro_accesos r
          JOIN puntos_acceso pa ON pa.id_punto_acceso = r.id_punto_acceso
         GROUP BY pa.nombre_punto
         ORDER BY COUNT(*) DESC
         LIMIT 1)
ORDER BY orden;
