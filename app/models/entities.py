"""Modèles : objets immuables construits depuis les lignes SQL (aucune logique d'accès aux données)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..core import dates


def _col(row, name, default=None):
    try:
        return row[name]
    except (IndexError, KeyError):
        return default


@dataclass(frozen=True)
class Quartier:
    id: int
    nom: str

    @classmethod
    def from_row(cls, r):
        return cls(r["id"], r["nom"])


@dataclass(frozen=True)
class Pharmacie:
    id: int
    nom: str
    adresse: str
    telephone: str
    quartier_id: int
    quartier_nom: str
    actif: bool
    email: str | None = None

    @classmethod
    def from_row(cls, r):
        return cls(r["id"], r["nom"], r["adresse"], r["telephone"], r["quartier_id"],
                   r["quartier_nom"], bool(r["actif"]), _col(r, "email"))

    @property
    def tel_lien(self) -> str:
        return "tel:" + "".join(c for c in self.telephone if c.isdigit() or c == "+")

    @property
    def nom_quartier(self) -> str:
        return f"{self.nom}, {self.quartier_nom}"


@dataclass(frozen=True)
class Medicament:
    id: int
    nom: str
    dosage: str
    forme: str
    conditionnement: str
    principe_actif_id: int | None = None
    principe_actif: str | None = None
    deja_en_stock: bool = False

    @classmethod
    def from_row(cls, r):
        return cls(r["id"], r["nom"], r["dosage"], r["forme"], r["conditionnement"],
                   _col(r, "principe_actif_id"), _col(r, "principe_actif"),
                   bool(_col(r, "deja_en_stock", 0)))

    @property
    def libelle(self) -> str:
        return f"{self.nom} {self.dosage}"


@dataclass(frozen=True)
class LigneStock:
    pharmacie_id: int
    medicament_id: int
    quantite: int
    prix: int
    updated_at: datetime
    nom: str
    dosage: str
    forme: str
    conditionnement: str
    # Champs de jointure (recherche publique)
    pharmacie_nom: str | None = None
    adresse: str | None = None
    telephone: str | None = None
    quartier_nom: str | None = None
    de_garde: bool = False

    @classmethod
    def from_row(cls, r):
        return cls(r["pharmacie_id"], r["medicament_id"], r["quantite"], r["prix"],
                   dates.parse(r["updated_at"]), r["nom"], r["dosage"], r["forme"],
                   r["conditionnement"], _col(r, "pharmacie_nom"), _col(r, "adresse"),
                   _col(r, "telephone"), _col(r, "quartier_nom"), bool(_col(r, "de_garde", 0)))

    @property
    def libelle(self) -> str:
        return f"{self.nom} {self.dosage}"

    @property
    def tel_lien(self) -> str:
        return "tel:" + "".join(c for c in (self.telephone or "") if c.isdigit() or c == "+")


@dataclass(frozen=True)
class Garde:
    id: int
    pharmacie_id: int
    debut: datetime
    fin: datetime
    pharmacie_nom: str | None = None
    quartier_nom: str | None = None
    adresse: str | None = None
    telephone: str | None = None
    pharmacie_actif: bool = True

    @classmethod
    def from_row(cls, r):
        return cls(r["id"], r["pharmacie_id"], dates.parse(r["date_debut"]), dates.parse(r["date_fin"]),
                   _col(r, "pharmacie_nom"), _col(r, "quartier_nom"), _col(r, "adresse"),
                   _col(r, "telephone"), bool(_col(r, "pharmacie_actif", 1)))

    @property
    def tel_lien(self) -> str:
        return "tel:" + "".join(c for c in (self.telephone or "") if c.isdigit() or c == "+")

    @property
    def type_garde(self) -> str:
        h = dates.local(self.debut).hour
        return "Garde de jour" if 6 <= h < 15 else "Garde de nuit"


@dataclass(frozen=True)
class Utilisateur:
    id: int
    email: str
    mot_de_passe_hash: str
    role: str
    pharmacie_id: int | None
    actif: bool
    pharmacie_nom: str | None = None
    quartier_nom: str | None = None
    pharmacie_actif: bool = True

    @classmethod
    def from_row(cls, r):
        return cls(r["id"], r["email"], r["mot_de_passe_hash"], r["role"], r["pharmacie_id"],
                   bool(r["actif"]), _col(r, "pharmacie_nom"), _col(r, "quartier_nom"),
                   bool(_col(r, "pharmacie_actif", 1)))

    @property
    def pharmacie_label(self) -> str:
        return f"{self.pharmacie_nom}, {self.quartier_nom}" if self.pharmacie_nom else ""

    @property
    def peut_se_connecter(self) -> bool:
        return self.actif and (self.role == "admin" or self.pharmacie_actif)
