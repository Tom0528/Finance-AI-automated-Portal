/* AW Portal – shared JS */

// Auto-dismiss alerts after 5s
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".alert").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity .5s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 500);
    }, 5000);
  });
});
