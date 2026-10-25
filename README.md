# PharmaGarde Douala

Application web **Flask + Jinja + SQLite** pour afficher les pharmacies de garde de Douala, rechercher un
médicament dans les stocks déclarés (prix, ancienneté de l'information) et gérer pharmacies, stocks et gardes.
Trois espaces : **public**, **pharmacien**, **administrateur**. Aucun framework JavaScript : les pages sont rendues
côté serveur, le JS ne sert qu'à améliorer le confort (l'application fonctionne aussi sans).

## Démarrage rapide

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
flask --app wsgi seed --reset        # crée instance/pharmagarde.db avec les données de démonstration
flask --app wsgi run                 # http://127.0.0.1:5000
python3 -m pytest -q                 # 85 tests
```

Comptes de démonstration (à supprimer / changer avant toute mise en ligne) :

| Rôle | E-mail | Mot de passe |
|---|---|---|
| Administrateur | `admin@pharmadouala.cm` | `AdminDemo2026!` |
| Pharmacien (Pharmacie du Rond-Point) | `rondpoint@example.com` | `PharmaDemo2026!` |
| Autres pharmaciens | `akwa@example.com`, `bonanjo@example.com`, `deido@example.com`… | `PharmaDemo2026!` |

Pour revoir exactement l'état des maquettes (15 octobre 2026, 20h30) : `PHARMA_DEMO_NOW=2026-10-15T20:30 flask --app wsgi seed --reset`
puis lancer l'application avec la même variable.

Données de démonstration : 25 pharmacies (dont 1 désactivée) dans 10 quartiers, 100 médicaments (≈ 90 principes actifs/références),
1 000 lignes de stock, planning de gardes de 8 semaines (+ 2 semaines d'historique), ≈ 24 000 recherches enregistrées,
3 médicaments en rupture dans tout le réseau et 3 pharmacies sans mise à jour depuis plus de 7 jours.

## Architecture (séparation des couches)

```
Requête HTTP
  └─ app/routes/        Contrôleurs Flask : lisent la requête, appellent un service, rendent un gabarit. Aucune règle métier, aucun SQL.
      └─ app/services/  Règles métier (R1, R2, R3), validation, transactions.
          └─ app/repositories/   Tout le SQL (requêtes paramétrées uniquement).
              └─ SQLite (schema.sql : contraintes CHECK, clés étrangères, triggers)
app/models/             Objets de données immuables (dataclasses) construits depuis les lignes SQL.
app/core/               Base de données, sécurité (session, rôles), CSRF, dates (UTC → heure de Douala), erreurs, filtres Jinja.
app/templates/          Gabarits Jinja : layouts/ (public, pharmacien, admin), components/ (macros), pages par espace.
app/static/             CSS (app.css), JS (app.js), polices Inter auto-hébergées, icônes SVG (Lucide).
scripts/seed.py         Données de démonstration.       tests/   Suite pytest.       deploy/   Gunicorn, Nginx, sauvegarde.
```

## Les trois règles métier

| Règle | Mise en œuvre |
|---|---|
| **R1** — un pharmacien ne modifie que les stocks de sa pharmacie ; l'identité vient de la session, jamais d'un champ | `current_pharmacie_id()` relit l'utilisateur en base à chaque requête. Aucune URL ni aucun formulaire ne porte d'identifiant de pharmacie : un champ `pharmacie_id` (ou `updated_at`) envoyé est refusé (422). Toutes les requêtes d'écriture contiennent `WHERE pharmacie_id = <session>` : une ligne d'une autre pharmacie donne 404 et n'est pas modifiée. Un lot d'import CSV n'est utilisable que par la pharmacie qui l'a créé. |
| **R2** — deux gardes d'une même pharmacie ne se chevauchent pas | Contrôle applicatif dans une transaction `BEGIN IMMEDIATE` (pas de course entre deux administrateurs) **et** triggers SQL en filet de sécurité. Comparaison stricte : une garde qui finit à 07h00 et une autre qui commence à 07h00 sont autorisées. Message et contrôle en direct dans la fenêtre d'ajout/modification. |
| **R3** — afficher l'ancienneté de chaque stock | Calculée côté serveur (`dates.anciennete`) : vert < 2 jours, orange de 2 à 7 jours, rouge > 7 jours + « À confirmer par téléphone ». La date de mise à jour est posée par le serveur à chaque modification. |

## Sécurité

- **CSRF** : jeton par session (`app/core/csrf.py`), exigé sur **tout** POST (formulaires : champ caché ; appels JSON : en-tête `X-CSRF-Token`). Jeton régénéré à la connexion. Un test parcourt toutes les pages et vérifie que chaque formulaire POST le contient.
- Mots de passe hachés (scrypt), message d'erreur identique que l'e-mail existe ou non, **5 échecs / 5 minutes** puis blocage temporaire, hash factice pour égaliser les temps de réponse.
- Cookies de session `HttpOnly`, `SameSite=Lax`, `Secure` en production ; session invalidée si la pharmacie est désactivée.
- Contrôle d'accès par rôle (`@role_required`) ; redirection après connexion limitée aux chemins du site (pas de redirection ouverte).
- SQL toujours paramétré ; échappement automatique Jinja ; en-têtes `Content-Security-Policy` (scripts, styles et polices uniquement locaux — aucun JS ni style en ligne), `X-Frame-Options`, `nosniff`.
- Import CSV : 2 Mo max, UTF-8, aperçu **avant** écriture, confirmation atomique (tout ou rien) ; exports CSV protégés contre l'injection de formules.
- Pages pharmacien/admin : `noindex`, `Cache-Control: no-store`.

## Fidélité aux maquettes et compléments

Les 26 écrans du dossier de maquettes ont été reproduits (public, pharmacien, administrateur, modales, états vides et erreurs) et comparés
visuellement dans Chromium à 1440 px. Quelques éléments ont été ajoutés pour que l'application soit réellement utilisable :
bouton **Réactiver** (pharmacie désactivée), lien **Retirer du stock**, puce **En stock** (filtre de recherche), carte **Équivalents**
(recherche par principe actif), contrôle de chevauchement en direct, pagination à 10 lignes. Les pages sont aussi adaptées aux écrans étroits.

## Mise en production

1. Copier le projet dans `/opt/pharmagarde`, créer l'environnement virtuel, `pip install -r requirements.txt`.
2. Créer `/etc/pharmagarde.env` d'après `.env.example` (**SECRET_KEY** obligatoire, sinon l'application refuse de démarrer en production).
3. `flask --app wsgi init-db` (base vide) puis créer le premier compte administrateur ; **ne pas** exécuter `seed` en production.
4. Installer `deploy/pharmagarde.service` (systemd) et `deploy/nginx.conf` (HTTPS via Let's Encrypt).
5. Planifier `deploy/backup.sh` (cron quotidien). SQLite fonctionne en mode WAL ; 2 workers Gunicorn suffisent.

Création du premier administrateur (production) :

```bash
python3 - <<'PY'
from app import create_app
from app.core.db import get_db
from app.core.security import hash_password
app = create_app()
with app.app_context():
    get_db().execute("INSERT INTO utilisateur (email, mot_de_passe_hash, role) VALUES (?,?,'admin')",
                     ("vous@groupement.cm", hash_password("UnMotDePasseLong&Unique2026")))
PY
```

## Routes principales

| Espace | Routes |
|---|---|
| Public | `/` (gardes, `?quartier=`), `/medicaments` (`?q=`, `?m=`, `?quartier=`, `?stock=1`), `/api/quartiers`, `/api/gardes/en-cours`, `/api/pharmacies/<id>`, `/api/medicaments/suggestions` |
| Authentification | `/connexion`, `/deconnexion` (POST) |
| Pharmacien | `/pharmacien/`, `/pharmacien/stocks` (+ `ajouter`, `importer`, `modele.csv`, `<id>/modifier`, `<id>/retirer`), `/pharmacien/gardes` |
| Administrateur | `/admin/`, `/admin/pharmacies`, `/admin/gardes`, `/admin/statistiques` (+ exports `.csv`) |
