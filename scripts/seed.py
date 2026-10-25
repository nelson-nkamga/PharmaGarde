"""Données de démonstration : 25 pharmacies, 10 quartiers, 100 médicaments, 1 000 lignes de stock,
planning de gardes de 8 semaines (+ 2 semaines d'historique) et historique de recherches.

Usage :  flask --app wsgi seed --reset
"""
import json
import random
from datetime import timedelta
from pathlib import Path

from app.core import dates
from app.core.db import get_db, init_db, transaction
from app.core.security import hash_password

DEMO_PHARMACIEN_MDP = "PharmaDemo2026!"
DEMO_ADMIN_EMAIL = "admin@pharmadouala.cm"
DEMO_ADMIN_MDP = "AdminDemo2026!"

QUARTIERS = ["Akwa", "Bonanjo", "Bonapriso", "Bonamoussadi", "Deido", "Bepanda",
             "Makepe", "Logbessou", "Kotto", "Ndokoti"]

# (nom, quartier, adresse, e-mail éventuel)
PHARMACIES = [
    ("Pharmacie du Rond-Point", "Bonapriso", "Boulevard de la Liberté, près du rond-point Akwa", "rondpoint@example.com"),
    ("Pharmacie Bonamoussadi Centre", "Bonamoussadi", "Rue du marché, face à la station-service", "bonamoussadi@example.com"),
    ("Pharmacie Akwa Santé", "Akwa", "Avenue du Général de Gaulle, près du marché Sandaga", "akwa@example.com"),
    ("Pharmacie de Bonanjo", "Bonanjo", "Rue Joss, près de la Place du Gouvernement", "bonanjo@example.com"),
    ("Pharmacie de Deido", "Deido", "Route de Deido, près du carrefour Trois-Boutiques", "deido@example.com"),
    ("Pharmacie Bepanda", "Bepanda", "Carrefour Bepanda Omnisport, face à la station", "bepanda@example.com"),
    ("Pharmacie Makepe", "Makepe", "Makepe Missoke, derrière l'école publique", "makepe@example.com"),
    ("Pharmacie Logbessou", "Logbessou", "Carrefour Logbessou, route de Japoma", "logbessou@example.com"),
    ("Pharmacie Kotto", "Kotto", "Carrefour Kotto, près de l'Église", "kotto@example.com"),
    ("Pharmacie Ndokoti", "Ndokoti", "Carrefour Ndokoti, face à la gare routière", "ndokoti@example.com"),
    ("Pharmacie des Palmiers", "Bonapriso", "Rue Njo-Njo, près du marché des fleurs", None),
    ("Pharmacie Saint-Michel", "Akwa", "Rue Alfred Saker, près de la cathédrale", None),
    ("Pharmacie Nouvelle Bonanjo", "Bonanjo", "Avenue des Ambassadeurs", None),
    ("Pharmacie du Carrefour", "Bonamoussadi", "Carrefour Shell Bonamoussadi", None),
    ("Pharmacie Étoile de Deido", "Deido", "Rue de l'Étoile, Deido Bas", None),
    ("Pharmacie du Pont", "Bepanda", "Route du Pont, Bepanda Tonnerre", None),
    ("Pharmacie Makepe Missoke", "Makepe", "Rue des Cocotiers, Makepe", None),
    ("Pharmacie Beau Séjour", "Logbessou", "Rue Beau Séjour, Logbessou", None),
    ("Pharmacie Kotto Centre", "Kotto", "Avenue Kotto Centre, près du marché", None),
    ("Pharmacie de la Cité", "Ndokoti", "Cité des Palmiers, Ndokoti", None),
    ("Pharmacie Saint-Joseph", "Akwa", "Rue Pau, Akwa Nord", None),
    ("Pharmacie de la Paix", "Bonamoussadi", "Rue de la Paix, Bonamoussadi", None),
    ("Pharmacie du Port", "Bonanjo", "Boulevard de la Liberté, côté port", None),
    ("Pharmacie Espoir", "Deido", "Rue Espoir, Deido", None),
    ("Pharmacie Bonne Santé", "Makepe", "Carrefour Bonne Santé, Makepe", None),
]
PHARMACIE_DESACTIVEE = "Pharmacie Bepanda"
PHARMACIES_ANCIENNES = {"Pharmacie Makepe": 10, "Pharmacie Logbessou": 9, "Pharmacie Kotto": 8}  # jours sans mise à jour

# nom | dosage | forme | conditionnement | principe actif
CATALOGUE = """
Paracétamol|500 mg|Comprimé|Boîte de 20|Paracétamol
Paracétamol|1 g|Comprimé|Boîte de 8|Paracétamol
Doliprane|1000 mg|Comprimé|Boîte de 8|Paracétamol
Efferalgan|500 mg|Comprimé effervescent|Boîte de 16|Paracétamol
Paracétamol|120 mg/5 mL|Sirop|Flacon de 100 mL|Paracétamol
Amoxicilline|1 g|Comprimé dispersible|Boîte de 12|Amoxicilline
Amoxicilline|500 mg|Gélule|Boîte de 16|Amoxicilline
Clamoxyl|1 g|Comprimé|Boîte de 6|Amoxicilline
Augmentin|1 g/125 mg|Comprimé|Boîte de 12|Amoxicilline-acide clavulanique
Amoxicilline|250 mg/5 mL|Suspension buvable|Flacon de 60 mL|Amoxicilline
Ibuprofène|400 mg|Comprimé|Boîte de 20|Ibuprofène
Ibuprofène|200 mg|Comprimé|Boîte de 30|Ibuprofène
Ibuprofène|100 mg/5 mL|Suspension buvable|Flacon de 150 mL|Ibuprofène
Diclofénac|50 mg|Comprimé|Boîte de 20|Diclofénac
Diclofénac|75 mg/3 mL|Solution injectable|Boîte de 5|Diclofénac
Artéméther-Luméfantrine|20 mg/120 mg|Comprimé|Boîte de 24|Artéméther-Luméfantrine
Artéméther-Luméfantrine|20 mg/120 mg|Comprimé dispersible|Boîte de 12|Artéméther-Luméfantrine
Artésunate-Amodiaquine|100 mg/270 mg|Comprimé|Boîte de 6|Artésunate-Amodiaquine
Quinine|300 mg|Comprimé|Boîte de 30|Quinine
Quinine|200 mg/2 mL|Solution injectable|Boîte de 6|Quinine
Sulfadoxine-Pyriméthamine|500 mg/25 mg|Comprimé|Boîte de 3|Sulfadoxine-Pyriméthamine
Métronidazole|500 mg|Comprimé|Boîte de 20|Métronidazole
Métronidazole|250 mg|Comprimé|Boîte de 20|Métronidazole
Métronidazole|500 mg/100 mL|Solution pour perfusion|Poche de 100 mL|Métronidazole
Ciprofloxacine|500 mg|Comprimé|Boîte de 10|Ciprofloxacine
Azithromycine|500 mg|Comprimé|Boîte de 3|Azithromycine
Cotrimoxazole|400 mg/80 mg|Comprimé|Boîte de 20|Cotrimoxazole
Doxycycline|100 mg|Gélule|Boîte de 10|Doxycycline
Ceftriaxone|1 g|Poudre injectable|Flacon|Ceftriaxone
Oméprazole|20 mg|Gélule|Boîte de 14|Oméprazole
Oméprazole|40 mg|Gélule|Boîte de 14|Oméprazole
Pantoprazole|40 mg|Comprimé|Boîte de 14|Pantoprazole
Maalox|400 mg/400 mg|Comprimé à croquer|Boîte de 40|Hydroxyde d'aluminium-magnésium
Dompéridone|10 mg|Comprimé|Boîte de 30|Dompéridone
Lopéramide|2 mg|Gélule|Boîte de 12|Lopéramide
Sels de réhydratation orale|20,5 g|Sachet|Boîte de 10|Sels de réhydratation orale
Cétirizine|10 mg|Comprimé|Boîte de 14|Cétirizine
Loratadine|10 mg|Comprimé|Boîte de 15|Loratadine
Chlorphénamine|4 mg|Comprimé|Boîte de 20|Chlorphénamine
Salbutamol|100 µg/dose|Aérosol doseur|Flacon de 200 doses|Salbutamol
Salbutamol|2 mg|Comprimé|Boîte de 30|Salbutamol
Prednisolone|20 mg|Comprimé|Boîte de 20|Prednisolone
Dexaméthasone|4 mg/mL|Solution injectable|Boîte de 10|Dexaméthasone
Montélukast|10 mg|Comprimé|Boîte de 28|Montélukast
Amlodipine|5 mg|Comprimé|Boîte de 30|Amlodipine
Amlodipine|10 mg|Comprimé|Boîte de 30|Amlodipine
Losartan|50 mg|Comprimé|Boîte de 30|Losartan
Énalapril|10 mg|Comprimé|Boîte de 30|Énalapril
Aténolol|50 mg|Comprimé|Boîte de 28|Aténolol
Furosémide|40 mg|Comprimé|Boîte de 20|Furosémide
Hydrochlorothiazide|25 mg|Comprimé|Boîte de 30|Hydrochlorothiazide
Aspirine|100 mg|Comprimé gastro-résistant|Boîte de 30|Acide acétylsalicylique
Atorvastatine|20 mg|Comprimé|Boîte de 30|Atorvastatine
Metformine|500 mg|Comprimé|Boîte de 60|Metformine
Metformine|850 mg|Comprimé|Boîte de 60|Metformine
Glibenclamide|5 mg|Comprimé|Boîte de 30|Glibenclamide
Gliclazide|80 mg|Comprimé|Boîte de 30|Gliclazide
Insuline humaine NPH|100 UI/mL|Suspension injectable|Flacon de 10 mL|Insuline humaine
Lévothyroxine|100 µg|Comprimé|Boîte de 30|Lévothyroxine
Zinc|20 mg|Comprimé dispersible|Boîte de 10|Zinc
Vitamine C|500 mg|Comprimé à croquer|Boîte de 30|Acide ascorbique
Acide folique|5 mg|Comprimé|Boîte de 20|Acide folique
Fer-acide folique|200 mg/0,4 mg|Comprimé|Boîte de 30|Fer-acide folique
Vitamines B complexe|Standard|Comprimé|Boîte de 30|Vitamines B
Calcium-vitamine D3|500 mg/400 UI|Comprimé|Boîte de 30|Calcium-vitamine D3
Albendazole|400 mg|Comprimé à croquer|Boîte de 1|Albendazole
Mébendazole|100 mg|Comprimé|Boîte de 6|Mébendazole
Ivermectine|3 mg|Comprimé|Boîte de 4|Ivermectine
Praziquantel|600 mg|Comprimé|Boîte de 4|Praziquantel
Fluconazole|150 mg|Gélule|Boîte de 1|Fluconazole
Clotrimazole|1 %|Crème|Tube de 20 g|Clotrimazole
Miconazole|2 %|Gel|Tube de 30 g|Miconazole
Hydrocortisone|1 %|Crème|Tube de 15 g|Hydrocortisone
Povidone iodée|10 %|Solution cutanée|Flacon de 125 mL|Povidone iodée
Chlorhexidine|0,5 %|Solution cutanée|Flacon de 250 mL|Chlorhexidine
Sérum physiologique|0,9 %|Unidose|Boîte de 40|Chlorure de sodium
Chloramphénicol|0,4 %|Collyre|Flacon de 10 mL|Chloramphénicol
Xylométazoline|0,1 %|Solution nasale|Flacon de 10 mL|Xylométazoline
Ambroxol|15 mg/5 mL|Sirop|Flacon de 100 mL|Ambroxol
Ambroxol|30 mg|Comprimé|Boîte de 20|Ambroxol
Tramadol|50 mg|Gélule|Boîte de 20|Tramadol
Phloroglucinol|80 mg|Comprimé|Boîte de 30|Phloroglucinol
Butylhyoscine|10 mg|Comprimé|Boîte de 20|Butylhyoscine
Métoclopramide|10 mg|Comprimé|Boîte de 30|Métoclopramide
Prométhazine|25 mg|Comprimé|Boîte de 20|Prométhazine
Ondansétron|4 mg|Comprimé|Boîte de 10|Ondansétron
Acide tranexamique|500 mg|Comprimé|Boîte de 20|Acide tranexamique
Lévonorgestrel|1,5 mg|Comprimé|Boîte de 1|Lévonorgestrel
Paracétamol|100 mg|Suppositoire|Boîte de 10|Paracétamol
Gentamicine|80 mg/2 mL|Solution injectable|Boîte de 10|Gentamicine
Ampicilline|1 g|Poudre injectable|Flacon|Ampicilline
Cloxacilline|500 mg|Gélule|Boîte de 16|Cloxacilline
Érythromycine|500 mg|Comprimé|Boîte de 14|Érythromycine
Nystatine|100 000 UI/mL|Suspension buvable|Flacon de 30 mL|Nystatine
Oxytétracycline|3 %|Pommade ophtalmique|Tube de 5 g|Oxytétracycline
Thiamine|100 mg|Comprimé|Boîte de 30|Thiamine
Captopril|25 mg|Comprimé|Boîte de 30|Captopril
Spironolactone|25 mg|Comprimé|Boîte de 30|Spironolactone
Simvastatine|20 mg|Comprimé|Boîte de 28|Simvastatine
Glucose|5 %|Solution pour perfusion|Poche de 500 mL|Glucose
""".strip().splitlines()

# Médicaments en rupture dans TOUT le réseau (jeu de test de la statistique n°4)
RUPTURE_PARTOUT = {("Artéméther-Luméfantrine", "20 mg/120 mg", "Comprimé"),
                   ("Métronidazole", "500 mg", "Comprimé"),
                   ("Salbutamol", "100 µg/dose", "Aérosol doseur")}

# Stock du compte de démonstration (maquettes) : (nom, dosage, forme, quantité, prix, âge en jours)
STOCK_RONDPOINT = [
    ("Paracétamol", "500 mg", "Comprimé", 120, 500, 0),
    ("Amoxicilline", "1 g", "Comprimé dispersible", 32, 2500, 1),
    ("Ibuprofène", "400 mg", "Comprimé", 8, 1200, 3),
    ("Artéméther-Luméfantrine", "20 mg/120 mg", "Comprimé", 0, 3500, 9),
    ("Métronidazole", "500 mg", "Comprimé", 0, 1000, 10),
    ("Oméprazole", "20 mg", "Gélule", 24, 2000, 5),
]

# Recherches sur 30 jours (maquette de statistiques)
TOP_RECHERCHES = [("Paracétamol", "500 mg", "Comprimé", 1240), ("Amoxicilline", "1 g", "Comprimé dispersible", 980),
                  ("Artéméther-Luméfantrine", "20 mg/120 mg", "Comprimé", 870), ("Ibuprofène", "400 mg", "Comprimé", 760),
                  ("Métronidazole", "500 mg", "Comprimé", 640), ("Oméprazole", "20 mg", "Gélule", 520),
                  ("Cétirizine", "10 mg", "Comprimé", 410), ("Zinc", "20 mg", "Comprimé dispersible", 330),
                  ("Vitamine C", "500 mg", "Comprimé à croquer", 250), ("Acide folique", "5 mg", "Comprimé", 180)]


def _slug_email(nom: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", nom.lower().replace("pharmacie", "")).encode("ascii", "ignore").decode()
    return "".join(c for c in s if c.isalnum()) + "@example.com"


def run(app, reset: bool = False):
    path = Path(app.config["DATABASE"])
    if reset:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(path) + suffix)
            if p.exists():
                p.unlink()
    rng = random.Random(2026)
    with app.app_context():
        init_db()
        db = get_db()
        if db.execute("SELECT COUNT(*) FROM pharmacie").fetchone()[0]:
            raise SystemExit("La base contient déjà des données. Relancez avec --reset pour la recréer.")
        now = dates.now_utc()
        iso = dates.to_iso
        pwd_hash = hash_password(DEMO_PHARMACIEN_MDP)   # même mot de passe de démonstration pour tous les comptes pharmacien

        with transaction(db):
            # -- quartiers, pharmacies, comptes ----------------------------------------------------
            q_id = {}
            for nom in QUARTIERS:
                q_id[nom] = db.execute("INSERT INTO quartier (nom) VALUES (?)", (nom,)).lastrowid
            pharm_ids = {}
            for i, (nom, quartier, adresse, email) in enumerate(PHARMACIES, start=1):
                actif = 0 if nom == PHARMACIE_DESACTIVEE else 1
                pid = db.execute(
                    "INSERT INTO pharmacie (nom, adresse, telephone, quartier_id, actif, cree_le) VALUES (?,?,?,?,?,?)",
                    (nom, adresse, f"+237 690 100 {100 + i}", q_id[quartier], actif, iso(now))).lastrowid
                pharm_ids[nom] = pid
                db.execute("INSERT INTO utilisateur (email, mot_de_passe_hash, role, pharmacie_id) VALUES (?,?,?,?)",
                           (email or _slug_email(nom), pwd_hash, "pharmacien", pid))
            db.execute("INSERT INTO utilisateur (email, mot_de_passe_hash, role, pharmacie_id) VALUES (?,?,?,NULL)",
                       (DEMO_ADMIN_EMAIL, hash_password(DEMO_ADMIN_MDP), "admin"))

            # -- catalogue -----------------------------------------------------------------------
            assert len(CATALOGUE) == 100, f"Le catalogue doit contenir 100 médicaments ({len(CATALOGUE)})"
            pa_id, med_id, med_cle = {}, {}, []
            for ligne in CATALOGUE:
                nom, dosage, forme, cond, pa = ligne.split("|")
                if pa not in pa_id:
                    pa_id[pa] = db.execute("INSERT INTO principe_actif (nom) VALUES (?)", (pa,)).lastrowid
                mid = db.execute(
                    "INSERT INTO medicament (nom, dosage, forme, conditionnement, principe_actif_id) VALUES (?,?,?,?,?)",
                    (nom, dosage, forme, cond, pa_id[pa])).lastrowid
                med_id[(nom, dosage, forme)] = mid
                med_cle.append((nom, dosage, forme))

            # -- stocks : 25 pharmacies x 40 médicaments = 1 000 lignes -------------------------------
            base_prix = {m: rng.choice(range(300, 6001, 50)) for m in med_cle}
            for nom, dosage, forme, _q, prix, _age in STOCK_RONDPOINT:
                base_prix[(nom, dosage, forme)] = prix
            base_prix[("Paracétamol", "500 mg", "Comprimé")] = 550

            noms = [p[0] for p in PHARMACIES]
            choix = {n: set() for n in noms}
            forces = {(a, b, c) for a, b, c, *_ in STOCK_RONDPOINT}
            choix["Pharmacie du Rond-Point"] |= forces
            for n in noms:
                autres = [m for m in med_cle if m not in choix[n]]
                choix[n] |= set(rng.sample(autres, 40 - len(choix[n])))
            # couverture : chaque médicament doit être déclaré par au moins 3 pharmacies
            def compte(m): return sum(1 for n in noms if m in choix[n])
            for m in med_cle:
                while compte(m) < 3:
                    n = rng.choice([x for x in noms if m not in choix[x] and x != "Pharmacie du Rond-Point"])
                    surplus = [x for x in choix[n] if compte(x) > 8 and x not in forces]
                    choix[n].discard(rng.choice(surplus))
                    choix[n].add(m)

            lignes, vus_positifs = [], set()
            for n in noms:
                for m in sorted(choix[n]):
                    if m in RUPTURE_PARTOUT:
                        qte = 0
                    else:
                        r = rng.random()
                        qte = 0 if r < 0.12 else rng.randint(1, 10) if r < 0.27 else rng.randint(11, 200)
                    if n == "Pharmacie du Rond-Point" and m in forces:
                        ref = next(x for x in STOCK_RONDPOINT if (x[0], x[1], x[2]) == m)
                        qte, prix, age = ref[3], ref[4], ref[5]
                    else:
                        prix = max(50, round(base_prix[m] * rng.uniform(0.85, 1.2) / 50) * 50)
                        age = rng.choices([0, 1, rng.randint(2, 6), rng.randint(8, 15)], [38, 24, 30, 8])[0]
                    if n in PHARMACIES_ANCIENNES:
                        age = PHARMACIES_ANCIENNES[n] + rng.randint(0, 4)
                    heures = rng.randint(1, 10) if age == 0 else rng.randint(0, 11)
                    lignes.append([pharm_ids[n], med_id[m], qte, prix, age, heures, m])
                    if qte > 0:
                        vus_positifs.add(m)
            # un médicament « normal » doit rester disponible quelque part
            for m in med_cle:
                if m not in RUPTURE_PARTOUT and m not in vus_positifs:
                    cible = next(l for l in lignes if l[6] == m)
                    cible[2] = rng.randint(11, 60)
            # une pharmacie « ancienne » garde exactement N jours pour sa ligne la plus récente
            for n, jours in PHARMACIES_ANCIENNES.items():
                propres = [l for l in lignes if l[0] == pharm_ids[n]]
                min(propres, key=lambda l: l[4])[4:6] = [jours, 3]
            db.executemany(
                "INSERT INTO stock (pharmacie_id, medicament_id, quantite, prix, updated_at) VALUES (?,?,?,?,?)",
                [(l[0], l[1], l[2], l[3], iso(now - timedelta(days=l[4], hours=l[5]))) for l in lignes])

            # -- planning de gardes : 2 semaines d'historique + cycle de 8 semaines ------------------------
            debut_cycle = dates.monday_of(now)
            db.execute("INSERT INTO parametre (cle, valeur) VALUES ('planning_debut', ?)", (iso(debut_cycle),))
            actives = [n for n in noms if n != PHARMACIE_DESACTIVEE]
            rotation = actives[:]
            rng.shuffle(rotation)
            pointeur = 0

            def prochains(k, deja):
                nonlocal pointeur
                res = []
                while len(res) < k:
                    n = rotation[pointeur % len(rotation)]
                    pointeur += 1
                    if n not in deja and n not in res:
                        res.append(n)
                return res

            gardes = []
            for jour in range(-14, 56):
                j0 = debut_cycle + timedelta(days=jour)           # 00h00 Douala, en UTC
                dimanche = dates.local(j0).weekday() == 6
                utilises = []
                if dimanche:  # garde de jour 08h-20h, puis nuit 20h-07h
                    for n in prochains(2, utilises):
                        utilises.append(n)
                        gardes.append((pharm_ids[n], j0 + timedelta(hours=8), j0 + timedelta(hours=20)))
                nb = 4 if dates.local(j0).weekday() == 0 else 3
                heure = 20 if dimanche else 19
                for n in prochains(nb, utilises):
                    utilises.append(n)
                    gardes.append((pharm_ids[n], j0 + timedelta(hours=heure), j0 + timedelta(days=1, hours=7)))
            db.executemany("INSERT INTO garde (pharmacie_id, date_debut, date_fin) VALUES (?,?,?)",
                           [(p, iso(a), iso(b)) for p, a, b in gardes])

            # -- historique de recherches (90 jours) ---------------------------------------------------
            top = {(a, b, c): n for a, b, c, n in TOP_RECHERCHES}
            queue = []
            for m in med_cle:
                n30 = top.get(m, rng.randint(15, 140))
                n_ancien = int(n30 * rng.uniform(0.5, 1.1))
                libelle = f"{m[0]} {m[1]}"
                queue += [(libelle, med_id[m], rng.uniform(0, 30)) for _ in range(n30)]
                queue += [(libelle, med_id[m], rng.uniform(30, 90)) for _ in range(n_ancien)]
            db.executemany(
                "INSERT INTO recherche_log (terme, medicament_id, quartier_id, nb_resultats, date) VALUES (?,?,?,?,?)",
                [(t, mid, rng.choice([None] + list(q_id.values())), rng.randint(1, 12),
                  iso(now - timedelta(days=jours_ago, seconds=rng.randint(0, 80000)))) for t, mid, jours_ago in queue])

        stats = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("pharmacie", "quartier", "medicament", "stock", "garde", "recherche_log")}
        print("Base de démonstration :", json.dumps(stats))
        print(f"  Administrateur : {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_MDP}")
        print(f"  Pharmacien     : rondpoint@example.com / {DEMO_PHARMACIEN_MDP}")
