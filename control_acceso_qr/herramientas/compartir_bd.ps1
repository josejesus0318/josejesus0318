<#
  compartir_bd.ps1
  Permite que otras computadoras de la misma red se conecten a PostgreSQL de WSL.

  Qué hace:
    1. Enciende PostgreSQL dentro de WSL.
    2. Obtiene la IP actual de WSL (cambia al reiniciar la PC).
    3. Redirige el puerto 5432 de Windows hacia WSL (netsh portproxy).
    4. Abre el puerto 5432 en el Firewall de Windows (solo redes privadas).
    5. Muestra la IP que deben escribir las otras computadoras.

  Uso: abrir PowerShell COMO ADMINISTRADOR en la carpeta control_acceso_qr y ejecutar
      powershell -ExecutionPolicy Bypass -File .\herramientas\compartir_bd.ps1

  Para dejar de compartir la base de datos:
      powershell -ExecutionPolicy Bypass -File .\herramientas\compartir_bd.ps1 -Quitar
#>
param(
    [switch]$Quitar,
    [int]$Puerto = 5432
)

$nombreRegla = 'PostgreSQL WSL - Control de Acceso QR'

# --- Requiere permisos de administrador --------------------------------------
$identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identidad)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Abra PowerShell como administrador (clic derecho > Ejecutar como administrador) y vuelva a ejecutar el script.' -ForegroundColor Red
    exit 1
}

# --- Dejar de compartir --------------------------------------------------------
if ($Quitar) {
    netsh interface portproxy delete v4tov4 listenport=$Puerto listenaddress=0.0.0.0 2>$null | Out-Null
    Remove-NetFirewallRule -DisplayName $nombreRegla -ErrorAction SilentlyContinue
    Write-Host 'Listo: la base de datos ya no se comparte en la red.' -ForegroundColor Green
    exit 0
}

# --- 1. Encender PostgreSQL ------------------------------------------------------
Write-Host '1) Encendiendo PostgreSQL en WSL...'
wsl -u root service postgresql start | Out-Host

# --- 2. IP de WSL ----------------------------------------------------------------
Write-Host '2) Obteniendo la IP de WSL...'
$wslIp = (wsl hostname -I) -split '\s+' |
    Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' } |
    Select-Object -First 1
if (-not $wslIp) {
    Write-Host '   No se pudo obtener la IP de WSL. Verifique que Ubuntu (WSL) esté instalado.' -ForegroundColor Red
    exit 1
}
Write-Host "   IP de WSL: $wslIp"

# --- 3. Redirección de puerto ------------------------------------------------------
Write-Host "3) Redirigiendo el puerto $Puerto de Windows hacia WSL..."
netsh interface portproxy delete v4tov4 listenport=$Puerto listenaddress=0.0.0.0 2>$null | Out-Null
netsh interface portproxy add v4tov4 listenport=$Puerto listenaddress=0.0.0.0 connectport=$Puerto connectaddress=$wslIp | Out-Null

# --- 4. Firewall ----------------------------------------------------------------------
Write-Host '4) Configurando el Firewall de Windows...'
if (-not (Get-NetFirewallRule -DisplayName $nombreRegla -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $nombreRegla -Direction Inbound -Protocol TCP `
        -LocalPort $Puerto -Action Allow -Profile Private, Domain | Out-Null
}

# Advertencia si la red es "Pública" (el firewall bloquea en redes públicas)
$publicas = Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' }
foreach ($red in $publicas) {
    Write-Host "   AVISO: la red '$($red.Name)' es Pública y bloqueará las conexiones." -ForegroundColor Yellow
    Write-Host "   Cámbiela a Privada con:  Set-NetConnectionProfile -InterfaceIndex $($red.InterfaceIndex) -NetworkCategory Private" -ForegroundColor Yellow
}

# --- 5. IP para las otras computadoras -------------------------------------------------
$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.InterfaceAlias -notmatch 'vEthernet|Loopback|WSL|VirtualBox|VMware' -and
        $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1'
    } |
    Select-Object -ExpandProperty IPAddress

Write-Host ''
Write-Host 'LISTO. La base de datos está compartida.' -ForegroundColor Green
Write-Host 'En las otras computadoras escriban esta IP en "Servidor" (Opciones de conexión):'
foreach ($ip in $ips) { Write-Host "    $ip" -ForegroundColor Cyan }
Write-Host "Puerto: $Puerto    Base de datos: grupo_solutions_v2"
Write-Host 'En ESTA computadora pueden usar como servidor: 127.0.0.1'
Write-Host 'Si reinician la PC, vuelvan a ejecutar este script (la IP de WSL cambia).'
