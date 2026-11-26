/* ==========================================================
   Maélis Orvanne Shop — panier du site public
   Le panier est gardé dans le navigateur (localStorage).
   Les prix affichés sont relus depuis le serveur (/api/produits/),
   et le serveur recalcule tout à la commande.
   ========================================================== */
(function () {
  "use strict";

  var CLE = "mo-panier";
  var QTE_MAX = 99;

  /* ---------- Stockage ---------- */
  function lire() {
    try {
      var brut = JSON.parse(localStorage.getItem(CLE) || "[]");
      if (!Array.isArray(brut)) return [];
      return brut.filter(function (l) { return l && l.id > 0 && l.qte > 0; });
    } catch (e) { return []; }
  }
  function ecrire(lignes) {
    try { localStorage.setItem(CLE, JSON.stringify(lignes)); } catch (e) {}
    majCompteur();
  }
  function ajouter(id, qte) {
    var lignes = lire();
    var l = lignes.find(function (x) { return x.id === id; });
    if (l) l.qte = Math.min(l.qte + qte, QTE_MAX);
    else lignes.push({ id: id, qte: Math.min(qte, QTE_MAX) });
    ecrire(lignes);
  }
  function changerQte(id, qte) {
    var lignes = lire();
    if (qte <= 0) lignes = lignes.filter(function (x) { return x.id !== id; });
    else lignes.forEach(function (x) { if (x.id === id) x.qte = Math.min(qte, QTE_MAX); });
    ecrire(lignes);
  }
  function nombreArticles() {
    return lire().reduce(function (s, l) { return s + l.qte; }, 0);
  }

  /* ---------- Format ---------- */
  function fcfa(n) {
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " FCFA";
  }
  function echapper(t) {
    var d = document.createElement("div");
    d.textContent = t == null ? "" : String(t);
    return d.innerHTML;
  }

  /* ---------- Compteur dans l'en-tête ---------- */
  function majCompteur() {
    var n = nombreArticles();
    document.querySelectorAll("[data-compteur-panier]").forEach(function (el) {
      el.textContent = n > 99 ? "99+" : String(n);
      el.setAttribute("data-vide", n ? "0" : "1");
    });
  }

  /* ---------- Notification ---------- */
  var minuterie = null;
  function notifier(texte) {
    var t = document.getElementById("toast-panier");
    if (!t) return;
    t.querySelector("[data-texte]").textContent = texte;
    t.classList.add("visible");
    clearTimeout(minuterie);
    minuterie = setTimeout(function () { t.classList.remove("visible"); }, 3200);
  }

  /* ---------- Boutons « Ajouter au panier » ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-ajouter]");
    if (!b) return;
    e.preventDefault();
    var id = parseInt(b.getAttribute("data-ajouter"), 10);
    var qte = 1;
    var champ = b.getAttribute("data-quantite-depuis");
    if (champ) {
      var input = document.querySelector(champ);
      qte = Math.max(1, Math.min(QTE_MAX, parseInt(input && input.value, 10) || 1));
    }
    ajouter(id, qte);
    if (window.fbq) { try { fbq("track", "AddToCart", { content_ids: [String(id)], content_type: "product" }); } catch (err) {} }
    var vers = b.getAttribute("data-aller-panier");
    if (vers) { window.location.href = vers; return; }
    notifier((qte > 1 ? qte + " × " : "") + (b.getAttribute("data-nom") || "Article") + " ajouté au panier");
  });

  /* ---------- Sélecteur de quantité (fiche produit) ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-qte-pas]");
    if (!b || b.closest("[data-ligne]")) return;
    var input = b.parentElement.querySelector("input");
    var v = (parseInt(input.value, 10) || 1) + parseInt(b.getAttribute("data-qte-pas"), 10);
    input.value = Math.max(1, Math.min(QTE_MAX, v));
  });

  /* ---------- Menu mobile ---------- */
  var boutonMenu = document.querySelector("[data-ouvrir-menu]");
  if (boutonMenu) {
    boutonMenu.addEventListener("click", function () {
      var menu = document.getElementById("menu-principal");
      var ouvert = menu.classList.toggle("ouvert");
      boutonMenu.setAttribute("aria-expanded", ouvert ? "true" : "false");
    });
    var fermerMenu = function () {
      document.getElementById("menu-principal").classList.remove("ouvert");
      boutonMenu.setAttribute("aria-expanded", "false");
    };
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#menu-principal") && !e.target.closest("[data-ouvrir-menu]")) fermerMenu();
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") fermerMenu(); });
  }

  /* ---------- Page panier : commande en 3 étapes ---------- */
  var zone = document.getElementById("zone-panier");
  var produits = {}; // id -> données à jour venant du serveur
  var REGLES = {
    TG: function (c) { return c.length === 8; },
    BJ: function (c) { return (c.length === 10 && c.indexOf("01") === 0) || c.length === 8; },
    GH: function (c) { return (c.length === 10 && c[0] === "0") || (c.length === 9 && c[0] !== "0"); }
  };
  var INDICATIFS = { TG: "228", BJ: "229", GH: "233" };

  function normaliserVille(t) {
    return (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/-/g, " ").replace(/\s+/g, " ").trim();
  }
  function totalArticles() {
    return lignesDisponibles().reduce(function (s, l) { return s + produits[l.id].prix_actuel * l.qte; }, 0);
  }
  function lignesDisponibles() {
    return lire().filter(function (l) { return produits[l.id] && produits[l.id].disponible; });
  }

  function afficherPanier() {
    var lignes = lire().filter(function (l) { return produits[l.id]; });
    document.getElementById("panier-vide").hidden = lignes.length > 0;
    document.getElementById("panier-plein").hidden = lignes.length === 0;
    if (!lignes.length) return;

    var total = 0, articles = 0, indispo = 0, html = "", recap = "";
    lignes.forEach(function (l) {
      var p = produits[l.id];
      var dispo = p.disponible;
      var sousTotal = p.prix_actuel * l.qte;
      if (dispo) {
        total += sousTotal; articles += l.qte;
        recap += "<li><span>" + echapper(p.nom) + " × " + l.qte + '</span><span class="prix">' + fcfa(sousTotal) + "</span></li>";
      } else { indispo++; }
      var visuel = p.image
        ? '<img src="' + echapper(p.image) + '" alt="" loading="lazy">'
        : '<span class="monogramme" aria-hidden="true"><span class="o">O</span><span class="m">M</span></span>';
      html +=
        '<div class="ligne-panier' + (dispo ? "" : " indisponible") + '" data-ligne="' + l.id + '">' +
          '<a class="vignette" href="' + echapper(p.url) + '">' + visuel + "</a>" +
          "<div>" +
            '<a class="nom" href="' + echapper(p.url) + '">' + echapper(p.nom) + "</a>" +
            '<div class="small text-body-secondary prix">' + fcfa(p.prix_actuel) +
              (p.en_promo ? ' <span class="prix-barre">' + fcfa(p.prix) + "</span>" : "") + "</div>" +
            '<div class="details">' +
              (dispo
                ? '<div class="selecteur-qte petit">' +
                    '<button type="button" data-qte-pas="-1" aria-label="Retirer un">−</button>' +
                    '<input type="number" min="1" max="99" value="' + l.qte + '" aria-label="Quantité">' +
                    '<button type="button" data-qte-pas="1" aria-label="Ajouter un">+</button>' +
                  "</div>"
                : '<span class="dispo-non">Épuisé pour le moment</span>') +
              '<button type="button" class="retirer" data-retirer>Retirer</button>' +
            "</div>" +
          "</div>" +
          '<div class="sous-total prix">' + (dispo ? fcfa(sousTotal) : "—") + "</div>" +
        "</div>";
    });
    document.getElementById("lignes-panier").innerHTML = html;
    document.getElementById("recap-lignes").innerHTML = recap;
    document.querySelectorAll("[data-total-panier]").forEach(function (el) { el.textContent = fcfa(total); });
    document.getElementById("avert-indispo").hidden = indispo === 0;
    document.querySelectorAll("[data-bouton-commander]").forEach(function (b) { b.disabled = articles === 0; });
  }

  function chargerPanier(apres) {
    var lignes = lire();
    if (!lignes.length) { afficherPanier(); return; }
    var ids = lignes.map(function (l) { return l.id; }).join(",");
    fetch(zone.getAttribute("data-api") + "?ids=" + ids, { headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        produits = {};
        data.produits.forEach(function (p) { produits[p.id] = p; });
        var restants = lignes.filter(function (l) { return produits[l.id]; });
        if (restants.length !== lignes.length) ecrire(restants);
        afficherPanier();
        if (apres) apres();
      })
      .catch(function () {
        document.getElementById("lignes-panier").innerHTML =
          '<div class="p-4 text-center text-body-secondary">Impossible de charger le panier. Vérifiez votre connexion puis rechargez la page.</div>';
      });
  }

  /* Numéro de téléphone : même règles que le serveur, pour prévenir avant l'envoi */
  function numeroValide(saisie, code) {
    var brut = saisie.trim();
    var c = brut.replace(/\D/g, "");
    if (brut[0] === "+" || c.indexOf("00") === 0) return c.replace(/^00/, "").length >= 8;
    var ind = INDICATIFS[code];
    if (ind && c.indexOf(ind) === 0 && !(REGLES[code] && REGLES[code](c))) c = c.slice(ind.length);
    return REGLES[code] ? REGLES[code](c) : c.length >= 6;
  }
  function erreur(champ, texte) {
    effacerErreur(champ);
    champ.classList.add("is-invalid");
    var div = document.createElement("div");
    div.className = "erreur-champ";
    div.textContent = texte;
    champ.closest(".champ").appendChild(div);
  }
  function effacerErreur(champ) {
    var bloc = champ.closest(".champ");
    if (!bloc) return;
    bloc.querySelectorAll(".erreur-champ").forEach(function (d) { d.remove(); });
    bloc.querySelectorAll(".is-invalid").forEach(function (d) { d.classList.remove("is-invalid"); });
  }

  function brancherCommande(form) {
    var infosPays = {};
    try { infosPays = JSON.parse(document.getElementById("pays-infos").textContent); } catch (e) {}
    var pays = form.querySelector("[name=pays]");
    var tel = form.querySelector("[name=telephone]");
    var villeListe = form.querySelector("[name=ville_liste]");
    var villeAutre = form.querySelector("[name=ville]");
    var blocAutre = document.getElementById("bloc-autre-ville");
    var etapeMax = 1;

    function villeChoisie() {
      return villeListe.value === "__autre__" ? villeAutre.value.trim() : villeListe.value;
    }

    function verifierLivraison() {
      var premier = null;
      if (!villeListe.value) { erreur(villeListe, "Choisissez votre ville."); premier = villeListe; }
      else if (villeListe.value === "__autre__" && !villeAutre.value.trim()) { erreur(villeAutre, "Écrivez le nom de votre ville."); premier = villeAutre; }
      var nom = form.querySelector("[name=nom_client]");
      if (!nom.value.trim()) { erreur(nom, "Indiquez votre nom."); premier = premier || nom; }
      if (!tel.value.trim()) { erreur(tel, "Indiquez votre numéro WhatsApp."); premier = premier || tel; }
      else if (!numeroValide(tel.value, pays.value)) {
        var i = infosPays[pays.value] || {};
        erreur(tel, "Ce numéro ne semble pas complet. Exemple : " + (i.exemple || "") + ".");
        premier = premier || tel;
      }
      if (premier) premier.focus();
      return !premier;
    }

    function resumeLivraison() {
      var i = infosPays[pays.value] || {};
      document.getElementById("resume-livraison").innerHTML =
        "<strong>" + echapper(form.nom_client.value.trim()) + "</strong><br>" +
        "+" + (i.indicatif || "") + " " + echapper(tel.value.trim()) + "<br>" +
        echapper(villeChoisie()) + (i.nom ? ", " + echapper(i.nom) : "");
    }

    function majPays() {
      var i = infosPays[pays.value];
      if (!i) return;
      document.getElementById("prefixe-tel").textContent = "+" + i.indicatif;
      tel.placeholder = i.exemple;
      var garde = villeListe.value;
      villeListe.innerHTML = '<option value="">Choisissez votre ville</option>' +
        i.villes.map(function (v) { return '<option value="' + echapper(v) + '">' + echapper(v) + "</option>"; }).join("") +
        '<option value="__autre__">Autre ville…</option>';
      if (garde === "__autre__" || i.villes.indexOf(garde) >= 0) villeListe.value = garde;
      blocAutre.hidden = villeListe.value !== "__autre__";
    }
    if (pays.tagName === "SELECT") pays.addEventListener("change", function () { majPays(); effacerErreur(tel); });
    villeListe.addEventListener("change", function () {
      effacerErreur(villeListe);
      blocAutre.hidden = villeListe.value !== "__autre__";
      if (!blocAutre.hidden) villeAutre.focus();
    });

    var tarifs = [];
    try { tarifs = JSON.parse(document.getElementById("tarifs-livraison").textContent); } catch (e) {}
    function calculerLivraison() {
      var code = pays.value, cle = normaliserVille(villeChoisie());
      var duPays = tarifs.filter(function (t) { return t.pays === code; });
      var t = duPays.find(function (x) { return x.ville === cle; }) || duPays.find(function (x) { return x.ville === ""; });
      var frais = t ? t.frais : null;
      var articles = totalArticles();
      var aConfirmer = frais === null || frais === undefined;
      document.getElementById("frais-livraison").textContent = aConfirmer ? "à confirmer" : (frais ? fcfa(frais) : "Gratuite");
      document.getElementById("total-final").textContent = fcfa(articles + (aConfirmer ? 0 : frais)) + (aConfirmer ? " + envoi" : "");
      document.getElementById("note-envoi").hidden = !aConfirmer;
    }

    function allerA(n, defiler) {
      document.querySelectorAll("[data-pas]").forEach(function (p) {
        p.hidden = parseInt(p.getAttribute("data-pas"), 10) !== n;
      });
      etapeMax = Math.max(etapeMax, n);
      document.querySelectorAll(".progression li").forEach(function (li) {
        var k = parseInt(li.getAttribute("data-aller"), 10);
        li.classList.toggle("actif", k === n);
        li.classList.toggle("fait", k < n || (k <= etapeMax && k !== n));
        if (k === n) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
      });
      if (n === 3) { resumeLivraison(); calculerLivraison(); }
      if (defiler !== false) window.scrollTo({ top: 0, behavior: "smooth" });
    }

    form.addEventListener("click", function (e) {
      var b = e.target.closest("[data-suivant]");
      if (!b) return;
      var n = parseInt(b.getAttribute("data-suivant"), 10);
      var actuelle = parseInt(form.querySelector("[data-pas]:not([hidden])").getAttribute("data-pas"), 10);
      if (n === 2 && !lignesDisponibles().length) return;
      if (n === 3 && actuelle === 2 && !verifierLivraison()) return;
      allerA(n);
    });
    document.querySelector(".progression").addEventListener("click", function (e) {
      var li = e.target.closest("[data-aller]");
      if (!li || !li.classList.contains("fait")) return;
      var n = parseInt(li.getAttribute("data-aller"), 10);
      if (n === 3 && !verifierLivraison()) { allerA(2); return; }
      allerA(n);
    });
    // Entrée dans un champ de livraison = « Suivant », pas l'envoi de la commande
    form.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && e.target.tagName === "INPUT" && e.target.closest('[data-pas="2"]')) {
        e.preventDefault();
        if (verifierLivraison()) allerA(3);
      }
    });

    form.addEventListener("input", function (e) { effacerErreur(e.target); });
    form.addEventListener("submit", function (e) {
      var lignes = lignesDisponibles();
      if (!lignes.length) { e.preventDefault(); allerA(1); return; }
      if (!verifierLivraison()) { e.preventDefault(); allerA(2); return; }
      form.querySelector("[name=panier]").value = JSON.stringify(lignes);
      var b = form.querySelector("[data-bouton-valider]");
      b.disabled = true;
      b.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Envoi…';
    });

    // Retour du serveur avec des erreurs : on rouvre l'étape concernée
    form.querySelectorAll(".champ .erreur-champ").forEach(function (d) {
      var c = d.closest(".champ").querySelector("input, select, textarea");
      if (c) c.classList.add("is-invalid");
    });
    return function () {
      if (form.querySelector('[data-pas="2"] .erreur-champ')) { etapeMax = 2; allerA(2, false); }
    };
  }

  if (zone) {
    zone.addEventListener("click", function (e) {
      var ligne = e.target.closest("[data-ligne]");
      if (!ligne) return;
      var id = parseInt(ligne.getAttribute("data-ligne"), 10);
      if (e.target.closest("[data-retirer]")) { changerQte(id, 0); afficherPanier(); return; }
      var pas = e.target.closest("[data-qte-pas]");
      if (pas) {
        var actuelle = (lire().find(function (x) { return x.id === id; }) || { qte: 1 }).qte;
        changerQte(id, Math.max(1, actuelle + parseInt(pas.getAttribute("data-qte-pas"), 10)));
        afficherPanier();
      }
    });
    zone.addEventListener("change", function (e) {
      var ligne = e.target.closest("[data-ligne]");
      if (!ligne || e.target.tagName !== "INPUT") return;
      changerQte(parseInt(ligne.getAttribute("data-ligne"), 10), Math.max(1, parseInt(e.target.value, 10) || 1));
      afficherPanier();
    });
    var form = document.getElementById("form-commande");
    var rouvrir = form ? brancherCommande(form) : null;
    chargerPanier(rouvrir);
  }

  /* ---------- Page de confirmation : on vide le panier ---------- */
  if (document.querySelector("[data-vider-panier]")) ecrire([]);

  majCompteur();
  window.addEventListener("storage", function (e) { if (e.key === CLE) majCompteur(); });
})();


// Bandeau des horaires : compte à rebours seconde par seconde jusqu'à la fermeture (ou la réouverture)
(function () {
  var bandeau = document.querySelector(".bandeau-horaires[data-cible]");
  if (!bandeau) return;
  var chrono = bandeau.querySelector("[data-reste]");
  var cible = new Date(bandeau.dataset.cible).getTime();
  var ouvert = bandeau.dataset.ouvert === "1";
  var cases = {};

  function deux(n) { return String(n).padStart(2, "0"); }
  function construire(avecJours) {
    chrono.innerHTML = "";
    (avecJours ? ["j", "h", "min", "s"] : ["h", "min", "s"]).forEach(function (u) {
      var c = document.createElement("span");
      c.className = "case";
      c.innerHTML = '<span class="n">00</span><span class="u">' + u + "</span>";
      chrono.appendChild(c);
      cases[u] = c.querySelector(".n");
    });
    chrono.dataset.jours = avecJours ? "1" : "0";
  }
  function poser(u, valeur) {
    var el = cases[u];
    if (el && el.textContent !== valeur) {
      el.textContent = valeur;
      el.classList.remove("bascule"); void el.offsetWidth; el.classList.add("bascule");
    }
  }
  function maj() {
    var s = Math.max(0, Math.round((cible - Date.now()) / 1000));
    var j = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
    if (chrono.dataset.jours !== (j ? "1" : "0")) construire(j > 0);
    if (j) poser("j", String(j));
    poser("h", deux(h)); poser("min", deux(m)); poser("s", deux(sec));
    if (ouvert && s <= 3600 && !bandeau.classList.contains("est-bientot")) {
      bandeau.classList.replace("est-ouvert", "est-bientot");
      var t = bandeau.querySelector("[data-titre]");
      if (t) t.textContent = "Bientôt la fermeture";
    }
    if (s === 0) { setTimeout(function () { location.reload(); }, 1500); return; }
    setTimeout(maj, 1000 - (Date.now() % 1000) + 5);  // calé sur la seconde pile
  }
  maj();
})();
