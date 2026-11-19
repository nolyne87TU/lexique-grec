"""Étape 3 (version plan de travail) : le site du lexique (Flask).

Lancement :  flask run --debug
Puis ouvre http://127.0.0.1:5000 dans ton navigateur.
"""

import json
import re
import unicodedata

from datetime import date

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

import database
import langue
from fiche import generer_fiche

app = Flask(__name__)
app.secret_key = "lexique-grec-local"  # sert uniquement aux messages affichés après une action
database.init_db()
langue.init_langue()

# Lettres grecques : bloc de base + bloc des caractères accentués (grec polytonique)
LETTRES_GRECQUES = re.compile(r"[Ͱ-Ͽἀ-῿]")
LONGUEUR_MAX = 40


def verifier_saisie(mot: str) -> str | None:
    """Renvoie un message d'erreur si la saisie est invalide, sinon None."""
    if not mot:
        return "Écris un mot grec avant de lancer la recherche."
    if len(mot) > LONGUEUR_MAX:
        return "Ce mot est trop long : écris un seul mot grec."
    if " " in mot:
        return "Écris un seul mot à la fois."
    if not LETTRES_GRECQUES.search(mot):
        return "Ce mot ne contient pas de lettres grecques."
    return None


def cle_alphabetique(mot: str) -> str:
    """Clé de tri dans l'ordre de l'alphabet grec : sans accents ni esprits."""
    decompose = unicodedata.normalize("NFD", mot)
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return sans_accents.lower().replace("ς", "σ")


def afficher_plan(erreur=None, mot="", nouveau=None, statut=200):
    """Affiche le plan de travail avec tous les mots enregistrés."""
    mots = sorted(database.lister_mots(), key=lambda m: cle_alphabetique(m["mot"]))
    nb_verifiees = sum(1 for m in mots if m["verifie"])
    page = render_template("index.html", mots=mots, erreur=erreur, mot=mot, nouveau=nouveau,
                           nb_verifiees=nb_verifiees)
    return page, statut


@app.route("/")
def accueil():
    nouveau = database.normaliser(request.args.get("nouveau", ""))
    return afficher_plan(nouveau=nouveau or None)


@app.route("/recherche", methods=["POST"])
def recherche():
    mot = database.normaliser(request.form.get("mot", ""))
    erreur = verifier_saisie(mot)
    if erreur:
        return afficher_plan(erreur=erreur, mot=mot, statut=400)

    # 1. Le mot est-il déjà sur le plan de travail ?
    fiche = database.chercher_mot(mot)

    # 2. Sinon on demande à l'IA, puis on l'enregistre
    if fiche is None:
        try:
            fiche = generer_fiche(mot)
        except json.JSONDecodeError:
            erreur = "L'IA n'a pas renvoyé une réponse lisible. Réessaie dans un instant."
            return afficher_plan(erreur=erreur, mot=mot, statut=502)
        except Exception:
            erreur = "Impossible de joindre l'IA pour le moment. Vérifie ta connexion et ta clé d'API."
            return afficher_plan(erreur=erreur, mot=mot, statut=502)

        if "erreur" in fiche:
            return afficher_plan(erreur=fiche["erreur"], mot=mot, statut=422)

        database.ajouter_mot(fiche)

    # 3. On revient au plan de travail, où la carte du mot est mise en évidence
    mot_final = database.normaliser(fiche.get("mot") or mot)
    return redirect(url_for("accueil", nouveau=mot_final) + "#plan")


@app.route("/fiche/<mot>")
def fiche(mot):
    resultat = database.chercher_mot(mot)
    if resultat is None:
        return afficher_plan(erreur="Ce mot n'est pas encore dans ton lexique.", statut=404)
    return render_template("fiche.html", fiche=resultat, diffs=database.differences(resultat))


@app.route("/revision")
def revision():
    """Page de révision : les mots sont envoyés au navigateur, qui anime les jeux."""
    champs = ("mot", "translitteration", "nature", "genre", "genitif", "traductions",
              "etymologie", "champ_lexical", "derives_francais", "verifie")
    donnees = [{c: m.get(c) for c in champs} for m in database.lister_mots()]
    return render_template("revision.html", mots=donnees)


# ---------- Section « Langue » : points de cours et phrases à trous ----------
SUGGESTIONS = [
    "L'aoriste sigmatique", "L'aoriste second", "L'imparfait", "Le parfait", "Le futur",
    "Les verbes contractes", "Le présent de λύω", "L'optatif", "Le subjonctif", "L'impératif",
    "Le participe", "L'infinitif", "La voix moyenne", "La voix passive",
    "La première déclinaison", "La deuxième déclinaison", "La troisième déclinaison",
    "Les adjectifs", "Les comparatifs", "Les pronoms relatifs", "Le génitif absolu", "Le datif",
]


@app.route("/langue")
def langue_accueil():
    points = langue.lister_points()
    groupes = [(c, [p for p in points if p["categorie"] == c]) for c in langue.CATEGORIES]
    groupes = [(c, liste) for c, liste in groupes if liste]
    return render_template(
        "langue.html", groupes=groupes, nb_points=len(points),
        total_exos=sum(p["nb"] for p in points),
        categories=langue.CATEGORIES, suggestions=SUGGESTIONS, nb_defaut=langue.NB_PAR_DEFAUT,
    )


@app.route("/langue/ajouter", methods=["POST"])
def ajouter_point():
    titre = request.form.get("titre", "").strip()
    categorie = request.form.get("categorie", "")
    notes = request.form.get("notes", "").strip()

    if not titre or len(titre) > 120:
        flash("Écris le nom du point de cours (120 caractères maximum).", "erreur")
    elif categorie not in langue.CATEGORIES:
        flash("Choisis un type valide.", "erreur")
    elif len(notes) > 2000:
        flash("Tes notes sont trop longues (2000 caractères maximum).", "erreur")
    elif langue.ajouter_point(titre, categorie, notes):
        flash(f"Point « {titre} » ajouté. Génère maintenant ses exercices.", "info")
    else:
        flash("Ce point existe déjà.", "erreur")
    return redirect(url_for("langue_accueil"))


def retour_apres_action(id):
    """Revient sur la page de cours si l'action vient de là, sinon sur la liste des points."""
    if request.form.get("retour") == "point":
        return redirect(url_for("point_detail", id=id))
    return redirect(url_for("langue_accueil"))


@app.route("/langue/<int:id>/generer", methods=["POST"])
def generer_exercices_point(id):
    point = langue.lire_point(id)
    if point is None:
        flash("Ce point n'existe pas.", "erreur")
        return redirect(url_for("langue_accueil"))

    try:
        exercices = langue.generer_exercices(point, database.lister_mots())
    except json.JSONDecodeError:
        flash("L'IA n'a pas renvoyé une réponse lisible. Réessaie dans un instant.", "erreur")
        return retour_apres_action(id)
    except Exception:
        flash("Impossible de joindre l'IA pour le moment. Vérifie ta connexion et ta clé d'API.", "erreur")
        return retour_apres_action(id)

    ajoutes = langue.ajouter_exercices(id, exercices)
    if ajoutes:
        flash(f"{ajoutes} exercice(s) ajouté(s) à « {point['titre']} ». Pense à les relire d'un œil critique.", "info")
    else:
        flash("L'IA n'a pas produit d'exercice utilisable cette fois. Réessaie.", "erreur")
    return retour_apres_action(id)


@app.route("/langue/<int:id>/supprimer", methods=["POST"])
def supprimer_point(id):
    langue.supprimer_point(id)
    flash("Point supprimé.", "info")
    return redirect(url_for("langue_accueil"))


@app.route("/langue/exercices")
def exercices():
    points = [{"id": p["id"], "titre": p["titre"], "categorie": p["categorie"]} for p in langue.lister_points()]
    exos = [{c: e[c] for c in ("id", "point_id", "phrase", "reponse", "autres", "indice",
                               "traduction", "explication", "distracteurs")}
            for e in langue.lister_exercices()]
    return render_template("langue_exercices.html", donnees={"points": points, "exercices": exos},
                           point_initial=request.args.get("point", ""))


@app.route("/langue/exercice/<int:id>/supprimer", methods=["POST"])
def supprimer_exercice(id):
    langue.supprimer_exercice(id)
    return jsonify(ok=True)


@app.route("/langue/<int:id>")
def point_detail(id):
    point = langue.lire_point(id)
    if point is None:
        flash("Ce point n'existe pas.", "erreur")
        return redirect(url_for("langue_accueil"))
    return render_template("point.html", point=point, exercices=langue.exercices_du_point(id),
                           nb_defaut=langue.NB_PAR_DEFAUT)


@app.route("/langue/<int:id>/notes", methods=["POST"])
def enregistrer_notes(id):
    if langue.lire_point(id) is None:
        return redirect(url_for("langue_accueil"))
    notes = request.form.get("notes", "").strip()
    if len(notes) > 2000:
        flash("Tes notes sont trop longues (2000 caractères maximum).", "erreur")
    else:
        langue.modifier_notes(id, notes)
        flash("Notes enregistrées.", "info")
    return redirect(url_for("point_detail", id=id))


@app.route("/langue/<int:id>/cours", methods=["POST"])
def generer_cours_point(id):
    point = langue.lire_point(id)
    if point is None:
        return redirect(url_for("langue_accueil"))
    try:
        cours = langue.generer_cours(point)
    except json.JSONDecodeError:
        flash("L'IA n'a pas renvoyé une réponse lisible. Réessaie dans un instant.", "erreur")
        return redirect(url_for("point_detail", id=id))
    except Exception:
        flash("Impossible de joindre l'IA pour le moment. Vérifie ta connexion et ta clé d'API.", "erreur")
        return redirect(url_for("point_detail", id=id))

    if cours is None:
        flash("L'IA n'a pas produit de rappel utilisable cette fois. Réessaie.", "erreur")
    else:
        langue.enregistrer_cours(id, cours)
        flash("Rappel de cours créé. Compare-le avec ton cours avant de t'y fier.", "info")
    return redirect(url_for("point_detail", id=id))


# ---------- Vérification des fiches ----------
CHAMPS_LEXICAUX = ["langage", "pensée", "politique", "guerre", "religion", "nature", "corps",
                   "famille", "société", "morale", "temps", "espace", "art", "autre"]
NATURES = ["nom commun", "nom propre", "verbe", "adjectif", "adverbe", "préposition",
           "conjonction", "pronom", "particule", "article"]


@app.template_filter("date_fr")
def date_fr(valeur):
    """2026-11-19 -> 19/11/2026"""
    try:
        return date.fromisoformat(valeur).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valeur or ""


def liste_depuis_texte(texte: str) -> list[str]:
    morceaux = re.split(r"[,;]", texte or "")
    return [m.strip()[:80] for m in morceaux if m.strip()][:10]


@app.route("/fiche/<mot>/verifier", methods=["GET", "POST"])
def verifier_fiche(mot):
    actuelle = database.chercher_mot(mot)
    if actuelle is None:
        return redirect(url_for("accueil"))

    valeurs, erreur = dict(actuelle), None
    if request.method == "POST":
        f = request.form
        nouveaux = {
            "nature": f.get("nature", "").strip()[:60],
            "genre": f.get("genre", "").strip()[:30] or None,
            "genitif": f.get("genitif", "").strip()[:60] or None,
            "forme_de_base": f.get("forme_de_base", "").strip()[:60] or None,
            "traductions": liste_depuis_texte(f.get("traductions", "")),
            "etymologie": f.get("etymologie", "").strip()[:500] or None,
            "champ_lexical": f.get("champ_lexical", "").strip()[:40] or None,
            "derives_francais": liste_depuis_texte(f.get("derives_francais", "")),
        }
        note = f.get("note", "").strip()[:1000]
        verifie = f.get("verifie") == "oui"
        valeurs.update(nouveaux)
        valeurs["note_verif"] = note

        if not nouveaux["nature"]:
            erreur = "Indique la nature du mot."
        elif not nouveaux["traductions"]:
            erreur = "Indique au moins une traduction."
        else:
            database.enregistrer_verification(actuelle["mot"], nouveaux, verifie, note)
            flash("Fiche enregistrée." + (" Elle est marquée comme vérifiée." if verifie else ""), "info")
            return redirect(url_for("fiche", mot=actuelle["mot"]))

    return render_template("verifier.html", fiche=actuelle, f=valeurs, erreur=erreur,
                           champs=CHAMPS_LEXICAUX, natures=NATURES), (400 if erreur else 200)


@app.route("/fiche/<mot>/statut", methods=["POST"])
def statut_fiche(mot):
    if database.chercher_mot(mot) is not None:
        verifie = request.form.get("action") == "verifier"
        database.changer_statut(mot, verifie)
        flash("Fiche marquée comme vérifiée." if verifie else "Statut de vérification retiré.", "info")
    return redirect(url_for("fiche", mot=database.normaliser(mot)))


@app.route("/bilan")
def bilan():
    return render_template("bilan.html", b=database.bilan())
