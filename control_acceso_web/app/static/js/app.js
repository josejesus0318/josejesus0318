// Utilidades comunes de la aplicación
(function () {
  // Dibuja los códigos QR: <div class="qr" data-qr="TEXTO" data-tam="200"></div>
  document.querySelectorAll('[data-qr]').forEach(function (el) {
    var tam = parseInt(el.dataset.tam || '200', 10);
    new QRCode(el, { text: el.dataset.qr, width: tam, height: tam, correctLevel: QRCode.CorrectLevel.M });
    el.removeAttribute('title');
  });

  // Confirmación antes de acciones importantes: <form data-confirmar="¿Seguro?">
  document.querySelectorAll('form[data-confirmar]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (!window.confirm(f.dataset.confirmar)) e.preventDefault();
    });
  });

  // Mostrar u ocultar bloques según un select o radio: data-mostrar-si="nombre=valor1,valor2"
  function actualizar() {
    document.querySelectorAll('[data-mostrar-si]').forEach(function (bloque) {
      var partes = bloque.dataset.mostrarSi.split('=');
      var campos = document.querySelectorAll('[name="' + partes[0] + '"]');
      var valor = '';
      campos.forEach(function (c) {
        if ((c.type === 'radio' || c.type === 'checkbox') ? c.checked : true) valor = c.type === 'checkbox' ? '1' : c.value;
      });
      var visible = partes[1].split(',').indexOf(valor) !== -1;
      bloque.classList.toggle('oculto', !visible);
      bloque.querySelectorAll('input, select, textarea').forEach(function (i) {
        if (i.dataset.requerido === '1') i.required = visible;
      });
    });
  }
  document.addEventListener('change', actualizar);
  actualizar();

  // Copiar al portapapeles: <button data-copiar="texto">
  document.querySelectorAll('[data-copiar]').forEach(function (b) {
    b.addEventListener('click', function () {
      navigator.clipboard.writeText(b.dataset.copiar).then(function () {
        var t = b.textContent; b.textContent = 'Copiado'; setTimeout(function () { b.textContent = t; }, 1500);
      });
    });
  });

  // Descargar el QR como imagen PNG: <a data-descargar-qr="idDelContenedor" data-nombre="pase">
  document.querySelectorAll('[data-descargar-qr]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var cont = document.getElementById(a.dataset.descargarQr);
      var canvas = cont && cont.querySelector('canvas');
      if (!canvas) return;
      var enlace = document.createElement('a');
      enlace.download = (a.dataset.nombre || 'pase') + '.png';
      enlace.href = canvas.toDataURL('image/png');
      enlace.click();
    });
  });
})();
