// Kiosco de alumnos: número de control tecleado (o lector de código de barras USB) y cámara
(function () {
  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var form = document.getElementById('form-kiosco');
  var campo = document.getElementById('numero');
  var caja = document.getElementById('resultado');
  var vistaEspera = document.getElementById('vista-espera');
  var vistaFicha = document.getElementById('vista-ficha');
  var barra = document.getElementById('progreso');
  var ocupado = false;
  var temporizador = null;
  var lector = null;

  // ---------------------------------------------------------------- reloj
  function reloj() {
    var d = new Date();
    document.getElementById('reloj').textContent = d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('fecha').textContent = d.toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long' });
  }
  reloj();
  setInterval(reloj, 15000);

  // El campo siempre conserva el foco: el alumno solo teclea y presiona Enter
  function enfocar() { if (document.activeElement !== campo) campo.focus(); }
  document.addEventListener('click', function (e) {
    if (!e.target.closest('button, a, input')) enfocar();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { campo.value = ''; volverAEspera(); }
    else if (e.target !== campo && e.key.length === 1 && !e.ctrlKey && !e.metaKey) enfocar();
  });

  // ---------------------------------------------------------------- sonido
  var audio = null;
  function pitido(ok) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      (ok ? [880, 1320] : [300, 220]).forEach(function (f, i) {
        var o = audio.createOscillator(), g = audio.createGain();
        o.frequency.value = f; o.type = ok ? 'sine' : 'square';
        g.gain.value = 0.08;
        o.connect(g); g.connect(audio.destination);
        o.start(audio.currentTime + i * 0.16); o.stop(audio.currentTime + i * 0.16 + 0.14);
      });
    } catch (e) { /* sin sonido */ }
  }

  // ---------------------------------------------------------------- pantalla
  function poner(id, texto) { document.getElementById(id).textContent = texto == null || texto === '' ? '—' : texto; }

  function volverAEspera() {
    clearTimeout(temporizador);
    caja.className = 'k-resultado espera';
    vistaFicha.classList.add('oculto');
    vistaEspera.classList.remove('oculto');
    barra.style.transition = 'none';
    barra.style.width = '0';
    enfocar();
  }

  function mostrar(r) {
    var estado = r.error ? 'denegado' : r.resultado;
    caja.className = 'k-resultado ' + estado;
    vistaEspera.classList.add('oculto');
    vistaFicha.classList.remove('oculto');

    var titulo = r.error ? 'NO SE PUDO REGISTRAR'
      : r.resultado === 'permitido' ? 'ENTRADA REGISTRADA'
      : r.resultado === 'repetido' ? 'YA ESTABAS REGISTRADO'
      : 'ACCESO DENEGADO';
    poner('estado', titulo);
    poner('nombre', r.persona || (r.error ? '' : 'Alumno no identificado'));
    poner('control', r.numero_control);
    poner('carrera', r.carrera);
    poner('semestre', r.semestre ? r.semestre + '.º' : '');
    poner('hora', r.hora);
    var mensaje = r.error || r.mensaje;
    if (r.resultado === 'permitido') mensaje = 'Muestra tu credencial al personal de vigilancia.';
    if (r.resultado === 'repetido') mensaje = 'Tu entrada ya quedó registrada a las ' + r.hora + '.';
    poner('mensaje', mensaje);

    var img = document.getElementById('foto');
    var sinFoto = document.getElementById('sin-foto');
    if (r.foto) {
      img.src = r.foto;
      img.classList.remove('oculto');
      sinFoto.classList.add('oculto');
      document.getElementById('foto-ejemplo').classList.toggle('oculto', !r.foto_ejemplo);
    } else {
      img.removeAttribute('src');
      img.classList.add('oculto');
      sinFoto.classList.remove('oculto');
      document.getElementById('foto-ejemplo').classList.add('oculto');
    }

    pitido(r.resultado === 'permitido');

    // Cuenta regresiva y vuelta a la pantalla de espera
    var segundos = (KIOSCO.segundos || 6) + (estado === 'permitido' ? 0 : 2);
    clearTimeout(temporizador);
    barra.style.transition = 'none';
    barra.style.width = '100%';
    void barra.offsetWidth;
    barra.style.transition = 'width ' + segundos + 's linear';
    barra.style.width = '0';
    temporizador = setTimeout(volverAEspera, segundos * 1000);
  }

  function enviar(dato) {
    dato = (dato || '').trim();
    if (!dato || ocupado) return Promise.resolve();
    ocupado = true;
    return fetch(KIOSCO.registrar, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, 'Accept': 'application/json' },
      body: JSON.stringify({ dato: dato, punto: KIOSCO.punto })
    }).then(function (resp) {
      if (resp.status === 401) { window.location.reload(); return null; }
      return resp.json();
    }).then(function (r) { if (r) mostrar(r); })
      .catch(function () { mostrar({ error: 'Sin conexión con el servidor. Avisa al personal de vigilancia.' }); })
      .finally(function () { setTimeout(function () { ocupado = false; }, 1200); });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var dato = campo.value;
    campo.value = '';
    enviar(dato);
    enfocar();
  });

  // ---------------------------------------------------------------- cámara
  var btnCamara = document.getElementById('btn-camara');
  var estadoCamara = document.getElementById('estado-camara');

  function guardarPreferencia(valor) { try { localStorage.setItem('kiosco_camara', valor); } catch (e) { /* sin almacenamiento */ } }
  function preferencia() { try { return localStorage.getItem('kiosco_camara') === '1'; } catch (e) { return false; } }

  function formatos() {
    var F = window.Html5QrcodeSupportedFormats;
    return F ? [F.QR_CODE, F.CODE_128, F.CODE_39, F.CODE_93, F.ITF, F.EAN_13, F.CODABAR] : undefined;
  }

  function detenerCamara() {
    if (lector && lector.isScanning) {
      lector.stop().catch(function () {});
    }
    btnCamara.textContent = 'Usar cámara';
    estadoCamara.textContent = '';
    guardarPreferencia('0');
  }

  function iniciarCamara() {
    if (!window.isSecureContext) {
      estadoCamara.textContent = 'La cámara solo funciona con https:// (o en localhost).';
      return;
    }
    if (!window.Html5Qrcode) { estadoCamara.textContent = 'No se cargó el lector de códigos.'; return; }
    document.getElementById('lector').innerHTML = '';
    lector = lector || new Html5Qrcode('lector', { formatsToSupport: formatos(), verbose: false });
    estadoCamara.textContent = 'Solicitando permiso para la cámara…';
    lector.start({ facingMode: 'user' }, {
      fps: 10,
      qrbox: function (w, h) { return { width: Math.floor(w * 0.8), height: Math.floor(h * 0.6) }; }
    }, function (texto) {
      if (ocupado) return;
      lector.pause(true);
      enviar(texto).then(function () {
        setTimeout(function () { try { lector.resume(); } catch (e) {} }, 3000);
      });
    }, function () { /* sin código en este cuadro */ }
    ).then(function () {
      btnCamara.textContent = 'Apagar cámara';
      estadoCamara.textContent = 'Acerca el código de tu credencial a la cámara.';
      guardarPreferencia('1');
      enfocar();
    }).catch(function (e) {
      estadoCamara.textContent = 'No se pudo abrir la cámara: ' + e;
    });
  }

  btnCamara.addEventListener('click', function () {
    if (lector && lector.isScanning) detenerCamara(); else iniciarCamara();
  });
  if (preferencia()) iniciarCamara();
  enfocar();
})();
