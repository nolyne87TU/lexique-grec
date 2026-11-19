"""Étape 2 : la base de données du lexique (SQLite).

Le fichier lexique.db est créé automatiquement dans le dossier du projet.
"""

import json
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

CHEMIN_BASE = Path(__file__).parent / "lexique.db"

# Champs qui sont des listes : on les stocke en texte JSON dans la base
CHAMPS_LISTES = ("traductions", "derives_francais")


def normaliser(mot: str) -> str:
    """Uniformise l'écriture des accents grecs (évite les doublons invisibles)."""
    return unicodedata.normalize("NFC", mot.strip())


def connexion() -> sqlite3.Connection:
    conn = sqlite3.connect(CHEMIN_BASE)
    conn.row_factory = sqlite3.Row  # permet d'accéder aux colonnes par leur nom
    return conn


def init_db() -> None:
    """Crée la table si elle n'existe pas encore."""
    with connexion() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mot TEXT NOT NULL UNIQUE,
                translitteration TEXT,
                nature TEXT,
                genre TEXT,
                genitif TEXT,
                forme_de_base TEXT,
                traductions TEXT,
                etymologie TEXT,
                champ_lexical TEXT,
                derives_francais TEXT,
                fiabilite TEXT,
                verifie INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Mise à jour d'une base créée avant l'ajout de la vérification
        colonnes = [c["name"] for c in conn.execute("PRAGMA table_info(mots)")]
        for nom, definition in (
            ("corrige", "INTEGER NOT NULL DEFAULT 0"),
            ("note_verif", "TEXT"),
            ("date_verif", "TEXT"),
            ("original", "TEXT"),
        ):
            if nom not in colonnes:
                conn.execute(f"ALTER TABLE mots ADD COLUMN {nom} {definition}")


def _ligne_vers_dict(ligne: sqlite3.Row) -> dict:
    fiche = dict(ligne)
    for champ in CHAMPS_LISTES:
        fiche[champ] = json.loads(fiche[champ]) if fiche[champ] else []
    try:
        fiche["original"] = json.loads(fiche["original"]) if fiche.get("original") else None
    except ValueError:
        fiche["original"] = None
    return fiche


def ajouter_mot(fiche: dict) -> None:
    """Enregistre une fiche. Si le mot existe déjà, il n'est pas écrasé."""
    with connexion() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO mots (
                mot, translitteration, nature, genre, genitif, forme_de_base,
                traductions, etymologie, champ_lexical, derives_francais, fiabilite
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normaliser(fiche.get("mot", "")),
                fiche.get("translitteration"),
                fiche.get("nature"),
                fiche.get("genre"),
                fiche.get("genitif"),
                fiche.get("forme_de_base"),
                json.dumps(fiche.get("traductions") or [], ensure_ascii=False),
                fiche.get("etymologie"),
                fiche.get("champ_lexical"),
                json.dumps(fiche.get("derives_francais") or [], ensure_ascii=False),
                fiche.get("fiabilite"),
            ),
        )


def chercher_mot(mot: str) -> dict | None:
    """Renvoie la fiche du mot, ou None s'il n'est pas dans la base."""
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT * FROM mots WHERE mot = ?", (normaliser(mot),)
        ).fetchone()
    return _ligne_vers_dict(ligne) if ligne else None


def lister_mots() -> list[dict]:
    """Renvoie toutes les fiches (la liste est utilisée à l'étape 3 pour le site)."""
    with connexion() as conn:
        lignes = conn.execute("SELECT * FROM mots ORDER BY mot").fetchall()
    return [_ligne_vers_dict(ligne) for ligne in lignes]


# ---------- Vérification des fiches ----------
CHAMPS_EDITABLES = (
    "nature", "genre", "genitif", "forme_de_base", "traductions",
    "etymologie", "champ_lexical", "derives_francais",
)
ETIQUETTES = {
    "nature": "Nature", "genre": "Genre", "genitif": "Génitif", "forme_de_base": "Forme de base",
    "traductions": "Traductions", "etymologie": "Étymologie", "champ_lexical": "Champ lexical",
    "derives_francais": "Dérivés français",
}


def _texte(valeur) -> str:
    if isinstance(valeur, list):
        return ", ".join(valeur) or "—"
    return valeur or "—"


def differences(fiche: dict) -> list[dict]:
    """Ce qui a changé entre la fiche écrite par l'IA et la fiche corrigée."""
    original = fiche.get("original")
    if not original:
        return []
    sortie = []
    for champ in CHAMPS_EDITABLES:
        avant, apres = original.get(champ), fiche.get(champ)
        if (avant or None) != (apres or None):
            sortie.append({"champ": ETIQUETTES[champ], "avant": _texte(avant), "apres": _texte(apres)})
    return sortie


def enregistrer_verification(mot: str, nouveaux: dict, verifie: bool, note: str) -> bool:
    """Corrige la fiche si besoin, garde la version de l'IA, puis enregistre le statut."""
    actuel = chercher_mot(mot)
    if actuel is None:
        return False

    modifs = {c: v for c, v in nouveaux.items()
              if c in CHAMPS_EDITABLES and (v or None) != (actuel.get(c) or None)}

    with connexion() as conn:
        if modifs:
            if actuel["original"] is None:  # on garde la version de l'IA, une seule fois
                instantane = {c: actuel.get(c) for c in CHAMPS_EDITABLES}
                conn.execute("UPDATE mots SET original = ? WHERE mot = ?",
                             (json.dumps(instantane, ensure_ascii=False), actuel["mot"]))
            for champ, valeur in modifs.items():  # les noms de colonnes viennent de CHAMPS_EDITABLES
                if champ in CHAMPS_LISTES:
                    valeur = json.dumps(valeur, ensure_ascii=False)
                conn.execute(f"UPDATE mots SET {champ} = ? WHERE mot = ?", (valeur, actuel["mot"]))
        conn.execute(
            "UPDATE mots SET verifie = ?, note_verif = ?, date_verif = ? WHERE mot = ?",
            (1 if verifie else 0, note or None, date.today().isoformat() if verifie else None, actuel["mot"]),
        )

    apres = chercher_mot(mot)
    with connexion() as conn:
        conn.execute("UPDATE mots SET corrige = ? WHERE mot = ?",
                     (1 if differences(apres) else 0, apres["mot"]))
    return True


def changer_statut(mot: str, verifie: bool) -> None:
    """Marque une fiche comme vérifiée (ou retire le statut) sans la modifier."""
    with connexion() as conn:
        conn.execute(
            "UPDATE mots SET verifie = ?, date_verif = ? WHERE mot = ?",
            (1 if verifie else 0, date.today().isoformat() if verifie else None, normaliser(mot)),
        )


def bilan() -> dict:
    mots = lister_mots()
    verifiees = [m for m in mots if m["verifie"]]
    corrigees = [m for m in mots if m["corrige"]]
    return {
        "total": len(mots),
        "verifiees": len(verifiees),
        "corrigees": len(corrigees),
        "corrigees_verifiees": sum(1 for m in verifiees if m["corrige"]),
        "corrections": [{"mot": m["mot"], "diffs": differences(m)} for m in corrigees],
    }
