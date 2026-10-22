"""PAG anion library and structure descriptors for PFAS-free substitution screening.

The gold set does not yet carry PAG structures, so this module is a structure-only map, not a trained
model: it places fluorinated anions used in chemically amplified resists next to non-fluorinated ones
using descriptors computed by RDKit:

  * size (Labute ASA, Å²): larger anions diffuse less, which favors resolution and LER;
  * electron-withdrawing pull at the acid site: sum over F atoms of 1/d² and nitro N of 2/d², where d is
    the bond distance to the anionic head atom (S of SO3-, or the central N/C). Perfluoroalkyl groups next
    to the sulfonate score highest; this is a proxy for conjugate-acid strength and hence sensitivity.
  * mean Gasteiger charge on the head group is kept for reference; it is too local to rank sulfonates.

Both are proxies. Ranking candidates here says what to test, not what will work.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .compliance import oecd_pfas_smiles

LIBRARY = [
    # name, SMILES, class, note
    ("triflate", "[O-]S(=O)(=O)C(F)(F)F", "perfluoroalkylsulfonate", "classic strong-acid PAG anion"),
    ("nonaflate (PFBS)", "[O-]S(=O)(=O)C(F)(F)C(F)(F)C(F)(F)C(F)(F)F", "perfluoroalkylsulfonate",
     "flagged in US7432034B2 (I-1, PAG4-36)"),
    ("perfluorooctanesulfonate (PFOS)", "[O-]S(=O)(=O)" + "C(F)(F)" * 7 + "F", "perfluoroalkylsulfonate",
     "Stockholm Convention POP"),
    ("adamantanecarbonyloxy-difluoroethanesulfonate", "[O-]S(=O)(=O)C(F)(F)COC(=O)C12CC3CC(CC(C3)C1)C2",
     "partially fluorinated sulfonate", "bulky low-diffusion anion of modern ArF/EUV PAGs"),
    ("bis(triflyl)imide", "[N-](S(=O)(=O)C(F)(F)F)S(=O)(=O)C(F)(F)F", "fluorinated imide", "superacid conjugate base"),
    ("tris(triflyl)methide", "[C-](S(=O)(=O)C(F)(F)F)(S(=O)(=O)C(F)(F)F)S(=O)(=O)C(F)(F)F",
     "fluorinated methide", "superacid conjugate base"),
    ("3,5-bis(CF3)benzenesulfonate", "[O-]S(=O)(=O)c1cc(cc(c1)C(F)(F)F)C(F)(F)F", "CF3-arenesulfonate", ""),
    ("4-(CF3)benzenesulfonate", "[O-]S(=O)(=O)c1ccc(cc1)C(F)(F)F", "CF3-arenesulfonate", ""),
    ("hexafluoroantimonate", "F[Sb-](F)(F)(F)(F)F", "inorganic fluoroanion", "Cyracure 6974 anion; antimony"),
    ("hexafluorophosphate", "F[P-](F)(F)(F)(F)F", "inorganic fluoroanion", "Cyracure UVI-6990 anion"),
    ("tetrakis(pentafluorophenyl)borate",
     "[B-](c1c(F)c(F)c(F)c(F)c1F)(c1c(F)c(F)c(F)c(F)c1F)(c1c(F)c(F)c(F)c(F)c1F)c1c(F)c(F)c(F)c(F)c1F",
     "aryl-F borate", "aromatic C-F only"),
    ("pentafluorobenzenesulfonate", "[O-]S(=O)(=O)c1c(F)c(F)c(F)c(F)c1F", "aryl-F sulfonate", "aromatic C-F only"),
    ("10-camphorsulfonate", "CC1(C)C2CCC1(CS(=O)(=O)[O-])C(=O)C2", "alkylsulfonate", "non-fluorinated, bulky"),
    ("1-adamantylmethanesulfonate", "[O-]S(=O)(=O)CC12CC3CC(CC(C3)C1)C2", "alkylsulfonate", "non-fluorinated, bulky"),
    ("methanesulfonate", "CS(=O)(=O)[O-]", "alkylsulfonate", "small, diffuses fast"),
    ("p-toluenesulfonate", "Cc1ccc(cc1)S(=O)(=O)[O-]", "arenesulfonate", ""),
    ("benzenesulfonate", "[O-]S(=O)(=O)c1ccccc1", "arenesulfonate", ""),
    ("2,4,6-triisopropylbenzenesulfonate", "CC(C)c1cc(C(C)C)c(S(=O)(=O)[O-])c(C(C)C)c1", "arenesulfonate",
     "bulky"),
    ("dodecylbenzenesulfonate", "CCCCCCCCCCCCc1ccc(cc1)S(=O)(=O)[O-]", "arenesulfonate", "surfactant-like"),
    ("2-naphthalenesulfonate", "[O-]S(=O)(=O)c1ccc2ccccc2c1", "arenesulfonate", ""),
    ("4-nitrobenzenesulfonate", "[O-]S(=O)(=O)c1ccc(cc1)[N+](=O)[O-]", "EWG-arenesulfonate",
     "electron-withdrawing, non-fluorinated"),
    ("2,4-dinitrobenzenesulfonate", "[O-]S(=O)(=O)c1ccc(cc1[N+](=O)[O-])[N+](=O)[O-]", "EWG-arenesulfonate",
     "electron-withdrawing, non-fluorinated"),
]


def _head_atoms(mol) -> list[int]:
    """Atoms of the anionic head: the charged atom plus O on the same S, or all F on a central MF6/B."""
    charged = [a for a in mol.GetAtoms() if a.GetFormalCharge() < 0 and a.GetSymbol() != "O"
               or (a.GetFormalCharge() < 0 and a.GetSymbol() == "O" and
                   any(n.GetSymbol() == "S" for n in a.GetNeighbors()))]
    idx = set()
    for a in charged:
        idx.add(a.GetIdx())
        for n in a.GetNeighbors():
            if n.GetSymbol() == "S":
                idx |= {o.GetIdx() for o in n.GetNeighbors() if o.GetSymbol() == "O"}
            if a.GetSymbol() in ("Sb", "P", "B", "N", "C"):
                idx.add(n.GetIdx())
    return sorted(idx)


def describe(smiles: str) -> dict | None:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    from rdkit.Chem.rdPartialCharges import ComputeGasteigerCharges

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    ComputeGasteigerCharges(mol)
    head = _head_atoms(mol)
    charges = [mol.GetAtomWithIdx(i).GetDoubleProp("_GasteigerCharge") for i in head]
    charges = [q for q in charges if np.isfinite(q)]
    n_f = sum(a.GetSymbol() == "F" for a in mol.GetAtoms())
    metals = sorted({a.GetSymbol() for a in mol.GetAtoms() if a.GetSymbol() in ("Sb", "As", "Sn", "Hf", "Zr")})
    centers = [a.GetIdx() for a in mol.GetAtoms() if a.GetSymbol() == "S" and
               any(n.GetFormalCharge() < 0 for n in a.GetNeighbors())]
    centers += [a.GetIdx() for a in mol.GetAtoms() if a.GetFormalCharge() < 0 and a.GetSymbol() in ("N", "C")]
    pull = np.nan
    if centers:
        dm = Chem.GetDistanceMatrix(mol)
        pull = 0.0
        for a in mol.GetAtoms():
            d = min(dm[a.GetIdx(), c] for c in centers)
            if a.GetSymbol() == "F" and d > 0:
                pull += 1.0 / d ** 2
            if a.GetSymbol() == "N" and a.GetFormalCharge() > 0 and d > 0:
                pull += 2.0 / d ** 2
    return {
        "smiles": Chem.MolToSmiles(mol),
        "pfas_oecd": bool(oecd_pfas_smiles(smiles)),
        "n_F": n_f,
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "size_ASA": rdMolDescriptors.CalcLabuteASA(mol),
        "mw": Descriptors.MolWt(mol),
        "ewg_pull": float(pull),
        "head_charge": float(np.mean(charges)) if charges else np.nan,
        "metal": ", ".join(metals),
    }


def library_table() -> pd.DataFrame:
    rows = []
    for name, smi, cls, note in LIBRARY:
        d = describe(smi)
        if d:
            rows.append({"anion": name, "class": cls, "note": note, **d})
    df = pd.DataFrame(rows)
    df["status"] = np.where(df["pfas_oecd"], "PFAS (OECD 2021)",
                            np.where(df["n_F"] > 0, "fluorinated, not PFAS", "fluorine-free"))
    return df


def substitutes(df: pd.DataFrame, reference: str, k: int = 5, allow_fluorine: bool = False) -> pd.DataFrame:
    """Nearest non-PFAS anions to `reference` in standardized (size, ewg_pull) space."""
    df = df[df["ewg_pull"].notna()].reset_index(drop=True)
    feats = df[["size_ASA", "ewg_pull"]].to_numpy(float)
    z = (feats - np.nanmean(feats, 0)) / np.nanstd(feats, 0)
    ref = z[df["anion"].to_numpy() == reference][0]
    pool = ~df["pfas_oecd"].to_numpy()
    if not allow_fluorine:
        pool &= df["n_F"].to_numpy() == 0
    pool &= df["metal"].to_numpy() == ""
    d = np.sqrt(((z - ref) ** 2).sum(1))
    out = df.assign(distance=d)[pool].sort_values("distance").head(k)
    return out
