/* =====================================================================
   SCRIPT 02 – POBLACIÓN DE DATOS (INSERT)
   Proyecto : Sistema de Control de Acceso con Códigos QR – Grupo Solutions
   Materia  : Taller de Bases de Datos – ITVH (Equipo 6 Magenta)
   SGBD     : PostgreSQL 18 (compatible con 15 o superior)
   Carga los datos en su estado final (después de la Actividad 2.1).
   Esperado: 6, 4, 3, 4, 9, 10, 5, 15 y 23 filas por tabla.
   ===================================================================== */

-- Catálogo de departamentos
INSERT INTO departamentos (nombre_departamento, ubicacion) VALUES
('Dirección General',             'Piso 3, Edificio Principal'),
('Recursos Humanos',              'Piso 3, Ala Norte'),
('Tecnologías de la Información', 'Piso 1, Ala Sur'),
('Contabilidad y Finanzas',       'Piso 2, Ala Sur'),
('Seguridad Patrimonial',         'Planta Baja, Caseta de Control'),
('Atención a Clientes',           'Planta Baja, Recepción');
 
-- Catálogo de roles de acceso
INSERT INTO roles_acceso (nombre_rol, descripcion) VALUES
('Acceso Total', 'Permite el ingreso a todas las áreas del edificio sin restricción de horario'),
('Acceso Horario de Oficina', 'Permite el ingreso únicamente durante el horario laboral asignado al colaborador'),
('Acceso Temporal de Visitante', 'Permite el ingreso limitado a la fecha y al área autorizadas para la visita'),
('Acceso Restringido a Áreas Comunes', 'Permite el ingreso solo a recepción, sala de espera y áreas comunes, sin acceso a oficinas internas ni a la sala de servidores');
 
-- Turnos laborales (hora de salida ya ampliada 15 minutos)
INSERT INTO horarios_laborales (nombre_turno, hora_entrada, hora_salida, dias_aplicables) VALUES
('Turno Matutino',       '07:00', '15:15', 'Lunes a Viernes'),
('Turno Vespertino',     '14:00', '22:15', 'Lunes a Viernes'),
('Turno Administrativo', '09:00', '18:15', 'Lunes a Viernes');
 
-- Puntos de acceso vigentes
INSERT INTO puntos_acceso (nombre_punto, ubicacion, tipo_punto) VALUES
('Entrada Principal',                                'Planta Baja, Vestíbulo', 'mixto'),
('Acceso a Estacionamiento',                         'Sótano 1',               'mixto'),
('Puerta de Oficinas Administrativas',               'Piso 2',                 'mixto'),
('Acceso a Sala de Servidores y Telecomunicaciones', 'Piso 1, Área de TI',     'mixto');
 
-- Puestos por departamento
INSERT INTO puestos (nombre_puesto, id_departamento) VALUES
('Director General', 1),
('Coordinador de Recursos Humanos', 2),
('Analista de Nómina y Prestaciones', 2),
('Administrador de Redes', 3),
('Soporte Técnico', 3),
('Contador General', 4),
('Jefe de Seguridad Patrimonial', 5),
('Guardia de Acceso', 5),
('Ejecutivo de Atención a Clientes', 6);
 
-- Colaboradores (Karla Hernández con baja lógica)
INSERT INTO colaboradores (nombre_completo, numero_empleado, tipo_colaborador, id_puesto,
                           id_horario, telefono, correo, fecha_ingreso, activo) VALUES
('Mariana Torres Gutiérrez',       'EMP-0001', 'empleado',    1, 3, '9931054872', 'mariana.torres@solutions.com.mx',    '2019-03-11', TRUE),
('Roberto Jiménez Pech',           'EMP-0002', 'empleado',    2, 3, '9932187045', 'roberto.jimenez@solutions.com.mx',   '2020-06-01', TRUE),
('Diana Cristina López May',       'EMP-0003', 'empleado',    3, 3, '9934471023', 'diana.lopez@solutions.com.mx',       '2021-02-15', TRUE),
('Fernando Alberto Castillo Ruiz', 'EMP-0004', 'empleado',    4, 3, '9931123456', 'fernando.castillo@solutions.com.mx', '2018-09-20', TRUE),
('Karla Patricia Hernández Cruz',  'CON-0005', 'contratista', 5, 1, '9935678234', 'karla.hernandez@solutions.com.mx',   '2023-01-10', FALSE),
('Juan Manuel Pérez Aguilar',      'EMP-0006', 'empleado',    6, 3, '9936789345', 'juan.perez@solutions.com.mx',        '2017-11-05', TRUE),
('Sergio Iván Domínguez Vera',     'EMP-0007', 'empleado',    7, 2, '9937890456', 'sergio.dominguez@solutions.com.mx',  '2019-07-22', TRUE),
('Lucía Beatriz Mendoza Ríos',     'CON-0008', 'contratista', 8, 1, '9938901567', 'lucia.mendoza@solutions.com.mx',     '2022-04-18', TRUE),
('Andrés Felipe Gómez Solís',      'EMP-0009', 'empleado',    8, 2, '9939012678', 'andres.gomez@solutions.com.mx',      '2020-10-30', TRUE),
('Paola Guadalupe Sánchez Nieves', 'EMP-0010', 'empleado',    9, 3, '9930123789', 'paola.sanchez@solutions.com.mx',     '2021-08-09', TRUE);
 
-- Visitantes
INSERT INTO visitantes (nombre_completo, identificacion, empresa_procedencia, motivo_visita,
                        id_colaborador_anfitrion, fecha_visita) VALUES
('Óscar Iván Ramírez Cordero',     'INE-RC820714HTC', 'Consultoría Digital del Sureste',    'Reunión de seguimiento de proyecto de infraestructura', 4, '2026-09-15'),
('Gabriela Montserrat Nava Cetina','INE-NC910302MTC', 'Despacho Contable Nava y Asociados', 'Auditoría externa del tercer trimestre',                6, '2026-09-16'),
('Ricardo Uribe Palma',            'PAS-UP7734521',   'Proveeduría Industrial Uribe',       'Entrega de equipo de cómputo y firma de contrato de mantenimiento', 4, '2026-09-17'),
('Alma Rosa Jiménez Balam',        'INE-JB880519MTC', NULL,                                 'Entrevista de trabajo para vacante en Recursos Humanos', 2, '2026-09-18'),
('Tomás Enrique Ceballos Ortiz',   'INE-CO750108HTC', 'Instalaciones Eléctricas Ceballos',  'Mantenimiento preventivo del sistema eléctrico',        7, '2026-09-19');
 
-- Credenciales (las de visitante ya marcadas como vencidas)
INSERT INTO credenciales (codigo_qr, id_rol_acceso, id_colaborador, id_visitante,
                          fecha_emision, fecha_vigencia, estado) VALUES
('QR-COL-0001', 1, 1,    NULL, '2019-03-11', '2028-12-31', 'activa'),
('QR-COL-0002', 2, 2,    NULL, '2020-06-01', '2028-12-31', 'activa'),
('QR-COL-0003', 2, 3,    NULL, '2021-02-15', '2028-12-31', 'activa'),
('QR-COL-0004', 2, 4,    NULL, '2018-09-20', '2028-12-31', 'activa'),
('QR-COL-0005', 2, 5,    NULL, '2023-01-10', '2027-01-10', 'activa'),
('QR-COL-0006', 2, 6,    NULL, '2017-11-05', '2028-12-31', 'activa'),
('QR-COL-0007', 1, 7,    NULL, '2019-07-22', '2028-12-31', 'activa'),
('QR-COL-0008', 2, 8,    NULL, '2022-04-18', '2027-04-18', 'activa'),
('QR-COL-0009', 2, 9,    NULL, '2020-10-30', '2028-12-31', 'activa'),
('QR-COL-0010', 4, 10,   NULL, '2021-08-09', '2028-12-31', 'activa'),
('QR-VIS-0001', 3, NULL, 1,    '2026-09-15', '2026-09-15', 'vencida'),
('QR-VIS-0002', 3, NULL, 2,    '2026-09-16', '2026-09-16', 'vencida'),
('QR-VIS-0003', 3, NULL, 3,    '2026-09-17', '2026-09-17', 'vencida'),
('QR-VIS-0004', 3, NULL, 4,    '2026-09-18', '2026-09-18', 'vencida'),
('QR-VIS-0005', 3, NULL, 5,    '2026-09-19', '2026-09-19', 'vencida');
 
-- Bitácora de accesos (23 eventos; el del 19/09 a las 14:00 ya corregido a 'salida')
INSERT INTO registro_accesos (id_credencial, id_punto_acceso, fecha_hora, tipo_evento) VALUES
(1,  1, '2026-09-15 07:58:00', 'entrada'), (1,  1, '2026-09-15 16:05:00', 'salida'),
(4,  3, '2026-09-15 09:02:00', 'entrada'), (4,  3, '2026-09-15 18:10:00', 'salida'),
(7,  1, '2026-09-15 13:55:00', 'entrada'), (7,  1, '2026-09-15 22:03:00', 'salida'),
(11, 1, '2026-09-15 10:15:00', 'entrada'), (11, 1, '2026-09-15 12:30:00', 'salida'),
(2,  1, '2026-09-16 08:59:00', 'entrada'), (2,  1, '2026-09-16 18:02:00', 'salida'),
(12, 1, '2026-09-16 11:00:00', 'entrada'), (12, 1, '2026-09-16 13:20:00', 'salida'),
(6,  1, '2026-09-17 09:01:00', 'entrada'), (6,  1, '2026-09-17 18:05:00', 'salida'),
(13, 1, '2026-09-17 10:40:00', 'entrada'), (13, 1, '2026-09-17 12:15:00', 'salida'),
(9,  2, '2026-09-18 13:50:00', 'entrada'), (9,  2, '2026-09-18 21:58:00', 'salida'),
(14, 1, '2026-09-18 09:30:00', 'entrada'), (14, 1, '2026-09-18 11:45:00', 'salida'),
(7,  1, '2026-09-19 14:00:00', 'salida'),
(15, 1, '2026-09-19 10:10:00', 'entrada'), (15, 1, '2026-09-19 12:00:00', 'salida');

-- Verificación de la carga
-- Conteo de filas por tabla
SELECT (SELECT COUNT(*) FROM departamentos)      AS departamentos,
       (SELECT COUNT(*) FROM roles_acceso)       AS roles,
       (SELECT COUNT(*) FROM horarios_laborales) AS horarios,
       (SELECT COUNT(*) FROM puntos_acceso)      AS puntos,
       (SELECT COUNT(*) FROM puestos)            AS puestos,
       (SELECT COUNT(*) FROM colaboradores)      AS colaboradores,
       (SELECT COUNT(*) FROM visitantes)         AS visitantes,
       (SELECT COUNT(*) FROM credenciales)       AS credenciales,
       (SELECT COUNT(*) FROM registro_accesos)   AS registros;
 
-- Relaciones (claves foráneas) definidas en el esquema
SELECT tc.table_name   AS tabla_hija,
       kcu.column_name AS columna_fk,
       ccu.table_name  AS tabla_padre,
       ccu.column_name AS columna_referenciada
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
     ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
     ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tabla_hija, columna_fk;
