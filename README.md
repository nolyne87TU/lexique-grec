# Λεξικόν : mon lexique de grec ancien

Site web interactif pour construire et réviser mon lexique de grec ancien. Projet personnel, réalisé en Python pendant mes études de lettres classiques, pour relier ma passion pour le grec et mon apprentissage du code.

## Ce que fait le site

- **Fiches de lexique** : on écrit un mot grec, une IA génère sa fiche (nature, genre, génitif, traductions, étymologie, champ lexical, dérivés français). La fiche est enregistrée et posée sur le plan de travail.
- **Plan de travail** : les mots sont des cartes qu'on range par ordre alphabétique grec, par classe grammaticale, par champ lexical ou par statut de vérification.
- **Révision** : cinq modes (flashcards, quiz à choix multiples, écriture, associations, quiz de grammaire), avec des filtres et un suivi des mots à revoir.
- **Langue** : on note les points de cours (conjugaison, déclinaison, syntaxe…), et le site produit un rappel de cours et des phrases grecques à compléter.
- **Vérification critique** : une IA peut se tromper en grec. Chaque fiche se compare au Bailly ou au Chantraine, se corrige, puis se marque comme vérifiée. Le site garde ce que l'IA avait écrit et affiche un **bilan** des erreurs corrigées.

## Pourquoi cette démarche

Les modèles de langage commettent des erreurs sur le grec ancien (accents, étymologies, formes rares). Plutôt que de leur faire confiance aveuglément, le site impose une étape de vérification humaine et mesure le taux d'erreurs de l'IA dans la page *Bilan*.

## Technologies

Python 3 · Flask · SQLite · HTML / CSS / JavaScript · API Groq (modèle ouvert `openai/gpt-oss-120b`)

## Installation

```bash
git clone https://github.com/VOTRE-NOM/lexique-grec.git
cd lexique-grec
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Crée un fichier `.env` à la racine (voir `.env.example`) avec ta clé d'API Groq, gratuite sur [console.groq.com](https://console.groq.com) :

```
GROQ_API_KEY=ta_clé_ici
```

## Lancement

```bash
flask run --debug
```

Puis ouvre http://127.0.0.1:5000 dans ton navigateur. La base de données `lexique.db` est créée automatiquement au premier lancement.

## Structure du projet

| Fichier | Rôle |
| --- | --- |
| `app.py` | Les pages du site (Flask) |
| `fiche.py` | Génération des fiches de lexique par l'IA |
| `langue.py` | Points de cours, rappels de cours et phrases à trous |
| `database.py` | Base SQLite : mots, vérification, bilan |
| `templates/` | Pages HTML |
| `static/` | Styles CSS et scripts JavaScript (plan de travail, révision, exercices) |

## Limites

- Les fiches et les exercices sont écrits par une IA : à vérifier avec un dictionnaire de référence.
- Le site est prévu pour un usage personnel en local, pas pour une mise en ligne publique.
