// Deja a la vista un solo curso sin recargar la página, para que quien va
// probando botones no vuelva cada vez al principio. La dirección se actualiza
// igual, así un curso elegido se puede compartir o recargar.
(function () {
  var lista = document.getElementById("cursos-lista");
  if (!lista) return;
  var botones = lista.querySelectorAll(".boton-curso");
  var tarjetas = lista.querySelectorAll(".tarjeta-curso[data-curso]");
  var base = window.location.pathname;

  function aplicar(slug) {
    botones.forEach(function (boton) {
      var activo = boton.dataset.curso === slug;
      boton.classList.toggle("boton-curso--activo", activo);
      if (activo) boton.setAttribute("aria-current", "true");
      else boton.removeAttribute("aria-current");
      // El enlace queda coherente por si se abre en otra pestaña.
      boton.setAttribute(
        "href",
        activo ? base + "#cursos-lista" : base + "?curso=" + boton.dataset.curso + "#cursos-lista"
      );
    });
    tarjetas.forEach(function (tarjeta) {
      tarjeta.hidden = Boolean(slug) && tarjeta.dataset.curso !== slug;
    });
  }

  lista.addEventListener("click", function (evento) {
    var boton = evento.target.closest(".boton-curso");
    if (!boton || evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
    evento.preventDefault();
    // Tocar el botón activo lo apaga y vuelven a verse todos.
    var slug = boton.classList.contains("boton-curso--activo") ? "" : boton.dataset.curso;
    aplicar(slug);
    var url = new URL(window.location.href);
    if (slug) url.searchParams.set("curso", slug);
    else url.searchParams.delete("curso");
    url.searchParams.delete("categoria");
    url.hash = "cursos-lista";
    history.replaceState(null, "", url);
  });
})();
