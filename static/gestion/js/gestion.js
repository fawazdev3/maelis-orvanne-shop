// Maélis Orvanne Shop — petits comportements du back-office
(function () {
  "use strict";

  // Thème clair / sombre (mémorisé dans le navigateur)
  const racine = document.documentElement;
  function majBoutonsTheme() {
    const sombre = racine.getAttribute("data-bs-theme") === "dark";
    document.querySelectorAll("[data-basculer-theme]").forEach(function (b) {
      b.setAttribute("aria-label", sombre ? "Passer au thème clair" : "Passer au thème sombre");
    });
  }
  document.querySelectorAll("[data-basculer-theme]").forEach(function (bouton) {
    bouton.addEventListener("click", function () {
      const nouveau = racine.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      racine.setAttribute("data-bs-theme", nouveau);
      try { localStorage.setItem("mo-theme", nouveau); } catch (e) { /* stockage indisponible */ }
      majBoutonsTheme();
    });
  });
  majBoutonsTheme();

  // Menu latéral sur mobile
  const sidebar = document.querySelector(".mo-sidebar");
  const voile = document.querySelector(".mo-voile");
  const boutonMenu = document.querySelector("[data-ouvrir-menu]");
  function fermerMenu() {
    if (!sidebar) return;
    sidebar.classList.remove("ouverte");
    voile && voile.classList.remove("visible");
    boutonMenu && boutonMenu.setAttribute("aria-expanded", "false");
  }
  if (boutonMenu && sidebar) {
    boutonMenu.addEventListener("click", function () {
      const ouverte = sidebar.classList.toggle("ouverte");
      voile && voile.classList.toggle("visible", ouverte);
      boutonMenu.setAttribute("aria-expanded", ouverte ? "true" : "false");
    });
  }
  voile && voile.addEventListener("click", fermerMenu);

  // Aperçu de la photo avant l'enregistrement
  document.querySelectorAll("input[type=file][data-apercu]").forEach(function (champ) {
    const zone = document.getElementById(champ.dataset.apercu);
    if (!zone) return;
    champ.addEventListener("change", function () {
      const fichier = champ.files && champ.files[0];
      if (!fichier) return;
      if (!fichier.type.startsWith("image/")) {
        alert("Ce fichier n'est pas une image.");
        champ.value = "";
        return;
      }
      if (fichier.size > 5 * 1024 * 1024) {
        alert("Cette image dépasse 5 Mo. Choisissez une image plus légère.");
        champ.value = "";
        return;
      }
      const lecteur = new FileReader();
      lecteur.onload = function (e) {
        zone.innerHTML = "";
        const img = document.createElement("img");
        img.src = e.target.result;
        img.alt = "Aperçu de la photo";
        zone.appendChild(img);
      };
      lecteur.readAsDataURL(fichier);
      const caseRetirer = document.getElementById("id_supprimer_image");
      if (caseRetirer) caseRetirer.checked = false;
    });
  });

  // Aperçu du prix et de la remise en direct dans le formulaire produit
  const prix = document.getElementById("id_prix");
  const promo = document.getElementById("id_prix_promo");
  const resume = document.getElementById("resume-prix");
  function formater(n) {
    return Math.round(n).toLocaleString("fr-FR").replace(/ | /g, " ") + " FCFA";
  }
  function majResume() {
    if (!resume || !prix) return;
    const p = parseInt(prix.value, 10);
    const pp = promo ? parseInt(promo.value, 10) : NaN;
    if (isNaN(p)) { resume.textContent = "Saisissez un prix."; return; }
    if (!isNaN(pp) && pp < p) {
      const remise = Math.round(((p - pp) * 100) / p);
      resume.innerHTML = "Affiché sur le site : <s>" + formater(p) + "</s> <strong>" + formater(pp) + "</strong> <span class=\"etiquette etiquette-promo\">−" + remise + " %</span>";
    } else if (!isNaN(pp) && pp >= p) {
      resume.textContent = "Le prix promo doit être inférieur au prix normal.";
    } else {
      resume.innerHTML = "Affiché sur le site : <strong>" + formater(p) + "</strong>";
    }
  }
  prix && prix.addEventListener("input", majResume);
  promo && promo.addEventListener("input", majResume);
  majResume();

  // Copier le message prêt à envoyer au client
  document.querySelectorAll("[data-copier]").forEach(function (bouton) {
    bouton.addEventListener("click", function () {
      const cible = document.getElementById(bouton.dataset.copier);
      if (!cible) return;
      navigator.clipboard.writeText(cible.value || cible.textContent).then(function () {
        const texte = bouton.innerHTML;
        bouton.innerHTML = '<i class="bi bi-check2" aria-hidden="true"></i> Copié';
        setTimeout(function () { bouton.innerHTML = texte; }, 1800);
      });
    });
  });
})();
