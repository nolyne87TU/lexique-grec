"""Section « Langue » : points de cours (grammaire, conjugaison...) et phrases à trous.

Les points et les exercices sont enregistrés dans lexique.db (mêmes fichiers que le lexique).
"""

import json
import random
import re
import unicodedata

import database
from fiche import MODELE, client

CATEGORIES = ["conjugaison", "déclinaison", "grammaire", "syntaxe", "autre"]
TROU = "____"
NB_PAR_DEFAUT = 6


# ---------- Base de données ----------
def init_langue() -> None:
    with database.connexion() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre TEXT NOT NULL UNIQUE,
                categorie TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exercices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                point_id INTEGER NOT NULL,
                phrase TEXT NOT NULL,
                reponse TEXT NOT NULL,
                autres TEXT,
                indice TEXT,
                traduction TEXT,
                explication TEXT,
                distracteurs TEXT,
                UNIQUE (point_id, phrase)
            )
            """
        )
        # Mise à jour d'une base créée avant l'ajout des fiches de cours
        colonnes = [c["name"] for c in conn.execute("PRAGMA table_info(points)")]
        if "cours" not in colonnes:
            conn.execute("ALTER TABLE points ADD COLUMN cours TEXT")


def ajouter_point(titre: str, categorie: str, notes: str) -> bool:
    """Renvoie False si ce point existe déjà."""
    with database.connexion() as conn:
        curseur = conn.execute(
            "INSERT OR IGNORE INTO points (titre, categorie, notes) VALUES (?, ?, ?)",
            (titre, categorie, notes),
        )
        return curseur.rowcount > 0


def lire_point(point_id: int) -> dict | None:
    with database.connexion() as conn:
        ligne = conn.execute("SELECT * FROM points WHERE id = ?", (point_id,)).fetchone()
    if not ligne:
        return None
    point = dict(ligne)
    try:
        point["cours"] = json.loads(point["cours"]) if point.get("cours") else None
    except ValueError:
        point["cours"] = None
    return point


def lister_points() -> list[dict]:
    """Tous les points, avec le nombre d'exercices de chacun."""
    with database.connexion() as conn:
        lignes = conn.execute(
            """
            SELECT p.*, COUNT(e.id) AS nb
            FROM points p LEFT JOIN exercices e ON e.point_id = p.id
            GROUP BY p.id ORDER BY p.titre COLLATE NOCASE
            """
        ).fetchall()
    return [dict(ligne) for ligne in lignes]


def supprimer_point(point_id: int) -> None:
    with database.connexion() as conn:
        conn.execute("DELETE FROM exercices WHERE point_id = ?", (point_id,))
        conn.execute("DELETE FROM points WHERE id = ?", (point_id,))


def ajouter_exercices(point_id: int, exercices: list[dict]) -> int:
    """Enregistre les exercices (les doublons sont ignorés). Renvoie le nombre ajouté."""
    ajoutes = 0
    with database.connexion() as conn:
        for e in exercices:
            curseur = conn.execute(
                """
                INSERT OR IGNORE INTO exercices
                    (point_id, phrase, reponse, autres, indice, traduction, explication, distracteurs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    point_id, e["phrase"], e["reponse"],
                    json.dumps(e["autres"], ensure_ascii=False),
                    e["indice"], e["traduction"], e["explication"],
                    json.dumps(e["distracteurs"], ensure_ascii=False),
                ),
            )
            ajoutes += curseur.rowcount
    return ajoutes


def lister_exercices() -> list[dict]:
    with database.connexion() as conn:
        lignes = conn.execute("SELECT * FROM exercices ORDER BY id").fetchall()
    exercices = []
    for ligne in lignes:
        e = dict(ligne)
        e["autres"] = json.loads(e["autres"] or "[]")
        e["distracteurs"] = json.loads(e["distracteurs"] or "[]")
        exercices.append(e)
    return exercices


def supprimer_exercice(exercice_id: int) -> None:
    with database.connexion() as conn:
        conn.execute("DELETE FROM exercices WHERE id = ?", (exercice_id,))


# ---------- Génération par l'IA ----------
CONSIGNE = """Tu es un professeur de grec ancien qui prépare des exercices pour une lycéenne francophone
(niveau lycée, spécialité LLCA grec). Réponds UNIQUEMENT par un objet JSON valide, sans texte autour.

Format :
{"exercices": [
  {
    "phrase": "phrase grecque avec UNE SEULE lacune notée ____",
    "reponse": "le mot grec qui complète la lacune (un seul mot, avec accents et esprits)",
    "autres_reponses": ["variantes également correctes, sinon liste vide"],
    "indice": "consigne en français qui dit quelle forme écrire, sans donner la réponse",
    "distracteurs": ["3 formes grecques fausses mais plausibles : autre temps, autre cas, autre personne"],
    "traduction": "traduction française de la phrase complète",
    "explication": "une phrase en français qui explique la règle appliquée"
  }
]}

Règles :
- Phrases courtes et simples, en grec ancien correct, adaptées à un niveau lycée.
- Chaque phrase ne travaille que le point de cours demandé.
- La lacune porte sur la forme à produire (forme verbale, cas du nom ou de l'adjectif, etc.).
- L'indice cite le mot de base (ex. « verbe λύω, aoriste, 3e personne du singulier »).
- N'invente rien : en cas de doute sur une forme, choisis une phrase plus simple.
- Varie les phrases et les mots utilisés."""


def nettoyer(texte) -> str:
    return unicodedata.normalize("NFC", str(texte or "").strip())


def _cle(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower().replace("ς", "σ")


def valider_exercices(donnees) -> list[dict]:
    """Garde uniquement les exercices bien formés (une lacune, une réponse d'un seul mot)."""
    liste = donnees.get("exercices") if isinstance(donnees, dict) else donnees
    if not isinstance(liste, list):
        return []

    propres = []
    for e in liste:
        if not isinstance(e, dict):
            continue
        phrase = re.sub(r"_{2,}|…+|\.{3,}", TROU, nettoyer(e.get("phrase")))
        reponse = nettoyer(e.get("reponse"))
        if phrase.count(TROU) != 1 or not reponse or " " in reponse:
            continue

        def liste_mots(valeur, maximum):
            if not isinstance(valeur, list):
                return []
            vus, sortie = {_cle(reponse)}, []
            for v in valeur:
                v = nettoyer(v)
                if v and " " not in v and _cle(v) not in vus:
                    vus.add(_cle(v))
                    sortie.append(v)
            return sortie[:maximum]

        propres.append({
            "phrase": phrase,
            "reponse": reponse,
            "autres": liste_mots(e.get("autres_reponses"), 3),
            "indice": nettoyer(e.get("indice")),
            "traduction": nettoyer(e.get("traduction")),
            "explication": nettoyer(e.get("explication")),
            "distracteurs": liste_mots(e.get("distracteurs"), 3),
        })
    return propres


def _appeler_ia(systeme: str, utilisateur: str) -> dict:
    reponse = client.chat.completions.create(
        model=MODELE,
        messages=[
            {"role": "system", "content": systeme},
            {"role": "user", "content": utilisateur},
        ],
        response_format={"type": "json_object"},
    )
    texte = reponse.choices[0].message.content.strip()
    if texte.startswith("```"):
        texte = texte.strip("`")
        if texte.startswith("json"):
            texte = texte[4:]
    return json.loads(texte.strip())


def generer_exercices(point: dict, mots_lexique: list[dict], nombre: int = NB_PAR_DEFAUT) -> list[dict]:
    """Demande à l'IA des phrases à trous pour un point de cours."""
    demande = [
        f"Point de cours : {point['titre']}",
        f"Type : {point['categorie']}",
        f"Nombre de phrases à créer : {nombre}",
    ]
    if point.get("notes"):
        demande.append(f"Notes de cours de l'élève (à respecter) : {point['notes']}")

    if mots_lexique:
        echantillon = random.sample(mots_lexique, min(8, len(mots_lexique)))
        liste = ", ".join(f"{m['mot']} ({', '.join(m['traductions'][:2])})" for m in echantillon)
        demande.append(f"Si c'est adapté au point, réutilise de préférence des mots du lexique de l'élève : {liste}")

    return valider_exercices(_appeler_ia(CONSIGNE, "\n".join(demande)))


# ---------- Fiche de cours d'un point ----------
def modifier_notes(point_id: int, notes: str) -> None:
    with database.connexion() as conn:
        conn.execute("UPDATE points SET notes = ? WHERE id = ?", (notes, point_id))


def enregistrer_cours(point_id: int, cours: dict) -> None:
    with database.connexion() as conn:
        conn.execute(
            "UPDATE points SET cours = ? WHERE id = ?",
            (json.dumps(cours, ensure_ascii=False), point_id),
        )


def exercices_du_point(point_id: int) -> list[dict]:
    return [e for e in lister_exercices() if e["point_id"] == point_id]


CONSIGNE_COURS = """Tu es un professeur de grec ancien. Rédige un RAPPEL DE COURS concis et exact pour une
lycéenne francophone (niveau lycée) sur le point demandé. Réponds UNIQUEMENT par un objet JSON valide :

{
  "resume": "2 à 4 phrases en français qui expliquent la règle",
  "formes": [{"libelle": "ex. 1re personne du singulier", "forme": "ex. ἔλυσα"}],
  "exemples": [{"grec": "phrase ou groupe de mots en grec", "francais": "traduction"}],
  "pieges": ["erreurs fréquentes ou exceptions, en français"]
}

Règles :
- « formes » : un tableau de 6 à 12 lignes maximum si le point s'y prête (terminaisons, cas, personnes), sinon une liste vide.
- 2 à 4 exemples, 0 à 3 pièges.
- Si l'élève a fourni ses notes de cours, appuie-toi d'abord sur elles.
- N'invente rien : omets ce dont tu n'es pas sûr."""


def valider_cours(donnees) -> dict | None:
    """Garde uniquement les parties bien formées du rappel de cours."""
    if not isinstance(donnees, dict):
        return None

    def lignes(cle, champs, maximum):
        brut = donnees.get(cle)
        sortie = []
        for element in brut if isinstance(brut, list) else []:
            if isinstance(element, dict):
                ligne = {c: nettoyer(element.get(c)) for c in champs}
                if all(ligne.values()):
                    sortie.append(ligne)
        return sortie[:maximum]

    pieges = donnees.get("pieges")
    cours = {
        "resume": nettoyer(donnees.get("resume")),
        "formes": lignes("formes", ("libelle", "forme"), 14),
        "exemples": lignes("exemples", ("grec", "francais"), 5),
        "pieges": [nettoyer(x) for x in pieges if nettoyer(x)][:4] if isinstance(pieges, list) else [],
    }
    return cours if cours["resume"] or cours["formes"] else None


def generer_cours(point: dict) -> dict | None:
    demande = [f"Point de cours : {point['titre']}", f"Type : {point['categorie']}"]
    if point.get("notes"):
        demande.append(f"Notes de cours de l'élève (à respecter) : {point['notes']}")
    return valider_cours(_appeler_ia(CONSIGNE_COURS, "\n".join(demande)))
