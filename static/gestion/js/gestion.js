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
  const achat = document.getElementById("id_prix_achat");
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
    const a = achat ? parseInt(achat.value, 10) : NaN;
    if (!isNaN(a)) {
      const vente = !isNaN(pp) && pp < p ? pp : p;
      const marge = vente - a;
      resume.innerHTML += '<br><span class="' + (marge < 0 ? "text-danger" : "") + '">Bénéfice par article : <strong>' +
        (marge < 0 ? "− " : "") + formater(Math.abs(marge)) + "</strong>" +
        (vente ? " (" + Math.round((marge * 100) / vente) + " % du prix de vente)" : "") + "</span>";
    }
  }
  achat && achat.addEventListener("input", majResume);
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

  // Page Stock : prix d'achat proposé selon le produit, total de l'arrivage en direct
  const formArrivage = document.getElementById("form-arrivage");
  if (formArrivage) {
    let prixConnus = {};
    try { prixConnus = JSON.parse(document.getElementById("prix-achat").textContent); } catch (e) {}
    const produit = formArrivage.querySelector("[name=produit]");
    const qte = formArrivage.querySelector("[name=quantite]");
    const pu = formArrivage.querySelector("[name=prix_achat_unitaire]");
    const total = document.getElementById("total-arrivage");
    const majTotal = function () {
      const q = parseInt(qte.value, 10), p = parseInt(pu.value, 10);
      total.innerHTML = !isNaN(q) && !isNaN(p) ? "Total de l'achat : <strong>" + formater(q * p) + "</strong>" : "Total : —";
    };
    const proposerPrix = function () {
      if (prixConnus[produit.value] !== undefined && !pu.value) pu.value = prixConnus[produit.value];
      majTotal();
    };
    produit.addEventListener("change", function () { pu.value = ""; proposerPrix(); });
    qte.addEventListener("input", majTotal);
    pu.addEventListener("input", majTotal);
    proposerPrix();
    if (location.search.indexOf("produit=") >= 0) qte.focus();
  }
})();
