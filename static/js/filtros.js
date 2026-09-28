// Filtra la grilla de cursos sin recargar la página, para que quien va
// probando categorías no vuelva cada vez al principio. La dirección se
// actualiza igual, así un filtro se puede compartir o recargar.
(function () {
  var filtros = document.getElementById("filtros");
  if (!filtros) return;
  var enlaces = filtros.querySelectorAll(".filtro");
  var categorias = document.querySelectorAll(".categoria[data-categoria]");

  function aplicar(slug) {
    enlaces.forEach(function (enlace) {
      var activo = enlace.dataset.categoria === slug;
      enlace.classList.toggle("filtro--activo", activo);
      if (activo) enlace.setAttribute("aria-current", "true");
      else enlace.removeAttribute("aria-current");
    });
    categorias.forEach(function (bloque) {
      bloque.hidden = Boolean(slug) && bloque.dataset.categoria !== slug;
    });
  }

  filtros.addEventListener("click", function (evento) {
    var enlace = evento.target.closest(".filtro");
    if (!enlace || evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
    evento.preventDefault();
    // Tocar el filtro activo lo apaga y vuelven a verse todas.
    var slug = enlace.classList.contains("filtro--activo") ? "" : enlace.dataset.categoria;
    aplicar(slug);
    var url = new URL(window.location.href);
    if (slug) url.searchParams.set("categoria", slug);
    else url.searchParams.delete("categoria");
    url.hash = "filtros";
    history.replaceState(null, "", url);
  });
})();
