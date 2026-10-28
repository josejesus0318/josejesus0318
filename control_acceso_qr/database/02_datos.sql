/* =====================================================================
   MODELO v2 – DATOS DE PRUEBA
   Migra los datos del modelo v1 (estado final de la Actividad 2.1) a las
   18 tablas del modelo v2 y agrega una visita de HOY para poder probar
   el lector QR con un visitante.
   ===================================================================== */

-- Ubicaciones físicas del edificio
INSERT INTO ubicaciones (nombre, piso, descripcion) VALUES
('Piso 3, Edificio Principal',     3, 'Oficinas de Dirección General'),
('Piso 3, Ala Norte',              3, 'Oficinas de Recursos Humanos'),
('Piso 1, Ala Sur',                1, 'Oficinas de Tecnologías de la Información'),
('Piso 2, Ala Sur',                2, 'Oficinas de Contabilidad y Finanzas'),
('Planta Baja, Caseta de Control', 0, 'Seguridad Patrimonial'),
('Planta Baja, Recepción',         0, 'Atención a Clientes y sala de espera'),
('Planta Baja, Vestíbulo',         0, 'Acceso principal del edificio'),
('Sótano 1, Estacionamiento',     -1, 'Estacionamiento de empleados'),
('Piso 2, Oficinas Administrativas', 2, 'Pasillo de oficinas administrativas'),
('Piso 1, Área de TI',             1, 'Sala de servidores y telecomunicaciones');

INSERT INTO departamentos (nombre, id_ubicacion) VALUES
('Dirección General', 1), ('Recursos Humanos', 2), ('Tecnologías de la Información', 3),
('Contabilidad y Finanzas', 4), ('Seguridad Patrimonial', 5), ('Atención a Clientes', 6);

INSERT INTO puestos (nombre, id_departamento) VALUES
('Director General', 1), ('Coordinador de Recursos Humanos', 2),
('Analista de Nómina y Prestaciones', 2), ('Administrador de Redes', 3),
('Soporte Técnico', 3), ('Contador General', 4), ('Jefe de Seguridad Patrimonial', 5),
('Guardia de Acceso', 5), ('Ejecutivo de Atención a Clientes', 6);

INSERT INTO dias_semana (id_dia, nombre, abreviatura) VALUES
(1, 'Lunes', 'LUN'), (2, 'Martes', 'MAR'), (3, 'Miércoles', 'MIE'), (4, 'Jueves', 'JUE'),
(5, 'Viernes', 'VIE'), (6, 'Sábado', 'SAB'), (7, 'Domingo', 'DOM');

INSERT INTO horarios_laborales (nombre_turno, hora_entrada, hora_salida) VALUES
('Turno Matutino',       '07:00', '15:15'),
('Turno Vespertino',     '14:00', '22:15'),
('Turno Administrativo', '09:00', '18:15');

-- Los tres turnos aplican de lunes a viernes
INSERT INTO horario_dias (id_horario, id_dia)
SELECT h.id_horario, d.id_dia
FROM horarios_laborales h CROSS JOIN dias_semana d
WHERE d.id_dia BETWEEN 1 AND 5;

INSERT INTO tipos_identificacion (clave, nombre) VALUES
('INE', 'Credencial para votar (INE)'), ('PAS', 'Pasaporte'),
('LIC', 'Licencia de conducir'), ('CED', 'Cédula profesional');

INSERT INTO empresas (nombre, telefono) VALUES
('Consultoría Digital del Sureste',    '9933120045'),
('Despacho Contable Nava y Asociados', '9933457812'),
('Proveeduría Industrial Uribe',       '9933984410'),
('Instalaciones Eléctricas Ceballos',  '9933650921');

INSERT INTO colaboradores (numero_empleado, nombre, apellido_paterno, apellido_materno, tipo_colaborador,
                           id_puesto, id_horario, telefono, correo, fecha_ingreso, activo, fecha_baja) VALUES
('EMP-0001', 'Mariana',          'Torres',    'Gutiérrez', 'empleado',    1, 3, '9931054872', 'mariana.torres@solutions.com.mx',    '2019-03-11', TRUE,  NULL),
('EMP-0002', 'Roberto',          'Jiménez',   'Pech',      'empleado',    2, 3, '9932187045', 'roberto.jimenez@solutions.com.mx',   '2020-06-01', TRUE,  NULL),
('EMP-0003', 'Diana Cristina',   'López',     'May',       'empleado',    3, 3, '9934471023', 'diana.lopez@solutions.com.mx',       '2021-02-15', TRUE,  NULL),
('EMP-0004', 'Fernando Alberto', 'Castillo',  'Ruiz',      'empleado',    4, 3, '9931123456', 'fernando.castillo@solutions.com.mx', '2018-09-20', TRUE,  NULL),
('CON-0005', 'Karla Patricia',   'Hernández', 'Cruz',      'contratista', 5, 1, '9935678234', 'karla.hernandez@solutions.com.mx',   '2023-01-10', FALSE, '2026-09-25'),
('EMP-0006', 'Juan Manuel',      'Pérez',     'Aguilar',   'empleado',    6, 3, '9936789345', 'juan.perez@solutions.com.mx',        '2017-11-05', TRUE,  NULL),
('EMP-0007', 'Sergio Iván',      'Domínguez', 'Vera',      'empleado',    7, 2, '9937890456', 'sergio.dominguez@solutions.com.mx',  '2019-07-22', TRUE,  NULL),
('CON-0008', 'Lucía Beatriz',    'Mendoza',   'Ríos',      'contratista', 8, 1, '9938901567', 'lucia.mendoza@solutions.com.mx',     '2022-04-18', TRUE,  NULL),
('EMP-0009', 'Andrés Felipe',    'Gómez',     'Solís',     'empleado',    8, 2, '9939012678', 'andres.gomez@solutions.com.mx',      '2020-10-30', TRUE,  NULL),
('EMP-0010', 'Paola Guadalupe',  'Sánchez',   'Nieves',    'empleado',    9, 3, '9930123789', 'paola.sanchez@solutions.com.mx',     '2021-08-09', TRUE,  NULL);

INSERT INTO visitantes (nombre, apellido_paterno, apellido_materno, id_tipo_identificacion,
                        numero_identificacion, id_empresa, telefono) VALUES
('Óscar Iván',          'Ramírez',  'Cordero', 1, 'RC820714HTC', 1,    '9931472583'),
('Gabriela Montserrat', 'Nava',     'Cetina',  1, 'NC910302MTC', 2,    '9932583694'),
('Ricardo',             'Uribe',    'Palma',   2, 'UP7734521',   3,    '9933694715'),
('Alma Rosa',           'Jiménez',  'Balam',   1, 'JB880519MTC', NULL, '9934715826'),
('Tomás Enrique',       'Ceballos', 'Ortiz',   1, 'CO750108HTC', 4,    '9935826937');

-- Visitas históricas + una visita de HOY (Óscar regresa: no se duplican sus datos)
INSERT INTO visitas (id_visitante, id_colaborador_anfitrion, fecha_visita, motivo, estado) VALUES
(1, 4, '2026-09-15', 'Reunión de seguimiento de proyecto de infraestructura', 'realizada'),
(2, 6, '2026-09-16', 'Auditoría externa del tercer trimestre', 'realizada'),
(3, 4, '2026-09-17', 'Entrega de equipo de cómputo y firma de contrato de mantenimiento', 'realizada'),
(4, 2, '2026-09-18', 'Entrevista de trabajo para vacante en Recursos Humanos', 'realizada'),
(5, 7, '2026-09-19', 'Mantenimiento preventivo del sistema eléctrico', 'realizada'),
(1, 4, CURRENT_DATE, 'Revisión de avances del proyecto de infraestructura', 'programada');

INSERT INTO roles_acceso (nombre, descripcion) VALUES
('Acceso Total', 'Ingreso a todas las áreas del edificio sin restricción de horario'),
('Acceso Horario de Oficina', 'Ingreso a las áreas de oficina durante el horario laboral'),
('Acceso Temporal de Visitante', 'Ingreso limitado a la fecha y al área autorizadas para la visita'),
('Acceso Restringido a Áreas Comunes', 'Ingreso solo a recepción, sala de espera y áreas comunes');

INSERT INTO puntos_acceso (nombre, id_ubicacion, tipo_punto) VALUES
('Entrada Principal', 7, 'mixto'),
('Acceso a Estacionamiento', 8, 'mixto'),
('Puerta de Oficinas Administrativas', 9, 'mixto'),
('Acceso a Sala de Servidores y Telecomunicaciones', 10, 'mixto');

-- Matriz de permisos: qué rol de acceso pasa por qué punto
INSERT INTO permisos_rol_punto (id_rol_acceso, id_punto_acceso) VALUES
(1, 1), (1, 2), (1, 3), (1, 4),     -- Acceso Total: todos
(2, 1), (2, 2), (2, 3),             -- Horario de Oficina: todo menos servidores
(3, 1),                             -- Visitante: entrada principal
(4, 1);                             -- Áreas comunes: entrada principal

INSERT INTO estados_credencial (id_estado, clave, descripcion, permite_acceso) VALUES
(1, 'activa',     'Credencial vigente y habilitada',               TRUE),
(2, 'suspendida', 'Suspendida temporalmente por Seguridad',        FALSE),
(3, 'revocada',   'Revocada de forma definitiva (baja o extravío)', FALSE),
(4, 'vencida',    'Superó su fecha de vigencia',                   FALSE);

-- Credenciales del personal (la de Karla se revocó por su baja)
INSERT INTO credenciales (codigo_qr, id_rol_acceso, id_colaborador, fecha_emision, fecha_vigencia, id_estado) VALUES
('QR-COL-0001', 1, 1,  '2019-03-11', '2028-12-31', 1),
('QR-COL-0002', 2, 2,  '2020-06-01', '2028-12-31', 1),
('QR-COL-0003', 2, 3,  '2021-02-15', '2028-12-31', 1),
('QR-COL-0004', 2, 4,  '2018-09-20', '2028-12-31', 1),
('QR-COL-0005', 2, 5,  '2023-01-10', '2027-01-10', 3),
('QR-COL-0006', 2, 6,  '2017-11-05', '2028-12-31', 1),
('QR-COL-0007', 1, 7,  '2019-07-22', '2028-12-31', 1),
('QR-COL-0008', 2, 8,  '2022-04-18', '2027-04-18', 1),
('QR-COL-0009', 2, 9,  '2020-10-30', '2028-12-31', 1),
('QR-COL-0010', 4, 10, '2021-08-09', '2028-12-31', 1);

-- Credenciales de visita (las históricas ya vencieron; la de hoy está activa)
INSERT INTO credenciales (codigo_qr, id_rol_acceso, id_visita, fecha_emision, fecha_vigencia, id_estado) VALUES
('QR-VIS-0001', 3, 1, '2026-09-15', '2026-09-15', 4),
('QR-VIS-0002', 3, 2, '2026-09-16', '2026-09-16', 4),
('QR-VIS-0003', 3, 3, '2026-09-17', '2026-09-17', 4),
('QR-VIS-0004', 3, 4, '2026-09-18', '2026-09-18', 4),
('QR-VIS-0005', 3, 5, '2026-09-19', '2026-09-19', 4),
('QR-VIS-0006', 3, 6, CURRENT_DATE, CURRENT_DATE, 1);

-- Bitácora histórica (23 eventos permitidos del modelo v1)
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
SELECT (SELECT COUNT(*) FROM colaboradores)    AS colaboradores,   -- 10
       (SELECT COUNT(*) FROM visitantes)       AS visitantes,      -- 5
       (SELECT COUNT(*) FROM visitas)          AS visitas,         -- 6
       (SELECT COUNT(*) FROM credenciales)     AS credenciales,    -- 16
       (SELECT COUNT(*) FROM registro_accesos) AS registros;       -- 23
