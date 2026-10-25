-- PharmaGarde Douala — schéma SQLite
-- Dates : texte ISO 8601 en UTC (ex. 2026-10-20T19:00:00Z).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS quartier (
    id   INTEGER PRIMARY KEY,
    nom  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS pharmacie (
    id          INTEGER PRIMARY KEY,
    nom         TEXT NOT NULL,
    adresse     TEXT NOT NULL,
    telephone   TEXT NOT NULL,
    quartier_id INTEGER NOT NULL REFERENCES quartier(id),
    actif       INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0, 1)),
    cree_le     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (nom, quartier_id)
);
CREATE INDEX IF NOT EXISTS ix_pharmacie_quartier ON pharmacie(quartier_id);

CREATE TABLE IF NOT EXISTS utilisateur (
    id                INTEGER PRIMARY KEY,
    email             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    mot_de_passe_hash TEXT NOT NULL,
    role              TEXT NOT NULL CHECK (role IN ('admin', 'pharmacien')),
    pharmacie_id      INTEGER REFERENCES pharmacie(id),
    actif             INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0, 1)),
    CHECK ((role = 'admin' AND pharmacie_id IS NULL)
        OR (role = 'pharmacien' AND pharmacie_id IS NOT NULL))
);
-- Un seul compte pharmacien par pharmacie
CREATE UNIQUE INDEX IF NOT EXISTS ux_utilisateur_pharmacie
    ON utilisateur(pharmacie_id) WHERE pharmacie_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS principe_actif (
    id  INTEGER PRIMARY KEY,
    nom TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS medicament (
    id               INTEGER PRIMARY KEY,
    nom              TEXT NOT NULL,
    dosage           TEXT NOT NULL,
    forme            TEXT NOT NULL,
    conditionnement  TEXT NOT NULL DEFAULT '',
    principe_actif_id INTEGER REFERENCES principe_actif(id),
    UNIQUE (nom, dosage, forme)
);
CREATE INDEX IF NOT EXISTS ix_medicament_pa ON medicament(principe_actif_id);

CREATE TABLE IF NOT EXISTS stock (
    pharmacie_id INTEGER NOT NULL REFERENCES pharmacie(id),
    medicament_id INTEGER NOT NULL REFERENCES medicament(id),
    quantite     INTEGER NOT NULL CHECK (quantite >= 0),
    prix         INTEGER NOT NULL CHECK (prix > 0),   -- FCFA
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (pharmacie_id, medicament_id)
);
CREATE INDEX IF NOT EXISTS ix_stock_medicament ON stock(medicament_id);

CREATE TABLE IF NOT EXISTS garde (
    id           INTEGER PRIMARY KEY,
    pharmacie_id INTEGER NOT NULL REFERENCES pharmacie(id),
    date_debut   TEXT NOT NULL,
    date_fin     TEXT NOT NULL,
    CHECK (date_fin > date_debut)
);
CREATE INDEX IF NOT EXISTS ix_garde_periode ON garde(date_debut, date_fin);
CREATE INDEX IF NOT EXISTS ix_garde_pharmacie ON garde(pharmacie_id, date_debut);

-- Règle R2 appliquée aussi en base : deux gardes d'une même pharmacie ne se chevauchent pas.
-- Comparaison stricte : une garde qui finit à 07h00 et une autre qui commence à 07h00 sont autorisées.
CREATE TRIGGER IF NOT EXISTS garde_no_overlap_insert
BEFORE INSERT ON garde
WHEN EXISTS (SELECT 1 FROM garde g
              WHERE g.pharmacie_id = NEW.pharmacie_id
                AND g.date_debut < NEW.date_fin
                AND g.date_fin   > NEW.date_debut)
BEGIN
    SELECT RAISE(ABORT, 'GARDE_CHEVAUCHEMENT');
END;

CREATE TRIGGER IF NOT EXISTS garde_no_overlap_update
BEFORE UPDATE ON garde
WHEN EXISTS (SELECT 1 FROM garde g
              WHERE g.pharmacie_id = NEW.pharmacie_id
                AND g.id != NEW.id
                AND g.date_debut < NEW.date_fin
                AND g.date_fin   > NEW.date_debut)
BEGIN
    SELECT RAISE(ABORT, 'GARDE_CHEVAUCHEMENT');
END;

CREATE TABLE IF NOT EXISTS recherche_log (
    id            INTEGER PRIMARY KEY,
    terme         TEXT NOT NULL,
    medicament_id INTEGER REFERENCES medicament(id),
    quartier_id   INTEGER REFERENCES quartier(id),
    nb_resultats  INTEGER NOT NULL DEFAULT 0,
    date          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_recherche_date ON recherche_log(date);
CREATE INDEX IF NOT EXISTS ix_recherche_med ON recherche_log(medicament_id);

CREATE TABLE IF NOT EXISTS tentative_connexion (
    id   INTEGER PRIMARY KEY,
    cle  TEXT NOT NULL,
    date TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tentative_cle ON tentative_connexion(cle, date);

-- Lot d'import CSV en attente de confirmation (aperçu avant écriture)
CREATE TABLE IF NOT EXISTS import_lot (
    token        TEXT PRIMARY KEY,
    pharmacie_id INTEGER NOT NULL REFERENCES pharmacie(id),
    lignes_json  TEXT NOT NULL,
    cree_le      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parametre (
    cle    TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);
