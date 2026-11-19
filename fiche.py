"""Étapes 1 et 2 : générer une fiche de lexique pour un mot grec ancien (Groq + base SQLite).

Usage : python3 fiche.py λόγος      (cherche dans la base, sinon appelle l'IA)
        python3 fiche.py            (le programme te demande le mot)
        python3 fiche.py --liste    (affiche tous les mots enregistrés)
"""

import json
import sys

from dotenv import load_dotenv
from groq import Groq

import database

# Charge la clé d'API depuis le fichier .env
load_dotenv()

client = Groq()  # lit automatiquement GROQ_API_KEY
MODELE = "openai/gpt-oss-120b"  # si ce nom ne marche plus : voir console.groq.com/docs/models

CONSIGNE = """Tu es un helléniste rigoureux qui aide une lycéenne francophone.
On te donne un mot de grec ancien. Réponds UNIQUEMENT par un objet JSON valide
(sans texte avant ou après, sans balises ```), avec exactement ces clés :

{
  "mot": "le mot avec ses accents et esprits",
  "translitteration": "transcription en lettres latines",
  "nature": "nom commun, verbe, adjectif, adverbe, préposition, conjonction, pronom, particule...",
  "genre": "masculin, féminin, neutre, ou null si non applicable",
  "genitif": "génitif singulier pour un nom, ou null",
  "forme_de_base": "nominatif pour un nom, 1re personne du présent pour un verbe, masculin nominatif pour un adjectif",
  "traductions": ["2 à 4 traductions françaises, de la plus courante à la plus rare"],
  "etymologie": "racine ou famille de mots en une phrase, ou null si incertain",
  "champ_lexical": "UN seul champ parmi : langage, pensée, politique, guerre, religion, nature, corps, famille, société, morale, temps, espace, art, autre",
  "derives_francais": ["mots français issus de ce mot, ou liste vide"],
  "fiabilite": "haute, moyenne ou faible : ton degré de certitude sur cette fiche"
}

Règles : n'invente rien. Si tu n'es pas sûr d'une information, mets null
(ou "faible" dans fiabilite) plutôt que de deviner. Si le mot n'est pas du
grec ancien, renvoie {"erreur": "ce mot n'est pas du grec ancien"}."""


def generer_fiche(mot: str) -> dict:
    """Envoie le mot à l'IA et renvoie la fiche sous forme de dictionnaire."""
    reponse = client.chat.completions.create(
        model=MODELE,
        messages=[
            {"role": "system", "content": CONSIGNE},
            {"role": "user", "content": mot},
        ],
        response_format={"type": "json_object"},
    )
    texte = reponse.choices[0].message.content.strip()

    # Au cas où l'IA entoure quand même sa réponse de balises ```
    if texte.startswith("```"):
        texte = texte.strip("`")
        if texte.startswith("json"):
            texte = texte[4:]
        texte = texte.strip()

    return json.loads(texte)


def afficher_fiche(fiche: dict) -> None:
    """Affiche la fiche proprement dans le terminal."""
    if "erreur" in fiche:
        print(f"\n⚠️  {fiche['erreur']}\n")
        return

    print("\n" + "=" * 40)
    print(f"{fiche.get('mot', '?')}  ({fiche.get('translitteration', '?')})")
    print("=" * 40)
    print(f"Nature          : {fiche.get('nature', '?')}")
    if fiche.get("genre"):
        print(f"Genre           : {fiche['genre']}")
    if fiche.get("genitif"):
        print(f"Génitif         : {fiche['genitif']}")
    print(f"Forme de base   : {fiche.get('forme_de_base', '?')}")
    print(f"Traductions     : {', '.join(fiche.get('traductions') or [])}")
    print(f"Étymologie      : {fiche.get('etymologie') or 'non précisée'}")
    print(f"Champ lexical   : {fiche.get('champ_lexical', '?')}")
    derives = fiche.get("derives_francais") or []
    print(f"Dérivés français: {', '.join(derives) if derives else 'aucun'}")
    print(f"Fiabilité IA    : {fiche.get('fiabilite', '?')}")
    print("→ À vérifier dans le Bailly ou le Chantraine.\n")


def afficher_liste() -> None:
    """Affiche tous les mots enregistrés dans la base."""
    mots = database.lister_mots()
    if not mots:
        print("\nLa base est vide : cherche d'abord quelques mots.\n")
        return

    print(f"\n{len(mots)} mot(s) dans le lexique :\n")
    for m in mots:
        statut = "✓ vérifié" if m["verifie"] else "à vérifier"
        print(f"- {m['mot']}  |  {m['nature']}  |  {m['champ_lexical']}  |  {statut}")
    print()


def main() -> None:
    database.init_db()

    if len(sys.argv) > 1 and sys.argv[1] == "--liste":
        afficher_liste()
        return

    if len(sys.argv) > 1:
        mot = sys.argv[1]
    else:
        mot = input("Mot grec : ").strip()

    if not mot:
        print("Aucun mot saisi.")
        return

    # 1. On regarde d'abord dans la base (gratuit et instantané)
    fiche = database.chercher_mot(mot)
    if fiche:
        print("\n(fiche déjà enregistrée : aucun appel à l'IA)")
    else:
        # 2. Sinon on demande à l'IA, puis on enregistre
        try:
            fiche = generer_fiche(mot)
        except json.JSONDecodeError:
            print("L'IA n'a pas renvoyé un JSON valide. Relance le programme.")
            return
        except Exception as e:
            print(f"Erreur lors de l'appel à l'API : {e}")
            return

        if "erreur" not in fiche:
            database.ajouter_mot(fiche)
            print("\n(nouvelle fiche enregistrée dans la base)")

    afficher_fiche(fiche)


if __name__ == "__main__":
    main()
