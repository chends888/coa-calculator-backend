from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import math

app = FastAPI()

origins = [
    "https://coa-calculator.herokuapp.com",
    "http://localhost:3000",
    "localhost:3000",
    # add your Vercel domain(s) here, e.g.:
    # "https://coa-calculator.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- data loading ---
exp_data_file = open(os.path.dirname(__file__) + '/../data/exp_data.json')
exp_data = json.load(exp_data_file)

artisan_data_file = open(os.path.dirname(__file__) + '/../data/artisan_data.json')
artisan_data = json.load(artisan_data_file)

gathering_data_file = open(os.path.dirname(__file__) + '/../data/gathering_data.json')
gathering_data = json.load(gathering_data_file)

monsters_data_file = open(os.path.dirname(__file__) + '/../data/monsters_data.json')
monsters_data = json.load(monsters_data_file)

# Your JSON files are nested by skill, e.g. artisan_data["Smithing"]["Bronze"].
# Merge all top-level skill keys from all three files into one lookup so the
# frontend only needs to send a skill name, not which file it lives in.
# artisan_data.json and gathering_data.json both have a top-level "Alchemy"
# key with different xp values (brew-only vs combined gather+brew). A naive
# spread merge would silently let one clobber the other. Keep them distinct:
# "Alchemy" = gathering_data's combined version (Gather + Brew mode)
# "Alchemy-Brew" = artisan_data's brew-only version (Brew Only mode)
ALL_SKILL_DATA = {**monsters_data, **gathering_data, **artisan_data}
ALL_SKILL_DATA["Alchemy"] = gathering_data["Alchemy"]
ALL_SKILL_DATA["Alchemy-Brew"] = artisan_data["Alchemy"]


# --- original data-serving endpoints (unchanged, kept for compatibility) ---
@app.get("/exp", tags=["exp"])
async def get_exp() -> dict:
    return exp_data


@app.get("/artisan", tags=["artisan"])
async def get_artisan() -> dict:
    return artisan_data


@app.get("/gathering", tags=["gathering"])
async def get_gathering() -> dict:
    return gathering_data


@app.get("/monsters", tags=["monsters"])
async def get_monsters() -> dict:
    return monsters_data


# --- calculation endpoint ---

INVENTORY_SIZE_OVERRIDES = {
    ("Crafting", "Cursed"): 18,
    ("Crafting", "Experience"): 18,
    ("Crafting", "Ice"): 18,
    ("Crafting", "Affliction"): 35,
    ("Mining", "Naturite"): 100,
}
DEFAULT_INVENTORY_SIZE = {
    "Crafting": 36,
    "Mining": 36,
    "Woodcutting": 36,
}


class Boost(BaseModel):
    name: Optional[str] = None
    active: bool
    value: float


class CalculateRequest(BaseModel):
    skill: str
    element_key: str
    level: int
    level_percentage: float
    target_level: int
    boosts: List[Boost] = []
    boosts_equip_sets: List[Boost] = []
    keywords: List[str] = []
    apply_boost_on_smelt: bool = False
    buy_or_smelt_bars: bool = False
    lolli_price: Optional[float] = None


def to_float(val) -> float:
    """Values in the JSON files are stored as strings — convert safely."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def apply_boosts(base_xp, boosts: List[Boost], boosts_equip_sets: List[Boost]) -> int:
    xp = to_float(base_xp)
    for b in boosts:
        if b.active:
            xp *= b.value
    for b in boosts_equip_sets:
        if b.active:
            xp *= b.value
    return math.floor(xp)


def get_inventory_size(skill: str, element_name: str) -> Optional[int]:
    if (skill, element_name) in INVENTORY_SIZE_OVERRIDES:
        return INVENTORY_SIZE_OVERRIDES[(skill, element_name)]
    return DEFAULT_INVENTORY_SIZE.get(skill)


@app.post("/calculate", tags=["calculate"])
async def calculate(req: CalculateRequest) -> Dict[str, Any]:
    data_source = ALL_SKILL_DATA.get(req.skill)
    if data_source is None or req.element_key not in data_source:
        # Baits share a tab/skill name with their parent skill in the frontend
        # (e.g. "Fishing" -> "Bass bait", which actually lives under "Fishing-Baits")
        fallback_map = {
            "Fishing": "Fishing-Baits",
            "Cooking": "Cooking-Baits",
        }
        fallback_skill = fallback_map.get(req.skill)
        if fallback_skill:
            fallback_source = ALL_SKILL_DATA.get(fallback_skill)
            if fallback_source and req.element_key in fallback_source:
                data_source = fallback_source

    if data_source is None or req.element_key not in data_source:
        return {"error": "Unknown skill or element"}

    element_data = data_source[req.element_key]

    if str(req.level) not in exp_data or str(req.level + 1) not in exp_data or str(req.target_level) not in exp_data:
        return {"error": "Unknown level in exp_data"}

    current_level_exp = to_float(exp_data[str(req.level)]) + (
        to_float(exp_data[str(req.level + 1)]) - to_float(exp_data[str(req.level)])
    ) * (req.level_percentage / 100)
    target_level_exp = to_float(exp_data[str(req.target_level)])
    exp_gap = math.ceil(target_level_exp - current_level_exp)

    result: Dict[str, Any] = {"exp_gap": exp_gap}
    if exp_gap <= 0:
        return result

    boosts, equip = req.boosts, req.boosts_equip_sets

    # --- Combat ---
    if req.skill == "Combat":
        xp = apply_boosts(element_data["xp"], boosts, equip)
        total = math.ceil(exp_gap / xp) if xp else 0
        result["primary"] = {
            "label": req.element_key,
            "value": total,
            "xp_per_unit": to_float(element_data["xp"]),
        }
        result["gold"] = {
            "total": total * to_float(element_data["gold"]),
            "per_kill": to_float(element_data["gold"]),
        }
        return result

    # --- Smithing ---
    if req.skill == "Smithing":
        forge_xp = to_float(element_data.get("xp-forge", 0))
        smelt_xp = to_float(element_data.get("xp-smelt", 0))

        if req.buy_or_smelt_bars:
            xp = apply_boosts(forge_xp, boosts, equip)
        elif forge_xp == 0:
            # Smelt-only materials (e.g. Naturite) have no forge step at all,
            # so "apply boost on smelt" toggling shouldn't blank the result —
            # always compute using boosted smelt xp.
            xp = apply_boosts(smelt_xp, boosts, equip)
        elif req.apply_boost_on_smelt:
            xp = apply_boosts(forge_xp, boosts, equip) + apply_boosts(smelt_xp, boosts, equip)
        else:
            xp = apply_boosts(forge_xp, boosts, equip) + smelt_xp

        total = math.ceil(exp_gap / xp) if xp else 0
        result["primary"] = {
            "label": f"{req.element_key} {req.keywords[0] if req.keywords else ''}".strip(),
            "value": total,
        }

    # --- Crafting ---
    elif req.skill == "Crafting":
        xp = apply_boosts(element_data["xp"], boosts, equip)
        total = math.ceil(exp_gap / xp) if xp else 0
        label = (
            f"{req.element_key} Relics"
            if req.element_key == "Cursed"
            else f"{req.keywords[0] if req.keywords else ''} {req.element_key}".strip()
        )
        result["primary"] = {"label": label, "value": total}

    # --- Everything else: Cooking, Cooking-Baits, Mining, Woodcutting,
    #     Fishing, Fishing-Baits, Spellbinding, Alchemy, Alchemy-Gathering ---
    else:
        xp = apply_boosts(element_data["xp"], boosts, equip)
        total = math.ceil(exp_gap / xp) if xp else 0
        label = f"{req.keywords[0] if req.keywords else ''} {req.element_key}".strip()
        result["primary"] = {"label": label, "value": total}

    # --- subelements ---
    submaterials = element_data.get("submaterials")
    if submaterials:
        subelements = []
        for name, qty in submaterials.items():
            if req.skill == "Cooking" and name == req.element_key:
                # Cooking (e.g. Anchovies) lists the resource itself as one
                # of its own "submaterials" alongside genuine ingredients
                # (e.g. Anchovies -> {"Anchovies": 1, "Salt": 1}) — that's a
                # genuine duplicate of the primary line, so skip it here.
                # Other skills (e.g. Smithing's Naturite -> {"Naturite": 1})
                # use a self-referencing submaterial as their only real line,
                # so this skip must not apply to them.
                continue
            qty = to_float(qty)
            if req.skill == "Smithing":
                forge_xp = to_float(element_data.get("xp-forge", 0))
                smelt_xp = to_float(element_data.get("xp-smelt", 0))
                if req.buy_or_smelt_bars:
                    xp = apply_boosts(smelt_xp, boosts, equip) if forge_xp == 0 else apply_boosts(forge_xp, boosts, equip)
                elif forge_xp == 0:
                    xp = apply_boosts(smelt_xp, boosts, equip)
                elif req.apply_boost_on_smelt:
                    xp = apply_boosts(forge_xp, boosts, equip) + apply_boosts(smelt_xp, boosts, equip)
                else:
                    xp = apply_boosts(forge_xp, boosts, equip) + smelt_xp
            else:
                xp = apply_boosts(element_data["xp"], boosts, equip)

            if xp:
                subelements.append({"name": name, "value": math.ceil(exp_gap / xp) * qty})
        result["subelements"] = subelements

    # --- inventories ---
    inv_size = get_inventory_size(req.skill, req.element_key)
    if req.skill == "Cooking":
        inv_size = 18
    if inv_size and req.skill != "Smithing":
        xp = apply_boosts(element_data["xp"], boosts, equip)
        result["inventories"] = {
            "size": inv_size,
            "value": math.ceil(exp_gap / xp / inv_size) if xp else None,
        }

    # --- Fishing / Bass bait special case ---
    if req.skill in ("Fishing", "Fishing-Baits") and req.element_key == "Bass bait" and req.lolli_price is not None:
        xp = apply_boosts(element_data["xp"], boosts, equip)
        if xp:
            trips = math.ceil(exp_gap / xp / 34)
            result["remote_bank"] = {
                "trips": trips,
                "price": math.ceil(trips * req.lolli_price * 0.4),
            }

    return result
