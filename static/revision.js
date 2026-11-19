// Mode révision : flashcards, quiz, écriture, associations, quiz de grammaire.
(function () {
  "use strict";

  const donnees = JSON.parse(document.getElementById("donnees").textContent);
  const zone = document.getElementById("revision");
  const URL_ACCUEIL = zone.dataset.accueil;

  const NATURES = ["nom commun", "verbe", "adjectif", "adverbe", "préposition", "conjonction", "pronom", "particule", "article"];
  const CHAMPS = ["langage", "pensée", "politique", "guerre", "religion", "nature", "corps", "famille", "société", "morale", "temps", "espace", "art", "autre"];

  const MODES = [
    { id: "flashcards", nom: "Flashcards", desc: "Retourne la carte, puis dis si tu savais.", direction: true },
    { id: "qcm", nom: "Quiz à choix multiples", desc: "Trouve la bonne réponse parmi 4 propositions.", direction: true },
    { id: "saisie", nom: "Écriture", desc: "Écris toi-même la réponse.", direction: true },
    { id: "associations", nom: "Associations", desc: "Relie chaque mot grec à son sens.", direction: false },
    { id: "grammaire", nom: "Quiz de grammaire", desc: "Classe grammaticale et champ lexical.", direction: false },
  ];

  // ---------- Outils ----------
  const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/ς/g, "σ").trim();
  const majuscule = (s) => (s || "").charAt(0).toUpperCase() + (s || "").slice(1);
  const sensDe = (m) => (m.traductions || []).join(", ");
  const unAuHasard = (liste) => liste[Math.floor(Math.random() * liste.length)];

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

  // Raccourcis clavier de l'écran en cours
  let onTouche = null;
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (onTouche) onTouche(e);
  });

  // ---------- Mémoire du navigateur : mots ratés et réglages ----------
  function lire(cle, defaut) {
    try { return JSON.parse(localStorage.getItem(cle)) || defaut; } catch (e) { return defaut; }
  }
  function ecrire(cle, valeur) {
    try { localStorage.setItem(cle, JSON.stringify(valeur)); } catch (e) {}
  }
  function noter(mot, ok) {
    const d = lire("revision-erreurs", {});
    d[mot] = Math.max(0, (d[mot] || 0) + (ok ? -1 : 1));
    if (d[mot] === 0) delete d[mot];
    ecrire("revision-erreurs", d);
  }

  const reglages = Object.assign({ mode: "flashcards", filtre: "tous", direction: "gf", nombre: "10" }, lire("revision-reglages", {}));
  if (!MODES.some((m) => m.id === reglages.mode)) reglages.mode = "flashcards";

  // ---------- Éléments communs ----------
  function entete(i, total, etiquette) {
    return el("div", { class: "rev-entete" },
      el("span", {}, (etiquette || "Question") + " " + (i + 1) + " / " + total),
      el("div", { class: "barre" }, el("div", { class: "barre-remplie", style: "width:" + Math.round((i / total) * 100) + "%" })),
      el("button", { class: "lien-bouton", type: "button", onclick: menu }, "Quitter"));
  }

  function details(m) {
    const ligne = [m.nature, m.genre, m.genitif ? "gén. " + m.genitif : null].filter(Boolean).join(" · ");
    return el("div", { class: "details" },
      el("div", { class: "details-grec grec" }, m.mot, el("span", { class: "translit" }, " (" + (m.translitteration || "") + ")")),
      el("div", {}, sensDe(m)),
      ligne ? el("div", { class: "details-doux" }, ligne) : null,
      m.champ_lexical ? el("div", {}, el("span", { class: "badge badge-champ" }, m.champ_lexical)) : null,
      (m.derives_francais || []).length ? el("div", { class: "details-doux" }, "Dérivés : " + m.derives_francais.join(", ")) : null,
      m.etymologie ? el("div", { class: "details-doux" }, "Étymologie : " + m.etymologie) : null);
  }

  // Message de correction + bouton « Suivant »
  function apresReponse(ok, m, suite, message) {
    let passe = false;
    const go = () => { if (passe) return; passe = true; suite(); };
    const suivant = el("button", { class: "btn-principal", type: "button", onclick: go }, "Suivant (Entrée)");
    zone.append(el("div", { class: "feedback " + (ok ? "ok" : "ko") },
      el("strong", {}, message || (ok ? "Correct !" : "Pas tout à fait.")),
      details(m)), suivant);
    suivant.focus();
    onTouche = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } };
  }

  function fin(resultats, relancer) {
    onTouche = null;
    vider();
    const bons = resultats.filter((r) => r.ok).length;
    const rates = resultats.filter((r) => !r.ok);
    const part = resultats.length ? bons / resultats.length : 0;
    const phrase = part === 1 ? "Parfait !" : part >= 0.7 ? "Très bien !" : part >= 0.4 ? "C'est un début, continue !" : "Courage, ça rentrera avec la répétition.";

    zone.append(
      el("div", { class: "fin" },
        el("h2", {}, "Série terminée"),
        el("p", { class: "score" }, bons + " / " + resultats.length),
        el("p", {}, phrase)),
      rates.length ? el("div", {},
        el("h3", {}, "À revoir"),
        el("div", { class: "liste-ratees" }, rates.map((r) => details(r.m)))) : null,
      el("div", { class: "fin-actions" },
        rates.length ? el("button", { class: "btn-principal", type: "button", onclick: () => relancer(rates.map((r) => r.m)) }, "Rejouer les mots ratés") : null,
        el("button", { class: rates.length ? "btn-secondaire" : "btn-principal", type: "button", onclick: () => relancer(melanger(resultats.map((r) => r.m))) }, "Recommencer"),
        el("button", { class: "btn-secondaire", type: "button", onclick: menu }, "Menu")));
  }

  const sensDirect = (dir) => (dir === "mixte" ? Math.random() < 0.5 : dir === "gf"); // true : grec → français

  // ---------- Mode 1 : flashcards ----------
  function flashcards(mots, dir, relancer) {
    const file = melanger(mots), res = [];
    let i = 0;

    function repondre(ok) {
      noter(file[i].mot, ok);
      res.push({ m: file[i], ok });
      i++;
      suivante();
    }

    function suivante() {
      if (i >= file.length) return fin(res, relancer);
      const m = file[i], gf = sensDirect(dir);
      let retournee = false;
      vider();
      zone.append(entete(i, file.length, "Carte"));

      const recto = gf ? el("div", { class: "fc-grand grec" }, m.mot) : el("div", { class: "fc-grand" }, sensDe(m));
      const carte = el("button", { class: "flashcard", type: "button" }, recto, el("div", { class: "fc-aide" }, "Clique pour retourner (Espace)"));
      const actions = el("div", { class: "fc-actions cache" },
        el("button", { class: "btn-revoir", type: "button", onclick: () => repondre(false) }, "À revoir (1)"),
        el("button", { class: "btn-sais", type: "button", onclick: () => repondre(true) }, "Je sais (2)"));

      function retourner() {
        if (retournee) return;
        retournee = true;
        carte.classList.add("retournee");
        carte.replaceChildren(details(m));
        actions.classList.remove("cache");
      }

      carte.addEventListener("click", retourner);
      zone.append(carte, actions);
      onTouche = (e) => {
        if (e.key === " " || e.key === "Enter") { e.preventDefault(); retourner(); }
        else if (retournee && (e.key === "1" || e.key === "ArrowLeft")) repondre(false);
        else if (retournee && (e.key === "2" || e.key === "ArrowRight")) repondre(true);
      };
    }
    suivante();
  }

  // ---------- Choix multiple (utilisé par le quiz et la grammaire) ----------
  function choixMultiple(o) {
    vider();
    zone.append(entete(o.index, o.total), el("div", { class: "question" }, o.question));

    const options = melanger([{ t: o.bonne, juste: true }].concat(o.autres.map((t) => ({ t, juste: false }))));
    let repondu = false;

    function choisir(k) {
      if (repondu) return;
      repondu = true;
      boutons.forEach((b, j) => {
        b.disabled = true;
        if (options[j].juste) b.classList.add("juste");
        else if (j === k) b.classList.add("faux");
      });
      noter(o.m.mot, options[k].juste);
      apresReponse(options[k].juste, o.m, () => o.suite(options[k].juste));
    }

    const boutons = options.map((opt, k) =>
      el("button", { class: "option" + (o.grec ? " grec" : ""), type: "button", onclick: () => choisir(k) },
        el("span", { class: "num" }, String(k + 1)), opt.t));
    zone.append(el("div", { class: "options" }, boutons));

    onTouche = (e) => {
      const k = parseInt(e.key, 10) - 1;
      if (k >= 0 && k < options.length) choisir(k);
    };
  }

  // ---------- Mode 2 : quiz à choix multiples ----------
  function qcm(mots, dir, relancer) {
    const file = mots, res = [];
    let i = 0;

    function suivante() {
      if (i >= file.length) return fin(res, relancer);
      const m = file[i], gf = sensDirect(dir);
      const autres = melanger(donnees.filter((d) => d.mot !== m.mot));
      let bonne, mauvaises = [];

      if (gf) {
        bonne = unAuHasard(m.traductions);
        const vus = new Set(m.traductions.map(norm));
        for (const d of autres) {
          const t = unAuHasard(d.traductions);
          if (!vus.has(norm(t))) { vus.add(norm(t)); mauvaises.push(t); }
          if (mauvaises.length === 3) break;
        }
      } else {
        bonne = m.mot;
        mauvaises = autres.slice(0, 3).map((d) => d.mot);
      }
      if (!mauvaises.length) { i++; return suivante(); }

      const question = gf
        ? [el("div", { class: "consigne" }, "Que signifie ce mot ?"), el("div", { class: "fc-grand grec" }, m.mot), el("div", { class: "fc-aide" }, m.translitteration)]
        : [el("div", { class: "consigne" }, "Quel est le mot grec ?"), el("div", { class: "fc-grand" }, sensDe(m))];

      choixMultiple({
        index: i, total: file.length, question, bonne, autres: mauvaises, m, grec: !gf,
        suite: (ok) => { res.push({ m, ok }); i++; suivante(); },
      });
    }
    suivante();
  }

  // ---------- Mode 3 : écriture ----------
  function sansArticle(s) {
    return norm(s).replace(/^(le |la |les |l'|l’|un |une |des |du |de |d'|d’)/, "");
  }

  function saisie(mots, dir, relancer) {
    const file = mots, res = [];
    let i = 0;

    function suivante() {
      if (i >= file.length) return fin(res, relancer);
      const m = file[i], gf = sensDirect(dir);
      vider();
      zone.append(entete(i, file.length));

      const indice = [m.nature, m.genre].filter(Boolean).join(" · ");
      zone.append(el("div", { class: "question" },
        el("div", { class: "consigne" }, gf ? "Écris la traduction française :" : "Écris le mot grec :"),
        gf ? el("div", { class: "fc-grand grec" }, m.mot) : el("div", { class: "fc-grand" }, sensDe(m)),
        gf ? el("div", { class: "fc-aide" }, m.translitteration) : el("div", { class: "fc-aide" }, "Indice : " + indice + (m.translitteration ? " · " + m.translitteration : ""))));

      const champ = el("input", { type: "text", class: gf ? "" : "grec", autocomplete: "off", autocapitalize: "off", spellcheck: "false", placeholder: gf ? "Ta réponse en français" : "Ta réponse en grec" });
      const valider = el("button", { class: "btn-principal", type: "submit" }, "Valider");
      const nesaispas = el("button", { class: "btn-secondaire", type: "button" }, "Je ne sais pas");
      const form = el("form", { class: "saisie" }, champ, el("div", { class: "fin-actions" }, valider, nesaispas));
      zone.append(form);
      champ.focus();

      function conclure(ok, message) {
        champ.disabled = valider.disabled = nesaispas.disabled = true;
        noter(m.mot, ok);
        apresReponse(ok, m, () => { res.push({ m, ok }); i++; suivante(); }, message);
      }

      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const v = champ.value.trim();
        if (!v) return;
        let ok, message = null;
        if (gf) {
          ok = m.traductions.some((t) => sansArticle(t) === sansArticle(v));
        } else {
          ok = norm(v) === norm(m.mot);
          if (ok && v.normalize("NFC") !== m.mot.normalize("NFC")) message = "Correct, mais attention aux accents et aux esprits !";
        }
        conclure(ok, message);
      });
      nesaispas.addEventListener("click", () => conclure(false, "Pas de souci, la voici :"));
    }
    suivante();
  }

  // ---------- Mode 4 : associations ----------
  function associations(mots, dir, relancer) {
    const res = [], echecs = new Set();
    const lots = [];
    for (let k = 0; k < mots.length; k += 6) lots.push(mots.slice(k, k + 6));
    if (lots.length > 1 && lots[lots.length - 1].length < 3) lots[lots.length - 2] = lots[lots.length - 2].concat(lots.pop());
    let n = 0;

    function lot() {
      if (n >= lots.length) return fin(res, relancer);
      onTouche = null;

      // Chaque mot reçoit une traduction différente de celles des autres, pour éviter les ambiguïtés
      const utilisees = new Set(), paires = [];
      lots[n].forEach((m) => {
        const t = m.traductions.find((x) => !utilisees.has(norm(x)));
        if (t) { utilisees.add(norm(t)); paires.push({ m, t }); }
      });

      vider();
      zone.append(entete(n, lots.length, "Série"), el("div", { class: "consigne centre" }, "Clique un mot grec, puis son sens."));

      let selG = null, selD = null, restantes = paires.length;

      function verifier() {
        const g = selG, d = selD;
        selG = selD = null;
        if (g.p === d.p) {
          [g.b, d.b].forEach((x) => { x.classList.remove("sel"); x.classList.add("juste"); x.disabled = true; });
          const ok = !echecs.has(g.p.m.mot);
          if (ok) noter(g.p.m.mot, true);
          res.push({ m: g.p.m, ok });
          restantes--;
          if (restantes === 0) setTimeout(() => { n++; lot(); }, 700);
        } else {
          if (!echecs.has(g.p.m.mot)) noter(g.p.m.mot, false);
          echecs.add(g.p.m.mot);
          [g.b, d.b].forEach((x) => x.classList.add("faux"));
          setTimeout(() => [g.b, d.b].forEach((x) => x.classList.remove("faux", "sel")), 450);
        }
      }

      function clic(cote, p, b) {
        if (b.disabled || b.classList.contains("faux")) return;
        if (cote === "g") { if (selG) selG.b.classList.remove("sel"); selG = { p, b }; }
        else { if (selD) selD.b.classList.remove("sel"); selD = { p, b }; }
        b.classList.add("sel");
        if (selG && selD) verifier();
      }

      const carte = (texte, cls, cote, p) => {
        const b = el("button", { class: "assoc-item " + cls, type: "button" }, texte);
        b.addEventListener("click", () => clic(cote, p, b));
        return b;
      };

      zone.append(el("div", { class: "assoc" },
        el("div", { class: "assoc-col" }, melanger(paires).map((p) => carte(p.m.mot, "grec", "g", p))),
        el("div", { class: "assoc-col" }, melanger(paires).map((p) => carte(p.t, "", "d", p)))));
    }
    lot();
  }

  // ---------- Mode 5 : quiz de grammaire ----------
  function grammaire(mots, dir, relancer) {
    const file = mots.filter((m) => m.nature || m.champ_lexical), res = [];
    let i = 0;
    if (!file.length) return menu();

    function suivante() {
      if (i >= file.length) return fin(res, relancer);
      const m = file[i];
      const types = [m.nature ? "nature" : null, m.champ_lexical ? "champ" : null].filter(Boolean);
      const type = unAuHasard(types);
      const bonne = type === "nature" ? m.nature : m.champ_lexical;
      const reserve = type === "nature" ? NATURES : CHAMPS;
      const existants = donnees.map((d) => (type === "nature" ? d.nature : d.champ_lexical)).filter(Boolean);

      const vus = new Set([norm(bonne)]), mauvaises = [];
      for (const v of melanger(reserve.concat(existants))) {
        if (!vus.has(norm(v))) { vus.add(norm(v)); mauvaises.push(v); }
        if (mauvaises.length === 3) break;
      }

      choixMultiple({
        index: i, total: file.length, m,
        question: [
          el("div", { class: "consigne" }, type === "nature" ? "Quelle est la classe grammaticale de ce mot ?" : "À quel champ lexical appartient ce mot ?"),
          el("div", { class: "fc-grand grec" }, m.mot),
          el("div", { class: "fc-aide" }, (m.translitteration || "") + " — " + sensDe(m))],
        bonne: majuscule(bonne), autres: mauvaises.map(majuscule),
        suite: (ok) => { res.push({ m, ok }); i++; suivante(); },
      });
    }
    suivante();
  }

  // ---------- Menu ----------
  const JEUX = { flashcards, qcm, saisie, associations, grammaire };

  function motsFiltres() {
    const f = reglages.filtre, err = lire("revision-erreurs", {});
    if (f === "revoir") return donnees.filter((m) => err[m.mot]);
    if (f === "verifies") return donnees.filter((m) => m.verifie);
    if (f.startsWith("champ:")) return donnees.filter((m) => m.champ_lexical === f.slice(6));
    if (f.startsWith("nature:")) return donnees.filter((m) => m.nature === f.slice(7));
    return donnees;
  }

  function champSelect(label, options, courant, surChangement) {
    const s = el("select", {}, options.map(([v, t]) => { const o = el("option", { value: v }, t); if (v === courant) o.selected = true; return o; }));
    s.addEventListener("change", () => surChangement(s.value));
    return el("label", { class: "rev-champ" }, el("span", {}, label), s);
  }

  function menu() {
    onTouche = null;
    vider();

    if (!donnees.length) {
      zone.append(el("p", { class: "vide" }, "Ton lexique est vide : ajoute d'abord quelques mots sur ton plan de travail."),
        el("p", { class: "centre" }, el("a", { class: "retour", href: URL_ACCUEIL }, "← Retour au plan de travail")));
      return;
    }

    const err = lire("revision-erreurs", {});
    const nbRevoir = donnees.filter((m) => err[m.mot]).length;
    const uniques = (cle) => [...new Set(donnees.map((m) => m[cle]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fr"));
    const compte = (cle, v) => donnees.filter((m) => m[cle] === v).length;

    const optionsFiltre = [["tous", "Tous les mots (" + donnees.length + ")"]];
    const nbVerifies = donnees.filter((m) => m.verifie).length;
    if (nbVerifies) optionsFiltre.push(["verifies", "Mots vérifiés (" + nbVerifies + ")"]);
    if (nbRevoir) optionsFiltre.push(["revoir", "Mes mots à revoir (" + nbRevoir + ")"]);
    uniques("champ_lexical").forEach((c) => optionsFiltre.push(["champ:" + c, "Champ lexical : " + c + " (" + compte("champ_lexical", c) + ")"]));
    uniques("nature").forEach((c) => optionsFiltre.push(["nature:" + c, "Classe : " + c + " (" + compte("nature", c) + ")"]));
    if (!optionsFiltre.some(([v]) => v === reglages.filtre)) reglages.filtre = "tous";

    const mode = MODES.find((m) => m.id === reglages.mode);
    const maj = (cle) => (v) => { reglages[cle] = v; ecrire("revision-reglages", reglages); menu(); };

    const message = el("p", { class: "erreur cache" });

    zone.append(
      el("h2", {}, "Choisis un mode"),
      el("div", { class: "rev-modes" }, MODES.map((md) =>
        el("button", { class: "rev-mode" + (md.id === reglages.mode ? " actif" : ""), type: "button", onclick: maj("mode").bind(null, md.id) },
          el("strong", {}, md.nom), el("span", {}, md.desc)))),
      el("div", { class: "rev-reglages" },
        champSelect("Mots à réviser", optionsFiltre, reglages.filtre, maj("filtre")),
        mode.direction ? champSelect("Sens", [["gf", "Grec → Français"], ["fg", "Français → Grec"], ["mixte", "Mixte"]], reglages.direction, maj("direction")) : null,
        champSelect("Nombre", [["5", "5"], ["10", "10"], ["20", "20"], ["tous", "Tous"]], reglages.nombre, maj("nombre"))),
      message,
      el("button", {
        class: "btn-principal grand", type: "button",
        onclick: () => {
          const sel = motsFiltres();
          let probleme = null;
          if (!sel.length) probleme = "Aucun mot ne correspond à ce choix.";
          else if (mode.id === "qcm" && donnees.length < 4) probleme = "Il faut au moins 4 mots dans ton lexique pour ce quiz.";
          else if (mode.id === "associations" && sel.length < 3) probleme = "Il faut au moins 3 mots pour ce jeu.";
          if (probleme) { message.textContent = probleme; message.classList.remove("cache"); return; }

          let jeu = melanger(sel);
          if (reglages.nombre !== "tous") jeu = jeu.slice(0, parseInt(reglages.nombre, 10));
          const lancer = (mots) => JEUX[mode.id](mots, reglages.direction, lancer);
          lancer(jeu);
        },
      }, "Commencer"));
  }

  menu();
})();
