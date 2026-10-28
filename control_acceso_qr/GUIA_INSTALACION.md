# Guía de instalación paso a paso

Instrucciones para instalar y ejecutar el **Sistema de Control de Acceso QR** en cualquier computadora con Windows, desde cero.

**Antes de empezar, la computadora debe tener:**

- **WSL con Ubuntu** y **PostgreSQL** instalados dentro de WSL.
- **Python 3.10 o superior** instalado en Windows.

Se usan dos terminales distintas; cada paso indica cuál:

- **WSL**: la terminal de Ubuntu, donde se escribe en `usuario@equipo:~$`.
- **PowerShell**: la terminal de Windows, donde se escribe en `PS C:\...>`.

En todos los comandos, cambien **`TU_USUARIO`** por el nombre de su carpeta de usuario de Windows, la que aparece en `C:\Users\`.

---

## Paso 1. Descargar el proyecto

1. Entren a **github.com/josejesus0318/josejesus0318**.
2. Den clic en el botón verde **Code** y luego en **Download ZIP**.
3. Abran la carpeta **Descargas**, den clic derecho en `josejesus0318-main.zip` y elijan **Extraer todo** → **Extraer**.
4. Comprueben que exista esta carpeta:

```
C:\Users\TU_USUARIO\Downloads\josejesus0318-main\control_acceso_qr
```

> A veces Windows crea una carpeta doble (`josejesus0318-main\josejesus0318-main\...`). Si les pasa, usen esa ruta en todos los comandos.

---

## Paso 2. Instalar la base de datos

**Terminal: WSL**

```bash
sudo service postgresql start
cd /mnt/c/Users/TU_USUARIO/Downloads/josejesus0318-main/control_acceso_qr
sudo -u postgres psql -f database/instalar.sql
```

- `sudo` pide la contraseña de su usuario de Ubuntu. Al escribirla no se ve nada en pantalla; es normal.
- Debe terminar con `>> Instalación terminada` y una tabla con 6 cuentas (`gs_admin`, `gs_seguridad`…).

Si aparece *Permission denied*, ejecuten esto en su lugar:

```bash
cp -r database /tmp/ && sudo -u postgres psql -f /tmp/database/instalar.sql
```

---

## Paso 3. Permitir que Windows se conecte a PostgreSQL

La aplicación corre en Windows y PostgreSQL dentro de WSL. Por omisión, PostgreSQL solo acepta conexiones del propio WSL, así que hay que permitir las que vienen de Windows.

**Terminal: WSL** (copien los comandos uno por uno)

```bash
sudo -u postgres psql -c "ALTER SYSTEM SET listen_addresses = '*';"
HBA=$(sudo -u postgres psql -tAc "SHOW hba_file;")
echo "host all all 172.16.0.0/12 scram-sha-256" | sudo tee -a "$HBA"
sudo service postgresql restart
hostname -I
```

El último comando muestra la **IP de WSL**, por ejemplo `172.30.253.13`. **Anótenla**: se usa en el paso 5.

> La red interna de WSL usa direcciones `172.16.x.x` a `172.31.x.x`; la línea agregada solo permite conexiones desde ahí y siempre con contraseña. Si su IP empieza con `192.168.`, cambien `172.16.0.0/12` por `192.168.0.0/16` en el tercer comando.

---

## Paso 4. Instalar las librerías de Python

**Terminal: PowerShell**

```powershell
cd C:\Users\TU_USUARIO\Downloads\josejesus0318-main\control_acceso_qr
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

La instalación tarda unos minutos.

> **Importante:** en esta guía siempre se usa `.venv\Scripts\python.exe` en lugar de `python`, `pip` o `.venv\Scripts\activate`. Así se evitan dos errores comunes de Windows: *"python no se reconoce"* (Python no está en el PATH) y *"la ejecución de scripts está deshabilitada"*.
>
> Si `py` no se reconoce, Python no está instalado, o se instaló desde la Microsoft Store. Instálenlo desde **python.org/downloads** marcando la casilla **"Add python.exe to PATH"**.

---

## Paso 5. Poner la IP de WSL en la configuración

**Terminal: PowerShell** (en la misma carpeta)

```powershell
notepad config.ini
```

En el Bloc de notas cambien la línea `host` por la IP que anotaron en el paso 3, guarden con **Ctrl + S** y cierren:

```ini
host = 172.30.253.13
```

---

## Paso 6. Verificar la instalación

**Terminal: PowerShell**

```powershell
.venv\Scripts\python.exe pruebas\verificar_instalacion.py
```

Cuando pida la contraseña, escriban `GrupoSol#2026`. Todo debe salir `[OK]`.

- Si **pyzbar** sale como `[AVISO]`, no pasa nada: el lector usa OpenCV.
- Si la **cámara** sale `[FALLA]`, cierren Zoom, Teams o la app Cámara, y prueben `--camara 1` al final del comando.

---

## Paso 7. Abrir la aplicación

**Terminal: PowerShell**

```powershell
.venv\Scripts\python.exe pruebas\generar_qr_demo.py
.venv\Scripts\python.exe main.py
```

- El primer comando crea la carpeta `qr_demo` con códigos QR de prueba para mostrarlos a la cámara desde el celular.
- El segundo abre la aplicación.

### Cuentas de acceso

Todas las cuentas usan la contraseña **`GrupoSol#2026`**: la **G** y la **S** van en mayúscula y lleva el símbolo **#**.

| Usuario | Rol | Qué puede hacer |
|---|---|---|
| `gs_admin` | Administrador | Todo, incluida la creación de usuarios |
| `gs_seguridad` | Seguridad | Lector QR, bitácora y credenciales |
| `gs_recepcion` | Recepción | Visitantes, visitas y credenciales de visita |
| `gs_rrhh` | Recursos Humanos | Colaboradores y catálogos |
| `gs_direccion` | Dirección | Solo consulta |
| `gs_lector` | Lector QR | Abre directo el lector de la cámara |

Tras 3 contraseñas incorrectas, el login se bloquea 30 segundos.

---

## Prueba rápida

1. Entren con `gs_admin`.
2. Abran **Lector QR** → **Abrir lector QR** y elijan **Entrada Principal**.
3. En **Captura manual** escriban `QR-COL-0001` y presionen Enter. Debe salir **verde: acceso permitido, entrada**.
4. Escriban `QR-COL-0005`. Debe salir **rojo: credencial revocada**.
5. Den clic en **Iniciar cámara** y muestren desde el celular un QR de la carpeta `qr_demo`.
6. Cierren el lector y abran **Bitácora**: deben aparecer las lecturas que hicieron.

---

## Uso diario

Cada vez que vayan a usar la aplicación:

**Terminal: WSL**

```bash
sudo service postgresql start
hostname -I
```

**Terminal: PowerShell**

```powershell
cd C:\Users\TU_USUARIO\Downloads\josejesus0318-main\control_acceso_qr
.venv\Scripts\python.exe main.py
```

> **La IP de WSL puede cambiar al reiniciar la computadora.** Si `hostname -I` muestra una IP distinta a la de `config.ini`, actualícenla con `notepad config.ini`, o en el login marquen **Opciones de conexión** y escriban la nueva IP en **Servidor**. La aplicación la guarda para la próxima vez.
>
> Dejen abierta la terminal de WSL mientras usan la aplicación: si WSL se cierra, PostgreSQL se apaga.

---

## Problemas comunes

| Mensaje o síntoma | Solución |
|---|---|
| *No fue posible conectar* / *No se encontró PostgreSQL en ese servidor y puerto* | En WSL ejecuten `sudo service postgresql start`. Comparen `hostname -I` con la IP de `config.ini` |
| *El servidor rechazó la conexión (pg_hba.conf)* | Repitan el paso 3. Si su IP de WSL empieza con `192.168.`, lean la nota de ese paso |
| *La base de datos indicada no existe* | Repitan el paso 2 |
| *Usuario o contraseña incorrectos* | La contraseña es `GrupoSol#2026`, con mayúsculas y `#` |
| `py`, `python` o `pip` no se reconocen | Usen `.venv\Scripts\python.exe` como en la guía. Si `py` tampoco funciona, instalen Python desde python.org con **"Add python.exe to PATH"** |
| *La ejecución de scripts está deshabilitada* | No usen `activate`; usen `.venv\Scripts\python.exe` |
| *No se pudo abrir la cámara 0* | Cierren las apps que usen la cámara o elijan la cámara 1 en el lector |
| *La visita no corresponde al día de hoy* (`QR-VIS-0006`) | Esa visita de prueba se crea con la fecha de instalación. Programen otra desde Recepción o repitan el paso 2 |
| Cualquier otro error | Den clic en **Mostrar detalles** en la ventana del error y copien el texto |
