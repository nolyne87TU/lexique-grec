// Exercices de langue : phrases à trous à compléter (saisie ou choix multiple).
(function () {
  "use strict";

  const donnees = JSON.parse(document.getElementById("donnees").textContent);
  const points = donnees.points;
  const tous = donnees.exercices;
  const zone = document.getElementById("entrainement");
  const URL_LANGUE = zone.dataset.langue;

  // ---------- Outils ----------
  const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/ς/g, "σ").trim();
  const majuscule = (s) => (s || "").charAt(0).toUpperCase() + (s || "").slice(1);

  function melanger(liste) {
    const b = liste.slice();
    for (let i = b.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [b[i], b[j]] = [b[j], b[i]];
    }
    return b;
  }

  function el(tag, props, ...enfants) {
    const e = document.createElement(tag);
    for (const k in props || {}) {
      if (k === "class") e.className = props[k];
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), props[k]);
      else e.setAttribute(k, props[k]);
    }
    enfants.flat().forEach((c) => { if (c !== null && c !== undefined && c !== false) e.append(c); });
    return e;
  }

  const vider = () => zone.replaceChildren();

  let onTouche = null;
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (onTouche) onTouche(e);
  });

  function lire(cle, defaut) {
    try { return JSON.parse(localStorage.getItem(cle)) || defaut; } catch (e) { return defaut; }
  }
  function ecrire(cle, valeur) {
    try { localStorage.setItem(cle, JSON.stringify(valeur)); } catch (e) {}
  }

  const reglages = Object.assign({ portee: "tous", mode: "mixte", nombre: "10" }, lire("langue-reglages", {}));
  if (zone.dataset.point) reglages.portee = "point:" + zone.dataset.point;

  const titreDuPoint = (e) => (points.find((p) => p.id === e.point_id) || {}).titre || "";

  // ---------- Affichage d'une phrase à trous ----------
  function phrase(e, remplie) {
    const parts = e.phrase.split("____");
    const trou = remplie
      ? el("span", { class: "trou rempli" }, e.reponse)
      : el("span", { class: "trou" }, "      ");
    return el("div", { class: "phrase grec" }, parts[0], trou, parts[1] || "");
  }

  function entete(i, total) {
    return el("div", { class: "rev-entete" },
      el("span", {}, "Phrase " + (i + 1) + " / " + total),
      el("div", { class: "barre" }, el("div", { class: "barre-remplie", style: "width:" + Math.round((i / total) * 100) + "%" })),
      el("button", { class: "lien-bouton", type: "button", onclick: menu }, "Quitter"));
  }

  function enonce(e) {
    return el("div", { class: "question" },
      el("div", { class: "consigne" }, el("span", { class: "badge" }, titreDuPoint(e))),
      phrase(e, false),
      e.indice ? el("div", { class: "indice" }, "→ " + e.indice) : null);
  }

  // ---------- Correction ----------
  function correction(e, ok, message, suite, supprimer) {
    let passe = false;
    const go = () => { if (passe) return; passe = true; suite(); };
    const suivant = el("button", { class: "btn-principal", type: "button", onclick: go }, "Suivant (Entrée)");
    const signaler = el("button", { class: "lien-bouton", type: "button" }, "Cet exercice est faux ? Le supprimer");
    signaler.addEventListener("click", () => {
      if (passe) return;
      passe = true;
      supprimer();
    });

    zone.append(
      el("div", { class: "feedback " + (ok ? "ok" : "ko") },
        el("strong", {}, message),
        phrase(e, true),
        e.traduction ? el("div", { class: "details-doux" }, "« " + e.traduction + " »") : null,
        e.explication ? el("div", {}, e.explication) : null),
      el("div", { class: "fin-actions" }, suivant), el("p", { class: "centre" }, signaler));
    suivant.focus();
    onTouche = (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } };
  }

  function supprimerSurServeur(e) {
    const url = zone.dataset.supprimer.replace("/0/", "/" + e.id + "/");
    return fetch(url, { method: "POST" }).catch(() => {});
  }

  // ---------- Fin de série ----------
  function fin(resultats, relancer) {
    onTouche = null;
    vider();
    const bons = resultats.filter((r) => r.ok).length;
    const rates = resultats.filter((r) => !r.ok);
    const part = resultats.length ? bons / resultats.length : 0;
    const phraseFin = part === 1 ? "Parfait !" : part >= 0.7 ? "Très bien !" : part >= 0.4 ? "C'est un début, continue !" : "Courage, ça rentrera avec la répétition.";

    zone.append(
      el("div", { class: "fin" },
        el("h2", {}, "Série terminée"),
        el("p", { class: "score" }, bons + " / " + resultats.length),
        el("p", {}, phraseFin)),
      rates.length ? el("div", {},
        el("h3", {}, "À revoir"),
        el("div", { class: "liste-ratees" }, rates.map((r) =>
          el("div", { class: "details" }, phrase(r.e, true), el("div", { class: "details-doux" }, r.e.explication || ""))))) : null,
      el("div", { class: "fin-actions" },
        rates.length ? el("button", { class: "btn-principal", type: "button", onclick: () => relancer(rates.map((r) => r.e)) }, "Rejouer les phrases ratées") : null,
        el("button", { class: rates.length ? "btn-secondaire" : "btn-principal", type: "button", onclick: () => relancer(melanger(resultats.map((r) => r.e))) }, "Recommencer"),
        el("button", { class: "btn-secondaire", type: "button", onclick: menu }, "Menu"),
        el("a", { class: "btn-secondaire lien", href: URL_LANGUE }, "Mes points")));
  }

  // ---------- Série d'exercices ----------
  function session(liste, relancer) {
    const file = liste.slice(), res = [];
    let i = 0;

    function suivante() {
      if (i >= file.length) return fin(res, relancer);
      const e = file[i];
      const choix = reglages.mode === "choix" || (reglages.mode === "mixte" && Math.random() < 0.5);
      if (choix && e.distracteurs.length >= 2) questionChoix(e);
      else questionSaisie(e);
    }

    function apres(e, ok, message) {
      correction(e, ok, message,
        () => { res.push({ e, ok }); i++; suivante(); },
        () => {
          supprimerSurServeur(e);
          tous.splice(tous.indexOf(e), 1);
          file.splice(i, 1);
          suivante();
        });
    }

    function questionSaisie(e) {
      vider();
      zone.append(entete(i, file.length), enonce(e));

      const champ = el("input", { type: "text", class: "grec", autocomplete: "off", autocapitalize: "off", spellcheck: "false", placeholder: "Ta réponse en grec" });
      const valider = el("button", { class: "btn-principal", type: "submit" }, "Valider");
      const nesaispas = el("button", { class: "btn-secondaire", type: "button" }, "Je ne sais pas");
      const form = el("form", { class: "saisie" }, champ, el("div", { class: "fin-actions" }, valider, nesaispas));
      zone.append(form);
      champ.focus();

      function conclure(ok, message) {
        champ.disabled = valider.disabled = nesaispas.disabled = true;
        apres(e, ok, message);
      }

      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const v = champ.value.trim();
        if (!v) return;
        const acceptees = [e.reponse].concat(e.autres);
        const ok = acceptees.some((a) => norm(a) === norm(v));
        const exact = acceptees.some((a) => a.normalize("NFC") === v.normalize("NFC"));
        conclure(ok, ok ? (exact ? "Correct !" : "Correct, mais attention aux accents et aux esprits !") : "Pas tout à fait.");
      });
      nesaispas.addEventListener("click", () => conclure(false, "Pas de souci, voici la réponse :"));
    }

    function questionChoix(e) {
      vider();
      zone.append(entete(i, file.length), enonce(e));

      const options = melanger([{ t: e.reponse, juste: true }].concat(e.distracteurs.slice(0, 3).map((t) => ({ t, juste: false }))));
      let repondu = false;

      function choisir(k) {
        if (repondu) return;
        repondu = true;
        boutons.forEach((b, j) => {
          b.disabled = true;
          if (options[j].juste) b.classList.add("juste");
          else if (j === k) b.classList.add("faux");
        });
        apres(e, options[k].juste, options[k].juste ? "Correct !" : "Pas tout à fait.");
      }

      const boutons = options.map((opt, k) =>
        el("button", { class: "option grec", type: "button", onclick: () => choisir(k) },
          el("span", { class: "num" }, String(k + 1)), opt.t));
      zone.append(el("div", { class: "options" }, boutons));

      onTouche = (ev) => {
        const k = parseInt(ev.key, 10) - 1;
        if (k >= 0 && k < options.length) choisir(k);
      };
    }

    suivante();
  }

  // ---------- Menu ----------
  function choisis() {
    const p = reglages.portee;
    if (p.startsWith("cat:")) {
      const ids = new Set(points.filter((x) => x.categorie === p.slice(4)).map((x) => x.id));
      return tous.filter((e) => ids.has(e.point_id));
    }
    if (p.startsWith("point:")) return tous.filter((e) => String(e.point_id) === p.slice(6));
    return tous;
  }

  function champSelect(label, options, courant, surChangement) {
    const s = el("select", {}, options.map(([v, t]) => { const o = el("option", { value: v }, t); if (v === courant) o.selected = true; return o; }));
    s.addEventListener("change", () => surChangement(s.value));
    return el("label", { class: "rev-champ" }, el("span", {}, label), s);
  }

  function menu() {
    onTouche = null;
    vider();

    if (!tous.length) {
      zone.append(el("p", { class: "vide" }, "Aucun exercice pour l'instant : ajoute un point de cours, puis clique sur « Générer des exercices »."),
        el("p", { class: "centre" }, el("a", { class: "btn-principal lien", href: URL_LANGUE }, "Aller à mes points de langue")));
      return;
    }

    const options = [["tous", "Tous mes points (" + tous.length + " exercices)"]];
    const categories = [...new Set(points.map((p) => p.categorie))];
    categories.forEach((c) => {
      const n = tous.filter((e) => (points.find((p) => p.id === e.point_id) || {}).categorie === c).length;
      if (n) options.push(["cat:" + c, "Type : " + c + " (" + n + ")"]);
    });
    points.forEach((p) => {
      const n = tous.filter((e) => e.point_id === p.id).length;
      if (n) options.push(["point:" + p.id, "Point : " + p.titre + " (" + n + ")"]);
    });
    if (!options.some(([v]) => v === reglages.portee)) reglages.portee = "tous";

    const maj = (cle) => (v) => { reglages[cle] = v; ecrire("langue-reglages", reglages); menu(); };
    const message = el("p", { class: "erreur cache" });

    zone.append(
      el("h2", {}, "Que veux-tu réviser ?"),
      el("div", { class: "rev-reglages" },
        champSelect("Quoi réviser", options, reglages.portee, maj("portee")),
        champSelect("Façon de répondre", [["mixte", "Mixte"], ["saisie", "Je tape la réponse"], ["choix", "Choix multiple"]], reglages.mode, maj("mode")),
        champSelect("Nombre", [["5", "5"], ["10", "10"], ["20", "20"], ["tous", "Tous"]], reglages.nombre, maj("nombre"))),
      message,
      el("button", {
        class: "btn-principal grand", type: "button",
        onclick: () => {
          const sel = choisis();
          if (!sel.length) { message.textContent = "Aucun exercice ne correspond à ce choix."; message.classList.remove("cache"); return; }
          let jeu = melanger(sel);
          if (reglages.nombre !== "tous") jeu = jeu.slice(0, parseInt(reglages.nombre, 10));
          const lancer = (liste) => session(liste, lancer);
          lancer(jeu);
        },
      }, "Commencer"),
      el("p", { class: "centre details-doux" }, "Les exercices sont écrits par une IA : si une phrase te semble fausse, supprime-la pendant la correction."));
  }

  menu();
})();
