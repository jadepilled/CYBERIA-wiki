"""Extract diseases, drugs, recoil and crafting data from DayZ Enforce scripts.

    python extract/scripts.py --scripts <path to scripts folder> --out data/scripts.json

Reads 4_world sources: transmission agents, player modifiers, recoil classes, recipes,
and which items activate which modifiers or recoil classes.
"""
import argparse, glob, json, os, re

NUM = r"-?\d+(?:\.\d+)?"


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)


def strip_line_comments(src):
    return re.sub(r"//[^\n]*", "", src)


def class_name(src):
    m = re.search(r"\bclass\s+(\w+)", src)
    return m and m.group(1)


def num(v):
    v = float(v)
    return int(v) if v.is_integer() else v


def constants(src):
    """static/const numeric declarations: const float X = 1.5;"""
    out = {}
    for name, val in re.findall(rf"\bconst\s+(?:int|float)\s+(\w+)\s*=\s*({NUM})\s*;", src):
        out[name] = num(val)
    return out


def members(src, prefix="m_"):
    """Numeric member assignments like m_Invasibility = 0.15;"""
    out = {}
    for name, val in re.findall(rf"\b({prefix}\w+)\s*=\s*({NUM})\s*;", src):
        out[name[len(prefix):] if name.startswith(prefix) else name] = num(val)
    return out


def agent_defaults(root):
    """Drug resistances every agent starts with (agentbase.c), before its own Init()."""
    path = os.path.join(root, "4_world/classes/transmissionagents/agents/agentbase.c")
    src = strip_line_comments(read(path)) if os.path.exists(path) else ""
    return {d.lower(): num(v) for d, v in re.findall(rf"m_DrugResistances\.Insert\(EMedicalDrugsType\.(\w+),\s*({NUM})\)", src)}


def agents(root):
    out = {}
    defaults = agent_defaults(root)
    for path in glob.glob(os.path.join(root, "4_world/classes/transmissionagents/agents/*.c")):
        src = strip_line_comments(read(path))
        m = re.search(r"m_Type\s*=\s*eAgents\.(\w+)", src)
        if not m:
            continue
        a = {"class": class_name(src), **members(src)}
        pot = re.search(r"m_Potency\s*=\s*EStatLevels\.(\w+)", src)
        a["potency"] = (pot.group(1) if pot else "MEDIUM").lower()  # agentbase default
        a["dynamicGrowth"] = "GetInvasibility" in src or "GetDieOffSpeed" in src
        a.pop("AntibioticsResistance", None)  # deprecated in favour of drug resistances
        a["drugResistance"] = dict(defaults) | {d.lower(): num(v) for d, v in
                               re.findall(rf"m_DrugResistances\.Set\(EMedicalDrugsType\.(\w+),\s*({NUM})\)", src)}
        grows = re.findall(r"drugType\s*==\s*EMedicalDrugsType\.(\w+)", src)
        if grows:
            a["specialDrugHandling"] = [g.lower() for g in grows]
        out[m.group(1).lower()] = a
    return out


def modifiers(root):
    """Diseases and drug effects with thresholds, timings and symptoms."""
    out = {}
    for path in glob.glob(os.path.join(root, "4_world/classes/playermodifiers/modifiers/**/*.c"), recursive=True):
        src = strip_line_comments(read(path))
        mid = re.search(r"m_ID\s*=\s*eModifiers\.(\w+)", src)
        if not mid:
            continue
        rel = os.path.relpath(path, os.path.join(root, "4_world/classes/playermodifiers/modifiers"))
        mod = {
            "class": class_name(src),
            "kind": "disease" if rel.startswith("diseases") else ("condition" if rel.startswith("conditions") else "modifier"),
            "constants": constants(src),
            "tickActive": members(src).get("TickIntervalActive"),
            "persistent": bool(re.search(r"m_IsPersistent\s*=\s*true", src)),
            "agents": sorted({a.lower() for a in re.findall(r"eAgents\.(\w+)", src)}),
            "symptoms": sorted({s.lower() for s in re.findall(r"SymptomIDs\.SYMPTOM_(\w+)", src)}),
            "drugs": sorted({d.lower() for d in re.findall(r"EMedicalDrugsType\.(\w+)", src)}),
            "stats": sorted({s for s in re.findall(r"GetStat(\w+)\(\)", src)}),
        }
        kills = re.findall(r"AddAgent\(\s*eAgents\.(\w+)\s*,\s*-\s*(\w+)", src)
        if kills:
            mem = members(src)
            rate = lambda v: mem.get(v[2:]) if v.startswith("m_") else mod["constants"].get(v)
            mod["kills"] = {a.lower(): rate(v) for a, v in kills}
            c = mod["constants"]
            life = next((v for k, v in c.items() if k.endswith("LIFETIME")), None)
            eff = next((v for k, v in c.items() if k.endswith("EFFECT_TIME")), None)
            if life and eff:
                mod["killWindow"] = [life - eff, life]  # seconds after the dose when agents are killed
        out[mid.group(1).lower()] = mod
    return out


def item_modifiers(root):
    """Items whose scripts activate a modifier (drugs, vitamins, ...)."""
    out = {}
    for path in glob.glob(os.path.join(root, "4_world/entities/**/*.c"), recursive=True):
        src = strip_line_comments(read(path))
        acts = re.findall(r"ActivateModifier\(\s*eModifiers\.(\w+)\s*\)", src)
        if not acts:
            continue
        for cls, body in split_classes(src):
            found = sorted({a.lower() for a in re.findall(r"ActivateModifier\(\s*eModifiers\.(\w+)\s*\)", body)})
            if found and cls not in ("PlayerBase", "ModifiersManager"):
                out[cls] = found
    return out


def split_classes(src):
    """Yield (class name, body) for top-level classes."""
    for m in re.finditer(r"\bclass\s+(\w+)[^{;]*\{", src):
        depth, i = 1, m.end()
        while depth and i < len(src):
            depth += {"{": 1, "}": -1}.get(src[i], 0)
            i += 1
        yield m.group(1), src[m.end():i - 1]


def recoil(root):
    out = {}
    for path in glob.glob(os.path.join(root, "4_world/classes/recoilbase/recoils/*.c")):
        src = strip_line_comments(read(path))
        name = class_name(src)
        points = []
        for idx in sorted(set(re.findall(r"point_(\d+)\[0\]", src)), key=int):
            x = re.search(rf"point_{idx}\[0\]\s*=\s*(?:.*?GetRandomInRange\([^,]+,\s*({NUM})\s*,\s*({NUM})\)|({NUM}))\s*;", src)
            y = re.search(rf"point_{idx}\[1\]\s*=\s*({NUM})", src)
            if not (x and y):
                continue
            xr = [num(x.group(1)), num(x.group(2))] if x.group(1) else [num(x.group(3))] * 2
            points.append({"x": sorted(xr), "y": num(y.group(1))})
        r = {k: v for k, v in members(src).items()}
        r["curve"] = points
        out[name] = r
    return out


def weapon_recoil(root):
    """Recoil class per weapon class, following script inheritance (AKM -> AKM_Base)."""
    direct, parent = {}, {}
    for path in glob.glob(os.path.join(root, "4_world/entities/firearms/**/*.c"), recursive=True):
        src = strip_line_comments(read(path))
        for cls, base in re.findall(r"\bclass\s+(\w+)\s*(?::|extends)\s*(\w+)", src):
            parent[cls] = base
        for cls, body in split_classes(src):
            m = re.search(r"SpawnRecoilObject\(\)\s*\{\s*return\s+new\s+(\w+)\(", body)
            if m:
                direct[cls] = m.group(1)
    out = {}
    for cls in parent:
        c = cls
        while c and c not in direct:
            c = parent.get(c)
        if c and direct[c] != "DefaultRecoil":
            out[cls] = direct[c]
    # Concrete weapons (AKM) only exist in config as children of their script base (AKM_Base).
    # Until configs are merged in, assume the BI naming convention X -> X_Base.
    for cls in list(out):
        if cls.endswith("_Base"):
            out.setdefault(cls[:-5], out[cls])
    return out


def recipes(root):
    out = []
    for path in sorted(glob.glob(os.path.join(root, "4_world/classes/recipes/recipes/*.c"))):
        src = strip_line_comments(read(path))
        if "InsertIngredient" not in src:
            continue
        ings = [[], []]
        for idx, cls in re.findall(r"InsertIngredient\(\s*(\d)\s*,\s*\"(\w+)\"", src):
            ings[int(idx)].append(cls)
        name = re.search(r"m_Name\s*=\s*\"([^\"]*)\"", src)
        rec = {
            "class": class_name(src),
            "name": name.group(1) if name else None,
            "ingredients": ings,
            "results": re.findall(r"AddResult\(\s*\"(\w+)\"", src),
            "instant": bool(re.search(r"m_IsInstaRecipe\s*=\s*true", src)),
            "animationLength": members(src).get("AnimationLength"),
        }
        for field in ("MinQuantityIngredient", "MaxDamageIngredient", "IngredientAddQuantity", "IngredientDestroy"):
            vals = {}
            for idx, v in re.findall(rf"m_{field}\[(\d)\]\s*=\s*(true|false|{NUM})\s*;", src):
                vals[int(idx)] = v == "true" if v in ("true", "false") else num(v)
            if vals:
                rec[field[0].lower() + field[1:]] = [vals.get(0), vals.get(1)]
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = {
        "agents": agents(a.scripts),
        "modifiers": modifiers(a.scripts),
        "itemModifiers": item_modifiers(a.scripts),
        "recoil": recoil(a.scripts),
        "weaponRecoil": weapon_recoil(a.scripts),
        "recipes": recipes(a.scripts),
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print("scripts:", {k: len(v) for k, v in data.items()}, "->", a.out)


if __name__ == "__main__":
    main()
