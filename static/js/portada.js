/* Alterna las fotos del fondo de la portada.
   Sólo se carga cuando hay más de una: con una sola no hay nada que rotar.
   Si la persona pidió menos movimiento en su sistema, se queda con la primera. */
(function () {
  "use strict";

  var INTERVALO = 6000;

  function arrancar() {
    var fondo = document.querySelector(".portada__fondo");
    if (!fondo) return;

    var fotos = fondo.querySelectorAll(".portada__foto");
    if (fotos.length < 2) return;

    var menosMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (menosMovimiento.matches) return;

    var actual = 0;
    setInterval(function () {
      // Con la pestaña en segundo plano no tiene sentido gastar en repintar.
      if (document.hidden) return;
      fotos[actual].classList.remove("portada__foto--activa");
      actual = (actual + 1) % fotos.length;
      fotos[actual].classList.add("portada__foto--activa");
    }, INTERVALO);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", arrancar);
  } else {
    arrancar();
  }
})();
