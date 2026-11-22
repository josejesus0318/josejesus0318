// Caseta de vigilancia: lector QR con cámara, código tecleado, NIP y registro manual
(function () {
  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var selPunto = document.getElementById('punto');
  var caja = document.getElementById('resultado');
  var tablaUltimos = document.getElementById('ultimos');
  var ocupado = false;
  var lector = null;

  // ---------------------------------------------------------------- pestañas
  document.querySelectorAll('[data-pestana]').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('[data-pestana]').forEach(function (x) { x.classList.toggle('activa', x === b); });
      document.querySelectorAll('[data-panel]').forEach(function (p) {
        p.classList.toggle('oculto', p.dataset.panel !== b.dataset.pestana);
      });
      if (b.dataset.pestana !== 'camara') detenerCamara();
      var foco = { codigo: 'codigo', nip: 'numero', manual: 'buscar' }[b.dataset.pestana];
      if (foco) document.getElementById(foco).focus();
    });
  });

  // ---------------------------------------------------------------- sonido
  var audio = null;
  function pitido(ok) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      var tonos = ok ? [880, 1320] : [300, 220];
      tonos.forEach(function (f, i) {
        var o = audio.createOscillator(), g = audio.createGain();
        o.frequency.value = f; o.type = ok ? 'sine' : 'square';
        g.gain.value = 0.08;
        o.connect(g); g.connect(audio.destination);
        o.start(audio.currentTime + i * 0.16); o.stop(audio.currentTime + i * 0.16 + 0.14);
      });
    } catch (e) { /* sin sonido */ }
  }

  // ---------------------------------------------------------------- resultado
  function texto(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }

  function mostrar(r) {
    caja.className = 'resultado ' + (r.resultado || 'denegado');
    var titulo, icono;
    if (r.error) { titulo = 'Error'; icono = '!'; }
    else if (r.resultado === 'permitido') { titulo = r.evento === 'salida' ? 'SALIDA' : 'ACCESO PERMITIDO'; icono = '✔'; }
    else if (r.resultado === 'repetido') { titulo = 'Lectura repetida'; icono = '↻'; }
    else { titulo = 'ACCESO DENEGADO'; icono = '✖'; }
    var usos = (r.usos_restantes !== null && r.usos_restantes !== undefined)
      ? '<div class="tenue">Usos restantes del pase: ' + r.usos_restantes + '</div>' : '';
    caja.innerHTML =
      '<div class="icono">' + icono + '</div>' +
      '<div class="grande">' + titulo + '</div>' +
      (r.persona ? '<div class="nombre">' + texto(r.persona) + '</div>' : '') +
      (r.tipo || r.detalle ? '<div>' + texto([r.tipo, r.detalle].filter(Boolean).join(' · ')) + '</div>' : '') +
      '<div>' + texto(r.error || r.mensaje) + '</div>' + usos;
    pitido(r.resultado === 'permitido');
    if (!r.error && r.resultado !== 'repetido') agregarFila(r);
  }

  function agregarFila(r) {
    var ahora = new Date();
    var hh = ('0' + ahora.getHours()).slice(-2) + ':' + ('0' + ahora.getMinutes()).slice(-2);
    var etiqueta = r.resultado === 'permitido'
      ? '<span class="etiqueta ok">' + (r.evento === 'salida' ? 'Salida' : 'Entrada') + '</span>'
      : '<span class="etiqueta mal">Denegado</span><div class="tenue">' + texto(r.mensaje) + '</div>';
    var punto = selPunto.options[selPunto.selectedIndex].text;
    var fila = document.createElement('tr');
    fila.innerHTML = '<td>' + hh + '</td><td>' + texto(r.persona || '(desconocido)') +
      '<div class="tenue">' + texto(punto) + '</div></td><td>' + etiqueta + '</td>';
    var vacia = tablaUltimos.querySelector('td[colspan]');
    if (vacia) vacia.parentNode.remove();
    tablaUltimos.insertBefore(fila, tablaUltimos.firstChild);
    while (tablaUltimos.children.length > 10) tablaUltimos.lastChild.remove();
  }

  function enviar(datos) {
    if (ocupado) return Promise.resolve();
    ocupado = true;
    datos.punto = selPunto.value;
    return fetch(CASETA.registrar, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, 'Accept': 'application/json' },
      body: JSON.stringify(datos)
    }).then(function (resp) {
      if (resp.status === 401) { window.location.reload(); return null; }
      return resp.json();
    }).then(function (r) { if (r) mostrar(r); })
      .catch(function () { mostrar({ error: 'Sin conexión con el servidor. Revise el internet.' }); })
      .finally(function () { setTimeout(function () { ocupado = false; }, 1500); });
  }

  // ---------------------------------------------------------------- cámara
  var btnCamara = document.getElementById('btn-camara');
  var estadoCamara = document.getElementById('estado-camara');

  function detenerCamara() {
    if (lector && lector.isScanning) {
      lector.stop().catch(function () {});
      btnCamara.textContent = 'Iniciar cámara';
    }
  }

  btnCamara.addEventListener('click', function () {
    if (lector && lector.isScanning) { detenerCamara(); return; }
    if (!window.isSecureContext) {
      estadoCamara.textContent = 'La cámara solo funciona con https:// (o en localhost).';
      return;
    }
    lector = lector || new Html5Qrcode('lector');
    estadoCamara.textContent = 'Solicitando permiso para la cámara…';
    lector.start({ facingMode: 'environment' }, { fps: 10, qrbox: { width: 230, height: 230 } },
      function (texto) {
        if (ocupado) return;
        lector.pause(true);
        enviar({ metodo: 'qr', dato: texto }).then(function () {
          setTimeout(function () { try { lector.resume(); } catch (e) {} }, 2500);
        });
      },
      function () { /* sin código en este cuadro */ }
    ).then(function () {
      btnCamara.textContent = 'Detener cámara';
      estadoCamara.textContent = 'Leyendo… apunte al código QR.';
    }).catch(function (e) {
      estadoCamara.textContent = 'No se pudo abrir la cámara: ' + e;
    });
  });

  // ---------------------------------------------------------------- código tecleado
  document.getElementById('form-codigo').addEventListener('submit', function (e) {
    e.preventDefault();
    var campo = document.getElementById('codigo');
    enviar({ metodo: 'qr', dato: campo.value }).then(function () { campo.value = ''; campo.focus(); });
  });

  // ---------------------------------------------------------------- NIP
  document.getElementById('form-nip').addEventListener('submit', function (e) {
    e.preventDefault();
    var numero = document.getElementById('numero'), nip = document.getElementById('nip');
    enviar({ metodo: 'nip', dato: numero.value, nip: nip.value }).then(function () {
      numero.value = ''; nip.value = ''; numero.focus();
    });
  });

  // ---------------------------------------------------------------- manual
  var buscar = document.getElementById('buscar');
  var lista = document.getElementById('resultados-busqueda');
  var temporizador = null;
  buscar.addEventListener('input', function () {
    clearTimeout(temporizador);
    temporizador = setTimeout(function () {
      var q = buscar.value.trim();
      if (q.length < 2) { lista.classList.add('oculto'); return; }
      fetch(CASETA.buscar + '?q=' + encodeURIComponent(q), { headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          lista.innerHTML = '';
          if (!d.personas || !d.personas.length) {
            lista.innerHTML = '<li class="tenue">Sin coincidencias. Para alguien sin registro, cree un pase de visita.</li>';
          }
          (d.personas || []).forEach(function (p) {
            var li = document.createElement('li');
            var estado = !p.activo ? '<span class="etiqueta mal">Baja</span>'
              : p.dentro ? '<span class="etiqueta ok">Dentro</span>' : '<span class="etiqueta gris">Fuera</span>';
            li.innerHTML = '<div><b>' + texto(p.nombre_completo) + '</b> ' + estado +
              '<div class="tenue">' + texto([p.tipo, p.numero, p.adscripcion].filter(Boolean).join(' · ')) +
              (p.credencial ? ' · credencial ' + texto(p.credencial) : ' · sin credencial') + '</div></div>';
            var b = document.createElement('button');
            b.className = 'btn chico primario';
            b.textContent = p.dentro ? 'Registrar salida' : 'Registrar entrada';
            b.addEventListener('click', function () {
              enviar({ metodo: 'manual', dato: String(p.id_persona) }).then(function () {
                buscar.value = ''; lista.classList.add('oculto'); buscar.focus();
              });
            });
            li.appendChild(b);
            lista.appendChild(li);
          });
          lista.classList.remove('oculto');
        });
    }, 250);
  });
})();
