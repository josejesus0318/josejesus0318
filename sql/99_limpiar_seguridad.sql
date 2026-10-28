/* =====================================================================
   SCRIPT 99 – ELIMINAR USUARIOS Y ROLES DE LA ACTIVIDAD 3.1
   Proyecto : Sistema de Control de Acceso con Códigos QR – Grupo Solutions
   Materia  : Taller de Bases de Datos – ITVH (Equipo 6 Magenta)
   SGBD     : PostgreSQL 18 (compatible con 15 o superior)
   Permite volver a ejecutar 05_seguridad.sql desde cero.
   Ejecutar conectado a grupo_solutions como postgres.
   ===================================================================== */

DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['admin_gs','guardia_sergio','recep_paola','rrhh_roberto','dir_mariana',
                             'app_lector_qr','cont_karla','rol_admin_bd','rol_seguridad','rol_recepcion',
                             'rol_rrhh','rol_consulta','rol_lector_qr']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('DROP OWNED BY %I', r);
            EXECUTE format('DROP ROLE %I', r);
        END IF;
    END LOOP;
END $$;
