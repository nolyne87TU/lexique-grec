// Range les cartes du plan de travail : alphabétique, par classe grammaticale ou par champ lexical.
(function () {
  const plan = document.getElementById("plan");
  if (!plan) return;

  const cartes = Array.from(plan.querySelectorAll(".carte")); // déjà triées dans l'ordre alphabétique grec
  const boutons = document.querySelectorAll(".boutons-tri button");
  if (!cartes.length) return;

  function majuscule(texte) {
    return texte.charAt(0).toUpperCase() + texte.slice(1);
  }

  function creerGrille(liste) {
    const grille = document.createElement("div");
    grille.className = "grille";
    liste.forEach((carte) => grille.appendChild(carte));
    return grille;
  }

  function afficher(mode) {
    plan.innerHTML = "";

    if (mode === "alpha") {
      plan.appendChild(creerGrille(cartes));
    } else {
      const cle = mode;  // "nature", "champ" ou "verif" : correspond à data-nature, data-champ, data-verif
      const groupes = {};
      cartes.forEach((carte) => {
        const nom = carte.dataset[cle];
        (groupes[nom] = groupes[nom] || []).push(carte);
      });

      Object.keys(groupes)
        .sort((a, b) => a.localeCompare(b, "fr"))
        .forEach((nom) => {
          const section = document.createElement("section");
          section.className = "groupe";
          const titre = document.createElement("h3");
          titre.textContent = majuscule(nom) + " (" + groupes[nom].length + ")";
          section.appendChild(titre);
          section.appendChild(creerGrille(groupes[nom]));
          plan.appendChild(section);
        });
    }

    boutons.forEach((b) => b.classList.toggle("actif", b.dataset.tri === mode));
    try { localStorage.setItem("tri-lexique", mode); } catch (e) {}
  }

  boutons.forEach((b) => b.addEventListener("click", () => afficher(b.dataset.tri)));

  let mode = "alpha";
  try { mode = localStorage.getItem("tri-lexique") || "alpha"; } catch (e) {}
  if (!["alpha", "nature", "champ", "verif"].includes(mode)) mode = "alpha";
  afficher(mode);

  // Fait défiler jusqu'à la carte du mot qui vient d'être ajouté
  const nouveau = plan.querySelector(".carte.nouveau");
  if (nouveau) nouveau.scrollIntoView({ block: "center", behavior: "smooth" });
})();
