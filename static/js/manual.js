/* Manual de uso: abre las capturas en grande sin salir de la página.
   Sin JavaScript, el enlace abre la imagen en otra pestaña. */
(function () {
  var visor = document.getElementById("visor");
  if (!visor || typeof visor.showModal !== "function") return;
  var imagen = visor.querySelector("img");

  document.addEventListener("click", function (evento) {
    var enlace = evento.target.closest("[data-ampliar]");
    if (!enlace) return;
    evento.preventDefault();
    imagen.src = enlace.href;
    imagen.alt = enlace.querySelector("img").alt;
    visor.showModal();
  });

  // Clic en la imagen o en el fondo: cierra.
  visor.addEventListener("click", function (evento) {
    if (evento.target === visor || evento.target === imagen) visor.close();
  });
})();
