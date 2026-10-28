/* =====================================================================
   MODELO v2 – VISTAS
   La aplicación LEE de estas vistas y ESCRIBE en las tablas. Las vistas
   también funcionan como mecanismo de seguridad: un rol puede consultar
   una vista sin tener permiso sobre todas las tablas que la componen.
   ===================================================================== */

-- Datos de la cuenta con la que se inició sesión (current_user = quien consulta)
CREATE OR REPLACE VIEW vw_mi_usuario AS
SELECT u.cuenta,
       u.rol_aplicacion,
       concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno) AS nombre_completo,
       p.nombre AS puesto
FROM usuarios_sistema u
LEFT JOIN colaboradores c ON c.id_colaborador = u.id_colaborador
LEFT JOIN puestos p       ON p.id_puesto      = c.id_puesto
WHERE u.cuenta = current_user;

-- Directorio de colaboradores activos (para elegir anfitriones y titulares)
CREATE OR REPLACE VIEW vw_directorio AS
SELECT c.id_colaborador,
       c.numero_empleado,
       concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno) AS nombre_completo,
       d.nombre AS departamento,
       u.nombre AS ubicacion
FROM colaboradores c
JOIN puestos p       ON p.id_puesto       = c.id_puesto
JOIN departamentos d ON d.id_departamento = p.id_departamento
JOIN ubicaciones u   ON u.id_ubicacion    = d.id_ubicacion
WHERE c.activo;

-- Expediente completo de colaboradores (pantalla de RRHH)
CREATE OR REPLACE VIEW vw_colaboradores_detalle AS
SELECT c.id_colaborador,
       c.numero_empleado,
       c.nombre,
       c.apellido_paterno,
       c.apellido_materno,
       concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno) AS nombre_completo,
       c.tipo_colaborador,
       c.id_puesto,
       p.nombre  AS puesto,
       d.nombre  AS departamento,
       c.id_horario,
       h.nombre_turno,
       c.telefono,
       c.correo,
       c.fecha_ingreso,
       c.activo,
       c.fecha_baja
FROM colaboradores c
JOIN puestos p            ON p.id_puesto       = c.id_puesto
JOIN departamentos d      ON d.id_departamento = p.id_departamento
JOIN horarios_laborales h ON h.id_horario      = c.id_horario;

-- Visitantes con su identificación y empresa
CREATE OR REPLACE VIEW vw_visitantes_detalle AS
SELECT v.id_visitante,
       v.nombre,
       v.apellido_paterno,
       v.apellido_materno,
       concat_ws(' ', v.nombre, v.apellido_paterno, v.apellido_materno) AS nombre_completo,
       v.id_tipo_identificacion,
       t.clave AS tipo_identificacion,
       v.numero_identificacion,
       v.id_empresa,
       COALESCE(e.nombre, 'Particular') AS empresa,
       v.telefono,
       (SELECT COUNT(*) FROM visitas x WHERE x.id_visitante = v.id_visitante) AS total_visitas
FROM visitantes v
JOIN tipos_identificacion t ON t.id_tipo_identificacion = v.id_tipo_identificacion
LEFT JOIN empresas e        ON e.id_empresa = v.id_empresa;

-- Visitas con visitante, anfitrión y área visitada
CREATE OR REPLACE VIEW vw_visitas_detalle AS
SELECT vi.id_visita,
       vi.id_visitante,
       concat_ws(' ', v.nombre, v.apellido_paterno, v.apellido_materno) AS visitante,
       COALESCE(e.nombre, 'Particular') AS empresa,
       vi.fecha_visita,
       vi.motivo,
       vi.estado,
       vi.id_colaborador_anfitrion,
       concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno) AS anfitrion,
       d.nombre AS area_visitada,
       u.nombre AS ubicacion,
       (SELECT cr.codigo_qr FROM credenciales cr
         WHERE cr.id_visita = vi.id_visita ORDER BY cr.id_credencial DESC LIMIT 1) AS codigo_qr
FROM visitas vi
JOIN visitantes v    ON v.id_visitante    = vi.id_visitante
LEFT JOIN empresas e ON e.id_empresa      = v.id_empresa
JOIN colaboradores c ON c.id_colaborador  = vi.id_colaborador_anfitrion
JOIN puestos p       ON p.id_puesto       = c.id_puesto
JOIN departamentos d ON d.id_departamento = p.id_departamento
JOIN ubicaciones u   ON u.id_ubicacion    = d.id_ubicacion;

-- Credenciales con su titular (colaborador o visitante) y su vigencia
CREATE OR REPLACE VIEW vw_credenciales_detalle AS
SELECT cr.id_credencial,
       cr.codigo_qr,
       CASE WHEN cr.id_colaborador IS NOT NULL THEN 'Colaborador' ELSE 'Visitante' END AS tipo_titular,
       CASE WHEN cr.id_colaborador IS NOT NULL
            THEN concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno)
            ELSE concat_ws(' ', v.nombre, v.apellido_paterno, v.apellido_materno) END AS titular,
       cr.id_colaborador,
       cr.id_visita,
       cr.id_rol_acceso,
       ra.nombre AS rol_acceso,
       cr.id_estado,
       ec.clave  AS estado,
       cr.fecha_emision,
       cr.fecha_vigencia,
       cr.fecha_vigencia - CURRENT_DATE AS dias_restantes
FROM credenciales cr
JOIN roles_acceso ra       ON ra.id_rol_acceso = cr.id_rol_acceso
JOIN estados_credencial ec ON ec.id_estado     = cr.id_estado
LEFT JOIN colaboradores c  ON c.id_colaborador = cr.id_colaborador
LEFT JOIN visitas vi       ON vi.id_visita     = cr.id_visita
LEFT JOIN visitantes v     ON v.id_visitante   = vi.id_visitante;

-- Bitácora legible
CREATE OR REPLACE VIEW vw_bitacora AS
SELECT r.id_registro,
       r.fecha_hora,
       CASE WHEN cr.id_colaborador IS NOT NULL
            THEN concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno)
            ELSE concat_ws(' ', v.nombre, v.apellido_paterno, v.apellido_materno) END AS persona,
       CASE WHEN cr.id_colaborador IS NOT NULL THEN 'Colaborador' ELSE 'Visitante' END AS tipo_persona,
       cr.codigo_qr,
       pa.nombre AS punto_acceso,
       r.tipo_evento,
       r.resultado,
       r.motivo,
       r.registrado_por
FROM registro_accesos r
JOIN credenciales cr      ON cr.id_credencial   = r.id_credencial
JOIN puntos_acceso pa     ON pa.id_punto_acceso = r.id_punto_acceso
LEFT JOIN colaboradores c ON c.id_colaborador   = cr.id_colaborador
LEFT JOIN visitas vi      ON vi.id_visita       = cr.id_visita
LEFT JOIN visitantes v    ON v.id_visitante     = vi.id_visitante;

-- Personas dentro del edificio: su último evento permitido de HOY es una entrada
CREATE OR REPLACE VIEW vw_personas_dentro AS
SELECT b.persona, b.tipo_persona, b.codigo_qr, b.punto_acceso, b.fecha_hora AS hora_entrada
FROM (SELECT DISTINCT ON (codigo_qr) *
      FROM vw_bitacora
      WHERE resultado = 'permitido' AND fecha_hora::date = CURRENT_DATE
      ORDER BY codigo_qr, fecha_hora DESC, id_registro DESC) b
WHERE b.tipo_evento = 'entrada';

-- Indicadores del día para la pantalla de inicio
CREATE OR REPLACE VIEW vw_resumen_hoy AS
SELECT
    (SELECT COUNT(*) FROM registro_accesos
      WHERE fecha_hora::date = CURRENT_DATE AND resultado = 'permitido') AS accesos_permitidos,
    (SELECT COUNT(*) FROM registro_accesos
      WHERE fecha_hora::date = CURRENT_DATE AND resultado = 'denegado')  AS accesos_denegados,
    (SELECT COUNT(*) FROM vw_personas_dentro)                             AS personas_dentro,
    (SELECT COUNT(*) FROM visitas
      WHERE fecha_visita = CURRENT_DATE AND estado <> 'cancelada')        AS visitas_hoy,
    (SELECT COUNT(*) FROM credenciales
      WHERE id_estado = 1 AND fecha_vigencia BETWEEN CURRENT_DATE AND CURRENT_DATE + 30) AS credenciales_por_vencer,
    (SELECT COUNT(*) FROM colaboradores WHERE activo)                     AS colaboradores_activos;

-- Cuentas de usuario de la aplicación (módulo de administración)
CREATE OR REPLACE VIEW vw_usuarios_sistema AS
SELECT u.id_usuario_sistema,
       u.cuenta,
       u.rol_aplicacion,
       CASE WHEN u.id_colaborador IS NOT NULL
            THEN concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno)
            ELSE '(cuenta de servicio)' END AS colaborador,
       u.activo,
       r.rolcanlogin AS puede_conectarse,
       u.fecha_alta,
       u.creado_por
FROM usuarios_sistema u
LEFT JOIN colaboradores c ON c.id_colaborador = u.id_colaborador
LEFT JOIN pg_roles r      ON r.rolname        = u.cuenta;
