from __future__ import annotations
from dataclasses import dataclass, field


def _dedup(values: list[str]) -> list[str]:
    """Déduplique une liste en conservant l'ordre d'origine."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


@dataclass
class Produit:
    nom_produit: str
    lieux_de_vente: list[str] = field(default_factory=list)
    taille_format: list[str] = field(default_factory=list)
    categorie: str = ""

    def __post_init__(self) -> None:
        """Nettoyage du nom (espaces multiples, sauts de lignes)."""
        self.nom_produit = " ".join(self.nom_produit.split())
        self.lieux_de_vente = _dedup(
            [s.strip() for s in self.lieux_de_vente if s.strip()]
        )
        self.taille_format = _dedup(
            [s.strip() for s in self.taille_format if s.strip()]
        )

    def to_dict(self) -> dict:
        return {
            "nom": self.nom_produit,
            "lieux_de_vente": self.lieux_de_vente,
            "taille_format": self.taille_format,
            "categorie": self.categorie
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Produit":
        return cls(
            nom_produit=data.get("nom", ""),
            lieux_de_vente=list(data.get("lieux_de_vente") or []),
            taille_format=list(data.get("taille_format") or []),
            categorie=data.get("categorie", "")
        )


def fusionner(produits: list[Produit]) -> list[Produit]:
    """Fusionne les doublons basés sur le nom du produit."""
    par_nom: dict[str, Produit] = {}
    for produit in produits:
        cle = (produit.nom_produit.lower(), produit.categorie)
        existant = par_nom.get(cle)
        if existant is None:
            par_nom[cle] = produit
            continue
        existant.lieux_de_vente = _dedup(
            existant.lieux_de_vente + produit.lieux_de_vente
        )
        existant.taille_format = _dedup(
            existant.taille_format + produit.taille_format
        )

    return list(par_nom.values())