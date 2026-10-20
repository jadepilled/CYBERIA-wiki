"""Extract loot, spawn and server-balance data from a DayZ mission folder.

    python extract/mission.py --purez <PureZ mission folder> --out data/mission.json

The folder uses the standard DayZ mission layout (db/types.xml, cfgspawnabletypes.xml, ...).
"""
import argparse, json, os, re
import xml.etree.ElementTree as ET


def _xml(path):
    return ET.parse(path).getroot() if os.path.exists(path) else None


def types(mission):
    out = {}
    root = _xml(os.path.join(mission, "db/types.xml"))
    for t in root:
        g = lambda k: (t.find(k).text if t.find(k) is not None else None)
        num = lambda k: int(g(k)) if g(k) not in (None, "") else None
        flags = t.find("flags")
        out[t.get("name")] = {
            "nominal": num("nominal"), "min": num("min"),
            "lifetime": num("lifetime"), "restock": num("restock"),
            "quantmin": num("quantmin"), "quantmax": num("quantmax"),
            "category": t.find("category").get("name") if t.find("category") is not None else None,
            "usage": [u.get("name") for u in t.findall("usage")],
            "value": [v.get("name") for v in t.findall("value")],
            "tags": [v.get("name") for v in t.findall("tag")],
            "flags": {k: v == "1" for k, v in flags.attrib.items()} if flags is not None else {},
        }
    return out


def presets(mission):
    out = {}
    root = _xml(os.path.join(mission, "cfgrandompresets.xml"))
    for p in root:
        out[p.get("name")] = {
            "kind": p.tag, "chance": float(p.get("chance", 1)),
            "items": [[i.get("name"), float(i.get("chance", 1))] for i in p.findall("item")],
        }
    return out


def spawnable(mission):
    out = {}
    root = _xml(os.path.join(mission, "cfgspawnabletypes.xml"))
    for t in root:
        d = t.find("damage")
        groups = []
        for g in t:
            if g.tag not in ("attachments", "cargo"):
                continue
            entry = {"kind": g.tag}
            if g.get("preset"):
                entry["preset"] = g.get("preset")
            else:
                entry["chance"] = float(g.get("chance", 1))
                entry["items"] = [[i.get("name"), float(i.get("chance", 1))] for i in g.findall("item")]
            groups.append(entry)
        out[t.get("name")] = {
            "damage": [float(d.get("min")), float(d.get("max"))] if d is not None else None,
            "groups": groups,
            "hoarder": t.find("hoarder") is not None,
        }
    return out


def events(mission):
    out = {}
    root = _xml(os.path.join(mission, "db/events.xml"))
    spawns = _xml(os.path.join(mission, "cfgeventspawns.xml"))
    positions = {e.get("name"): len(e.findall("pos")) for e in spawns.findall("event")} if spawns is not None else {}
    for e in root:
        g = lambda k: (e.find(k).text if e.find(k) is not None else None)
        out[e.get("name")] = {
            "nominal": int(g("nominal") or 0), "min": int(g("min") or 0), "max": int(g("max") or 0),
            "lifetime": int(g("lifetime") or 0), "active": g("active") == "1",
            "children": [c.get("type") for c in e.findall("children/child")],
            "positions": positions.get(e.get("name")),
        }
    return out


def globals_(mission):
    root = _xml(os.path.join(mission, "db/globals.xml"))
    return {v.get("name"): float(v.get("value")) if v.get("type") == "1" else int(v.get("value")) for v in root}


def zombies(mission):
    """Infected zones per type with their dynamic density range."""
    root = _xml(os.path.join(mission, "env/zombie_territories.xml"))
    out = {}
    for z in root.iter("zone"):
        e = out.setdefault(z.get("name"), {"zones": 0, "min": 0, "max": 0})
        e["zones"] += 1
        e["min"] += int(z.get("dmin", 0))
        e["max"] += int(z.get("dmax", 0))
    return out


def gameplay(mission):
    path = os.path.join(mission, "cfggameplay.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(mission):
    return {
        "types": types(mission), "spawnable": spawnable(mission), "presets": presets(mission),
        "events": events(mission), "globals": globals_(mission), "zombies": zombies(mission),
        "gameplay": gameplay(mission),
    }


def carried_by(m):
    """Which infected (via presets) can spawn wearing or carrying each item."""
    out = {}
    for zmb, s in m["spawnable"].items():
        if not zmb.lower().startswith("zmb"):
            continue
        for g in s["groups"]:
            p = m["presets"].get(g.get("preset"))
            if not p:
                continue
            total = sum(c for _, c in p["items"]) or 1
            for item, c in p["items"]:
                e = out.setdefault(item, {})
                # chance this preset rolls this item on one zombie of this class
                e[zmb] = round(p["chance"] * c / total, 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--purez", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    purez = load(a.purez)
    data = {"purez": purez, "carriedBy": carried_by(purez)}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"mission: {len(purez['types'])} types, {len(purez['spawnable'])} spawnables, {len(purez['events'])} events -> {a.out}")


if __name__ == "__main__":
    main()
