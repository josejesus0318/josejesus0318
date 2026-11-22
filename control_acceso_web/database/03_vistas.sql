-- =============================================================================
-- Control de Acceso Campus ITVH  ·  03_vistas.sql
-- Vistas que consulta la aplicación web.
-- Las fechas se muestran en la hora local del campus.
-- =============================================================================
SET search_path TO campus, public;

-- Personas con su tipo y su identificador principal ----------------------------
CREATE OR REPLACE VIEW vw_personas AS
SELECT p.id_persona,
       t.clave                                   AS tipo_clave,
       t.nombre                                  AS tipo,
       concat_ws(' ', p.nombre, p.apellido_paterno, p.apellido_materno) AS nombre_completo,
       p.nombre, p.apellido_paterno, p.apellido_materno,
       coalesce(a.numero_control, e.numero_empleado)                    AS numero,
       coalesce(c.nombre, d.nombre, em.nombre)                          AS adscripcion,
       a.semestre, e.puesto,
       p.correo, p.telefono, p.identificacion, p.activo, p.fecha_alta,
       a.id_carrera, e.id_departamento, pr.id_empresa
  FROM personas p
  JOIN tipos_persona t        ON t.id_tipo = p.id_tipo
  LEFT JOIN alumnos a         ON a.id_persona = p.id_persona
  LEFT JOIN carreras c        ON c.id_carrera = a.id_carrera
  LEFT JOIN empleados e       ON e.id_persona = p.id_persona
  LEFT JOIN departamentos d   ON d.id_departamento = e.id_departamento
  LEFT JOIN proveedores pr    ON pr.id_persona = p.id_persona
  LEFT JOIN empresas em       ON em.id_empresa = pr.id_empresa;

-- Credenciales con su titular, perfil, horario efectivo y estado ----------------
CREATE OR REPLACE VIEW vw_credenciales AS
SELECT c.id_credencial, c.token, c.tipo,
       c.id_persona,
       coalesce(vp.nombre_completo, c.descripcion)          AS titular,
       coalesce(vp.tipo, 'Pase genérico')                    AS tipo_titular,
       vp.numero,
       c.descripcion,
       c.id_perfil, pa.nombre                                AS perfil,
       coalesce(c.id_horario, pa.id_horario)                 AS id_horario_efectivo,
       h.nombre                                              AS horario,
       c.id_horario IS NOT NULL                              AS horario_propio,
       c.id_evento, ev.nombre                                AS evento,
       c.id_visita,
       c.nip_hash IS NOT NULL                                AS tiene_nip,
       c.vigencia_inicio, c.vigencia_fin,
       c.usos_maximos, c.usos_realizados,
       c.usos_maximos - c.usos_realizados                    AS usos_restantes,
       c.activa,
       estado_credencial(c)                                  AS estado,
       c.creada_en, u.nombre                                 AS creada_por
  FROM credenciales c
  JOIN perfiles_acceso pa      ON pa.id_perfil = c.id_perfil
  LEFT JOIN vw_personas vp     ON vp.id_persona = c.id_persona
  LEFT JOIN horarios h         ON h.id_horario = coalesce(c.id_horario, pa.id_horario)
  LEFT JOIN eventos ev         ON ev.id_evento = c.id_evento
  LEFT JOIN usuarios u         ON u.id_usuario = c.creada_por;

-- Bitácora legible ----------------------------------------------------------------
CREATE OR REPLACE VIEW vw_bitacora AS
SELECT r.id_registro,
       r.fecha_hora,
       fecha_local(r.fecha_hora)                                       AS fecha,
       (r.fecha_hora AT TIME ZONE zona_horaria())::time(0)             AS hora,
       pt.nombre                                                       AS punto,
       r.id_punto,
       r.id_persona,
       r.id_credencial,
       coalesce(vp.nombre_completo, c.descripcion, '(desconocido)')    AS persona,
       coalesce(vp.tipo, CASE WHEN c.tipo = 'generica' THEN 'Pase genérico' END) AS tipo,
       r.metodo, r.evento, r.resultado, r.motivo, r.dato_leido,
       u.usuario                                                       AS operador
  FROM registro_accesos r
  JOIN puntos_acceso pt        ON pt.id_punto = r.id_punto
  LEFT JOIN vw_personas vp     ON vp.id_persona = r.id_persona
  LEFT JOIN credenciales c     ON c.id_credencial = r.id_credencial
  LEFT JOIN usuarios u         ON u.id_usuario = r.id_usuario;

-- Asistencia: hora de llegada y de salida por persona y por día --------------------
CREATE OR REPLACE VIEW vw_asistencia AS
WITH eventos AS (
    SELECT r.id_persona,
           fecha_local(r.fecha_hora) AS fecha,
           r.evento, r.fecha_hora
      FROM registro_accesos r
      JOIN puntos_acceso pt ON pt.id_punto = r.id_punto AND pt.perimetral
     WHERE r.resultado = 'permitido' AND r.id_persona IS NOT NULL
), dia AS (
    SELECT id_persona, fecha,
           min(fecha_hora) FILTER (WHERE evento = 'entrada')  AS llegada,
           max(fecha_hora) FILTER (WHERE evento = 'salida')   AS salida,
           count(*) FILTER (WHERE evento = 'entrada')         AS entradas,
           (array_agg(evento ORDER BY fecha_hora DESC))[1]    AS ultimo_evento
      FROM eventos
     GROUP BY id_persona, fecha
)
SELECT d.id_persona, vp.nombre_completo AS persona, vp.tipo, vp.numero, vp.adscripcion,
       d.fecha,
       (d.llegada AT TIME ZONE zona_horaria())::time(0)        AS hora_llegada,
       CASE WHEN d.ultimo_evento = 'salida'
            THEN (d.salida AT TIME ZONE zona_horaria())::time(0) END AS hora_salida,
       CASE WHEN d.ultimo_evento = 'salida' AND d.llegada IS NOT NULL
            THEN date_trunc('minute', d.salida - d.llegada) END AS tiempo_en_campus,
       d.entradas,
       CASE WHEN d.ultimo_evento = 'entrada' THEN 'dentro' ELSE 'fuera' END AS estado
  FROM dia d
  JOIN vw_personas vp ON vp.id_persona = d.id_persona;

-- Quién está dentro del campus en este momento -------------------------------------
CREATE OR REPLACE VIEW vw_presentes AS
WITH ultimo AS (
    SELECT DISTINCT ON (coalesce('P' || r.id_persona, 'C' || r.id_credencial))
           r.*
      FROM registro_accesos r
      JOIN puntos_acceso pt ON pt.id_punto = r.id_punto AND pt.perimetral
     WHERE r.resultado = 'permitido'
       AND fecha_local(r.fecha_hora) = fecha_local(now())
     ORDER BY coalesce('P' || r.id_persona, 'C' || r.id_credencial), r.fecha_hora DESC
)
SELECT u.id_persona, u.id_credencial, u.id_registro,
       coalesce(vp.nombre_completo, c.descripcion)               AS persona,
       coalesce(vp.tipo, 'Pase genérico')                         AS tipo,
       coalesce(vp.numero, vp.adscripcion, ev.nombre)             AS detalle,
       u.fecha_hora                                               AS desde,
       pt.nombre                                                  AS punto
  FROM ultimo u
  JOIN puntos_acceso pt    ON pt.id_punto = u.id_punto
  LEFT JOIN vw_personas vp ON vp.id_persona = u.id_persona
  LEFT JOIN credenciales c ON c.id_credencial = u.id_credencial
  LEFT JOIN eventos ev     ON ev.id_evento = c.id_evento
 WHERE u.evento = 'entrada';

-- Resumen del día para el panel ------------------------------------------------------
CREATE OR REPLACE VIEW vw_resumen_hoy AS
SELECT
    (SELECT count(*) FROM vw_presentes)                                           AS dentro_ahora,
    count(*) FILTER (WHERE resultado = 'permitido' AND evento = 'entrada')        AS entradas,
    count(*) FILTER (WHERE resultado = 'permitido' AND evento = 'salida')         AS salidas,
    count(*) FILTER (WHERE resultado = 'denegado')                                AS denegados,
    count(*) FILTER (WHERE resultado = 'permitido' AND metodo = 'qr')             AS por_qr,
    count(*) FILTER (WHERE resultado = 'permitido' AND metodo = 'nip')            AS por_nip,
    count(*) FILTER (WHERE resultado = 'permitido' AND metodo = 'manual')         AS manuales
  FROM registro_accesos
 WHERE fecha_local(fecha_hora) = fecha_local(now());

-- Horarios con sus franjas en texto ---------------------------------------------------
CREATE OR REPLACE VIEW vw_horarios AS
SELECT h.id_horario, h.nombre, h.descripcion,
       string_agg(
           (ARRAY['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'])[f.dia_semana] || ' '
           || to_char(f.hora_inicio, 'HH24:MI') || '–' || to_char(f.hora_fin, 'HH24:MI'),
           ', ' ORDER BY f.dia_semana, f.hora_inicio)  AS franjas,
       count(f.id_franja)                              AS total_franjas
  FROM horarios h
  LEFT JOIN horario_franjas f ON f.id_horario = h.id_horario
 GROUP BY h.id_horario;
