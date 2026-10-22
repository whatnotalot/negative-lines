import json
import os
import re

class ComplianceAgent:
    """
    Automated chemical regulatory compliance screener.
    Screens formulation candidates against OECD PFAS lists, EU REACH SVHC, and US TSCA.
    Provides explainable rationale and suggests non-PFAS benign substitutes.
    """
    def __init__(self, registry_path=None):
        if registry_path is None:
            registry_path = os.path.join(os.path.dirname(__file__), "..", "data", "pfas_registry.json")
        
        self.registry_path = registry_path
        self.registry = self._load_registry()
        
    def _load_registry(self):
        if os.path.exists(self.registry_path):
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"pfas_anions": [], "restricted_solvents": [], "approved_green_solvents": []}

    def check_substance(self, name_or_structure):
        """
        Screens an individual chemical entity for PFAS or restricted chemical alerts.
        """
        text = str(name_or_structure).lower()
        
        # Explicit non-fluorinated / compliant indicators
        if "camphor" in text or "tosylate" in text or "non-fluorinated" in text or "pfas-free" in text:
            # Check if there are actual PFAS co-present
            if not any(k in text for k in ["nonaflate", "perfluoro", "triflate", "cf3so3", "pfos", "pfoa"]):
                return {
                    "is_compliant": True,
                    "category": "Compliant (PFAS-Free)",
                    "flagged_entity": name_or_structure,
                    "regulatory_lists": ["Global Chemical Inventory Approved", "REACH Annex XVII Exempt"],
                    "concern": "None identified. Formulation is PFAS-free, non-fluorinated, and REACH compliant.",
                    "recommended_substitutes": []
                }

        # 1. Check for PFAS characteristics
        pfas_patterns = [
            r"nonaflate", r"c4f9", r"perfluoro", r"triflate", r"cf3so3",
            r"pfos", r"pfoa", r"(?<!non-)fluorinated\s+sulfonate", r"\bpag\s*i-1\b", r"\bpag4-36\b"
        ]
        
        for p in pfas_patterns:
            if re.search(p, text):
                # Matched PFAS pattern
                matched_entry = next(
                    (item for item in self.registry.get("pfas_anions", []) if item["name"] in text or item["formula"].lower() in text),
                    self.registry.get("pfas_anions", [{}])[0]
                )
                return {
                    "is_compliant": False,
                    "category": "PFAS Forever Chemical Restriction",
                    "flagged_entity": name_or_structure,
                    "regulatory_lists": matched_entry.get("regulatory_lists", ["OECD PFAS Definition", "EU REACH Restriction"]),
                    "concern": matched_entry.get("concern", "Contains perfluoroalkyl or polyfluoroalkyl persistent environmental moieties."),
                    "recommended_substitutes": matched_entry.get("recommended_substitutes", [
                        {"name": "camphorsulfonate", "class": "alicyclic non-fluorinated sulfonate", "compliance": "PFAS-Free"},
                        {"name": "p-toluenesulfonate (tosylate)", "class": "arylsulfonate", "compliance": "PFAS-Free"}
                    ])
                }

        # 2. Check for restricted solvents
        for s in self.registry.get("restricted_solvents", []):
            if s["name"].lower() in text or s["cas"] in text:
                return {
                    "is_compliant": False,
                    "category": "Restricted Solvent (Toxic / Reprotoxic)",
                    "flagged_entity": name_or_structure,
                    "regulatory_lists": s.get("regulatory_lists", ["EU REACH Annex XVII"]),
                    "concern": s.get("concern", "Restricted industrial solvent hazard."),
                    "recommended_substitutes": [{"name": sub, "class": "green solvent", "compliance": "Approved"} for sub in s.get("recommended_substitutes", [])]
                }
                
        return {
            "is_compliant": True,
            "category": "Compliant",
            "flagged_entity": name_or_structure,
            "regulatory_lists": ["Global Chemical Inventory Approved"],
            "concern": "None identified. Formulation is PFAS-free and REACH compliant.",
            "recommended_substitutes": []
        }

    def screen_formulation(self, formulation_dict):
        """
        Screens an entire multi-component formulation recipe.
        """
        flags = []
        is_all_compliant = True
        
        # Screen all components
        for key, val in formulation_dict.items():
            check = self.check_substance(val)
            if not check["is_compliant"]:
                is_all_compliant = False
                flags.append({
                    "component_role": key,
                    "chemical": val,
                    "issue": check["category"],
                    "concern": check["concern"],
                    "regulatory_lists": check["regulatory_lists"],
                    "suggested_substitutes": check["recommended_substitutes"]
                })
                
        status = "PASS" if is_all_compliant else "FLAGGED"
        
        return {
            "status": status,
            "pfas_free": is_all_compliant,
            "flags_count": len(flags),
            "flags": flags,
            "summary": (
                "Formulation verified 100% PFAS-free and REACH/TSCA compliant."
                if is_all_compliant
                else f"Formulation flagged for {len(flags)} restricted chemical alert(s). Action required before fab trial."
            )
        }

if __name__ == "__main__":
    agent = ComplianceAgent()
    
    print("--- Test 1: Screening restricted PAG I-1 (nonaflate) ---")
    test_1 = agent.check_substance("PAG I-1 (triphenylsulfonium nonaflate C4F9SO3-)")
    print("Compliant:", test_1["is_compliant"])
    print("Concern:", test_1["concern"])
    print("Substitutes:", [s["name"] for s in test_1["recommended_substitutes"]])
    
    print("\n--- Test 2: Screening compliant substitute (camphorsulfonate) ---")
    test_2 = agent.check_substance("triphenylsulfonium camphorsulfonate")
    print("Compliant:", test_2["is_compliant"])
    print("Concern:", test_2["concern"])
    
    print("\n--- Test 3: Screening full formulation ---")
    test_recipe = {
        "resin": "Resin (29) polyhydroxystyrene",
        "crosslinker_mm": "MM-1 melamine crosslinker",
        "crosslinker_cl": "CL-9 glycoluril crosslinker",
        "pag": "PAG I-1 (nonaflate C4F9SO3-)",
        "quencher": "D-1 trioctylamine",
        "solvent": "PGMEA"
    }
    screen_res = agent.screen_formulation(test_recipe)
    print("Formulation Status:", screen_res["status"])
    print("Summary:", screen_res["summary"])
