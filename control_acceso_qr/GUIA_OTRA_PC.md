# Guía: conectarse desde otra computadora

Esta guía permite que otra persona use la aplicación desde **su propia computadora**, conectada a la **misma base de datos** que está en la computadora servidor.

- **PC servidor:** la computadora que tiene PostgreSQL instalado en WSL, con la base `grupo_solutions_v2`.
- **PC cliente:** la computadora de la otra persona. No necesita WSL ni PostgreSQL, solo Python y la aplicación.

> **Requisito:** las dos computadoras deben estar en la **misma red** (el mismo Wi-Fi o módem). Algunas redes escolares o públicas bloquean la comunicación entre equipos. Si no funciona en la red de la escuela, prueben con el **hotspot de un celular** al que se conecten ambas computadoras.

---

## Parte 1 – En la PC servidor (una sola vez, y cada vez que se reinicie)

PostgreSQL vive dentro de WSL, que es una red interna que otras computadoras no ven. El script `compartir_bd.ps1` hace que Windows reenvíe las conexiones hacia WSL.

### 1. Permitir conexiones externas en PostgreSQL (solo la primera vez)

En la terminal de **WSL (Ubuntu)**:

```bash
sudo -u postgres psql -c "ALTER SYSTEM SET listen_addresses = '*';"
echo "host all all 172.16.0.0/12 scram-sha-256" | sudo tee -a /etc/postgresql/18/main/pg_hba.conf
sudo service postgresql restart
```

> Si estos comandos ya se ejecutaron antes, no hace falta repetirlos.

### 2. Compartir la base de datos en la red

1. Abran **PowerShell como administrador**: menú Inicio → escriban *PowerShell* → clic derecho → **Ejecutar como administrador**.
2. Vayan a la carpeta del proyecto y ejecuten el script:

```powershell
cd C:\Users\TU_USUARIO\Downloads\josejesus0318-main\control_acceso_qr
powershell -ExecutionPolicy Bypass -File .\herramientas\compartir_bd.ps1
```

3. Al final aparecerá algo como:

```
LISTO. La base de datos está compartida.
En las otras computadoras escriban esta IP en "Servidor" (Opciones de conexión):
    192.168.1.70
```

**Anoten esa IP**: es la que usará la PC cliente.

> - Si aparece un **AVISO** de que la red es *Pública*, copien y ejecuten el comando `Set-NetConnectionProfile …` que muestra el mismo aviso, y vuelvan a ejecutar el script.
> - **Cada vez que reinicien la PC servidor**, vuelvan a ejecutar el script, porque la IP de WSL cambia.
> - Con el script activo, en la propia PC servidor se puede usar `127.0.0.1` como servidor.
> - Para dejar de compartir: `powershell -ExecutionPolicy Bypass -File .\herramientas\compartir_bd.ps1 -Quitar`

### 3. Crear una cuenta para la otra persona (recomendado)

En la aplicación, entren con `gs_admin` → **Usuarios** → **Crear usuario…**. Asignen el rol que le corresponda (Recepción, Seguridad, etc.) y compartan la cuenta y la contraseña con esa persona.

También pueden usar las cuentas de demostración (`gs_recepcion`, `gs_seguridad`…, contraseña `GrupoSol#2026`), pero con cuentas propias la bitácora registra quién hizo cada cosa.

---

## Parte 2 – En la PC cliente

### 1. Instalar Python

1. Descarguen Python 3.12 o 3.13 desde **python.org/downloads**.
2. En el instalador marquen la casilla **"Add python.exe to PATH"** y den clic en **Install Now**.

### 2. Descargar la aplicación

1. Entren a **github.com/josejesus0318/josejesus0318**.
2. Botón verde **Code** → **Download ZIP**.
3. Descompriman el ZIP, por ejemplo en `Descargas`.

### 3. Instalar las librerías

Abran **PowerShell** (no hace falta que sea como administrador) y ejecuten, cambiando `TU_USUARIO` por su usuario de Windows:

```powershell
cd C:\Users\TU_USUARIO\Downloads\josejesus0318-main\control_acceso_qr
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

La instalación tarda unos minutos.

### 4. Comprobar que se ve el servidor

Cambien `192.168.1.70` por la IP que dio el script en la PC servidor:

```powershell
Test-NetConnection 192.168.1.70 -Port 5432
```

- **`TcpTestSucceeded : True`:** hay conexión; sigan al paso 5.
- **`False`:** revisen la sección *Problemas comunes*.

### 5. Escribir la IP del servidor en la configuración

Abran el archivo `config.ini` con el Bloc de notas:

```powershell
notepad config.ini
```

Cambien la línea `host` por la IP del servidor y guarden con **Ctrl + S**:

```ini
host = 192.168.1.70
```

> También se puede cambiar desde la aplicación: en el login, marquen **Opciones de conexión** y escriban la IP en **Servidor**.

### 6. Verificar y abrir la aplicación

```powershell
.venv\Scripts\python.exe pruebas\verificar_instalacion.py --usuario gs_recepcion
.venv\Scripts\python.exe main.py
```

El verificador pedirá la contraseña de la cuenta. Si todo sale `[OK]`, la aplicación está lista.

Si esta computadora se usará como **lector QR en una puerta**, cambien también en `config.ini` el número del punto de acceso:

```ini
[lector]
punto_acceso = 1
```

Los números son: `1` Entrada Principal, `2` Estacionamiento, `3` Oficinas Administrativas y `4` Sala de Servidores.

### Para usarla los días siguientes

Abran PowerShell en la carpeta `control_acceso_qr` y ejecuten:

```powershell
.venv\Scripts\python.exe main.py
```

La PC servidor debe estar encendida y con el script `compartir_bd.ps1` ejecutado.

---

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Test-NetConnection` da `False` | El script no se ha ejecutado, o se reinició la PC servidor | Ejecuten `compartir_bd.ps1` en la PC servidor como administrador |
| `False` aunque el script ya se ejecutó | La red es *Pública* o la red de la escuela aísla los equipos | Cambien la red a Privada (lo indica el script) o usen el hotspot de un celular |
| *No se encontró PostgreSQL en ese servidor y puerto* | IP incorrecta en `config.ini` o PostgreSQL apagado | Revisen la IP; vuelvan a ejecutar el script en el servidor |
| *El servidor rechazó la conexión (pg_hba.conf)* | Falta el permiso de red en PostgreSQL | Repitan la Parte 1, paso 1 en la PC servidor |
| *Usuario o contraseña incorrectos* | Cuenta o contraseña equivocada | Las cuentas de demostración usan `GrupoSol#2026`; tras 3 intentos fallidos el login se bloquea 30 segundos |
| *La base de datos indicada no existe* | Nombre de base distinto | En `config.ini` debe decir `base = grupo_solutions_v2` |
| `python` o `pip` no se reconocen | Python no está en el PATH | Usen siempre `.venv\Scripts\python.exe …` como en esta guía |

---

## Seguridad

- La conexión exige usuario y contraseña. PostgreSQL guarda las contraseñas cifradas con SCRAM-SHA-256 y la aplicación no las almacena.
- Cada cuenta solo puede hacer lo que su rol permite, aunque se conecte desde otra computadora.
- El puerto solo se abre en redes **privadas**. Al terminar de trabajar, ejecuten el script con `-Quitar`.
- En una red compartida (escuela), cambien las contraseñas de las cuentas de demostración desde **Usuarios → Restablecer contraseña**.
