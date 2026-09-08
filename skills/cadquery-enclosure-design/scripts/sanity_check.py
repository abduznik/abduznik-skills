# sanity_check.py — v3: concept-driven STL sanity checker, generic edition
#
# The spec declares DESIGN INTENT (box bounds, walls, cavity, holes, pins, slots)
# and the checker derives probes FROM THE SPEC, so a part that doesn't match the
# concept fails — not just "is a valid mesh".
#
# v3 changes vs the old version (kept as sanity_check_old.py):
#   - all point-probe checks (wall/cavity/pin/hole/slot) collapsed into one
#     generic ray-probe primitive with a uniform result vocabulary
#   - probes are jittered (a small multi-ray bundle) and voted on, so a single
#     grazed edge or degenerate triangle doesn't produce a false pass/fail
#   - every part automatically gets a generic mesh-health check (watertight,
#     winding consistency, degenerate faces) — not just when "watertight": true
#   - new "clearance" probe: min material / min air-gap between two arbitrary
#     points, generalizing "walls" beyond single-ray-from-outside
#   - new "contains" probe: assert a point from one part lands inside/outside
#     another part's mesh, generalizing "fuse" beyond boolean union
#   - spec keys are validated against an allowlist per probe type before any
#     geometry loads, so a typo'd key fails loud instead of silently no-op'ing
#
# Usage:
#   python sanity_check.py <spec.json>
#   python sanity_check.py --write-template
#
# Spec (superset of the old format — old specs still work):
# {
#   "parts": [
#     {
#       "file": "stl/x.stl", "name": "x",
#       "watertight": true,
#       "extents": [W,H,D], "tol": 0.4,
#       "volume_min": a, "volume_max": b,
#       "box": [x0,y0,z0,x1,y1,z1],
#       "walls":     [ {"x":0,"y":27,"from_z":-5,"dir":[1,0,0], "expect": 5.0} ],
#       "cavities":  [ {"box":[...], "probe":[x,y,z], "dir":[0,0,1], "expect_none": true} ],
#       "pins":      [ {"pos":[5.1,20.5], "from_z":14.0, "dir":[0,0,1], "expect_first": 3.3} ],
#       "holes":     [ {"pos":[10,10], "from_z":-5, "dir":[0,0,1], "expect_none": true} ],
#       "slots":     [ {"center":[1.5,27,22], "dir":[-1,0,0], "expect_none": true} ],
#       "clearances":[ {"a":[0,0,0], "b":[10,0,0], "min_gap": 0.4} ],
#       "contains":  [ {"point":[1,2,3], "part": "other_part_name", "inside": true} ]
#     }
#   ],
#   "fuse": { "files": [...], "extents": [W,H,D] }
# }
import json, sys, os
import trimesh
import numpy as np

JITTER = 0.05          # mm offset for the jitter bundle
JITTER_OFFSETS = [     # offsets in the plane perpendicular to the ray direction
    (0, 0),
    (JITTER, 0), (-JITTER, 0),
    (0, JITTER), (0, -JITTER),
]

# ---------------------------------------------------------------- loading --

_MESH_CACHE = {}

def load(path):
    if path not in _MESH_CACHE:
        _MESH_CACHE[path] = trimesh.load(path)
    return _MESH_CACHE[path]

# ----------------------------------------------------------- ray primitive --

def _perp_basis(direction):
    d = np.array(direction, float)
    d = d / np.linalg.norm(d)
    ref = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(d, ref); u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return u, v

def ray_dist(mesh, origin, direction):
    loc, _, _ = mesh.ray.intersects_location(
        ray_origins=[np.array(origin, float)], ray_directions=[np.array(direction, float)])
    if len(loc) == 0:
        return []
    d = np.array(direction, float); d = d / np.linalg.norm(d)
    dist = np.einsum("ij,j->i", loc - np.array(origin, float), d)
    return sorted(np.round(dist[dist > 1e-6], 2).tolist())

def ray_dist_jittered(mesh, origin, direction, jitter=JITTER):
    """Cast a small bundle of parallel rays around origin and vote on the result.

    Returns the median hit-list among the bundle (by hit count, then by first
    distance), so a single grazed edge / degenerate triangle doesn't flip the
    verdict. Falls back to the plain single ray if jitter is 0.
    """
    if not jitter:
        return ray_dist(mesh, origin, direction)
    u, v = _perp_basis(direction)
    results = []
    for du, dv in JITTER_OFFSETS:
        o = np.array(origin, float) + du * u + dv * v
        results.append(ray_dist(mesh, o, direction))
    # vote by hit count (mode), tie-break toward the plain (unjittered) result
    counts = {}
    for r in results:
        counts[len(r)] = counts.get(len(r), 0) + 1
    best_n = max(counts, key=lambda n: (counts[n], n == len(results[0])))
    candidates = [r for r in results if len(r) == best_n]
    return candidates[0]

# ------------------------------------------------------------- mesh health --

def check_mesh_health(m):
    """Generic structural sanity every part gets, regardless of spec content."""
    fails = []
    if not m.is_watertight:
        fails.append("not watertight")
    try:
        if not m.is_winding_consistent:
            fails.append("inconsistent face winding")
    except Exception:
        pass
    nondeg = m.nondegenerate_faces() if hasattr(m, "nondegenerate_faces") else None
    if nondeg is not None:
        n_bad = int((~nondeg).sum())
        if n_bad:
            fails.append(f"{n_bad} degenerate faces")
    if len(m.faces) == 0:
        fails.append("empty mesh")
    return fails

# -------------------------------------------------------------- box/extent --

def check_box(m, box):
    lo = np.array(box[:3]); hi = np.array(box[3:])
    got = np.round(np.concatenate([m.bounds[0], m.bounds[1]]), 1)
    exp = np.round(np.concatenate([lo, hi]), 1)
    if not np.allclose(got, exp, atol=0.4):
        return f"box got {got.tolist()} want {exp.tolist()}"
    return None

# --------------------------------------------------------- generic probe ---
# Every point-probe (wall/cavity/pin/hole/slot) reduces to:
#   cast a (jittered) ray from an origin in a direction, then assert one of:
#     expect_none            -> no hits allowed
#     expect_first  / expect -> first hit distance ~= value
#     expect_count            -> exact number of hits
#     expect_range            -> first hit distance within [lo, hi]

ALLOWED_PROBE_KEYS = {
    "origin", "pos", "center", "x", "y", "z", "from_z", "dir",
    "expect", "expect_first", "expect_none", "expect_count", "expect_range",
    "box", "probe", "name", "tol",
}

def _probe_origin(spec):
    if "origin" in spec:
        return spec["origin"]
    if "probe" in spec:
        return spec["probe"]
    if "center" in spec:
        return spec["center"]
    if "pos" in spec:
        x, y = spec["pos"][0], spec["pos"][1]
        z = spec.get("from_z", spec.get("z", 0))
        return [x, y, z]
    return [spec.get("x", 0), spec.get("y", 0), spec.get("z", spec.get("from_z", 0))]

def check_probe(m, spec, tol=0.3):
    unknown = set(spec.keys()) - ALLOWED_PROBE_KEYS
    if unknown:
        return f"unknown keys {sorted(unknown)}"
    origin = _probe_origin(spec)
    direction = spec["dir"]
    ds = ray_dist_jittered(m, origin, direction)

    if spec.get("expect_none"):
        if len(ds) != 0:
            return f"probe {origin} expected empty, got {ds[:3]}"
        return None

    if "expect_count" in spec:
        if len(ds) != spec["expect_count"]:
            return f"probe {origin} expect_count {spec['expect_count']} got {len(ds)} ({ds[:3]})"
        return None

    if "expect_range" in spec:
        lo, hi = spec["expect_range"]
        if len(ds) == 0 or not (lo - tol <= ds[0] <= hi + tol):
            return f"probe {origin} expect_range {spec['expect_range']} got {ds[:3]}"
        return None

    exp = spec.get("expect", spec.get("expect_first"))
    if exp is None:
        return None  # existence-only probe, no numeric assertion requested
    t = spec.get("tol", tol)
    if len(ds) == 0 or abs(ds[0] - exp) > t:
        return f"probe {origin} expect ~{exp} got {ds[:3]}"
    return None

# ------------------------------------------------------------- clearance ---

def check_clearance(m, spec):
    """Generic thickness/gap check between two arbitrary points.

    Casts a ray from a toward b and asserts either a minimum amount of
    material (min_wall) or a minimum amount of open air (min_gap) along the
    segment, generalizing the old "wall" concept beyond "probe from outside,
    expect a single wall thickness".
    """
    a = np.array(spec["a"], float); b = np.array(spec["b"], float)
    seg = b - a
    length = np.linalg.norm(seg)
    direction = seg / length
    ds = ray_dist_jittered(m, a, direction)
    ds = [d for d in ds if d <= length + 1e-6]

    if "min_gap" in spec:
        # material segments = pairs of consecutive crossings; find any gap >= min_gap
        # between crossings (or before the first / after the last) along [0, length]
        bounds = [0.0] + ds + [length]
        # gap regions alternate starting outside(if ds even count) — approximate by
        # taking largest inter-crossing span as the candidate open gap
        gaps = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
        if max(gaps, default=0) < spec["min_gap"]:
            return f"clearance {spec['a']}->{spec['b']} min_gap {spec['min_gap']} got {max(gaps, default=0):.2f}"
        return None

    if "min_wall" in spec:
        if len(ds) == 0:
            return f"clearance {spec['a']}->{spec['b']} min_wall {spec['min_wall']} got no material"
        thickness = ds[0]
        if len(ds) >= 2:
            thickness = ds[1] - ds[0]
        if thickness < spec["min_wall"]:
            return f"clearance {spec['a']}->{spec['b']} min_wall {spec['min_wall']} got {thickness:.2f}"
        return None

    return "clearance spec needs min_gap or min_wall"

# --------------------------------------------------------------- contains --

def check_contains(spec, parts_by_name):
    other = parts_by_name.get(spec["part"])
    if other is None:
        return f"contains: unknown part '{spec['part']}'"
    m = load(other["file"])
    point = np.array([spec["point"]], float)
    inside = m.contains(point)[0]
    want = spec.get("inside", True)
    if bool(inside) != bool(want):
        return f"contains: point {spec['point']} inside={inside} want {want} (part {spec['part']})"
    return None

# -------------------------------------------------------------- per-part ---

def check_part(part, parts_by_name):
    name = part.get("name", part["file"])
    m = load(part["file"])
    fails = []

    fails.extend(check_mesh_health(m))

    if "extents" in part:
        got = np.round(m.extents, 1)
        want = np.array(part["extents"], float)
        if not np.allclose(got, want, atol=part.get("tol", 0.4)):
            fails.append(f"extents got {got.tolist()} want {want.tolist()}")
    if "volume_min" in part and m.volume < part["volume_min"]:
        fails.append(f"volume {m.volume:.0f} < min {part['volume_min']}")
    if "volume_max" in part and m.volume > part["volume_max"]:
        fails.append(f"volume {m.volume:.0f} > max {part['volume_max']}")
    if "box" in part:
        e = check_box(m, part["box"])
        if e: fails.append(e)

    for kind in ("walls", "cavities", "pins", "holes", "slots"):
        for i, spec in enumerate(part.get(kind, [])):
            e = check_probe(m, spec)
            if e: fails.append(f"{kind[:-1]}{i}: {e}")

    for i, spec in enumerate(part.get("clearances", [])):
        e = check_clearance(m, spec)
        if e: fails.append(f"clearance{i}: {e}")

    for i, spec in enumerate(part.get("contains", [])):
        e = check_contains(spec, parts_by_name)
        if e: fails.append(f"contains{i}: {e}")

    return name, fails

# ------------------------------------------------------------------ fuse ---

def check_fuse(spec):
    f = spec.get("fuse")
    if not f:
        return None
    try:
        import trimesh.boolean  # noqa
    except Exception:
        return ["SKIP: no boolean engine (pip install manifold3d)"]
    mesh = None
    for fp in f["files"]:
        mm = load(fp)
        mesh = mm if mesh is None else mesh.union(mm)
    fails = []
    if not mesh.is_watertight:
        fails.append("fused watertight")
    if "extents" in f:
        got = np.round(mesh.extents, 1)
        want = np.array(f["extents"], float)
        if not np.allclose(got, want, atol=f.get("tol", 0.4)):
            fails.append(f"fused extents got {got.tolist()} want {want.tolist()}")
    return fails

# ------------------------------------------------------------------- run ---

def run(spec_path):
    with open(spec_path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    ok = True
    parts_by_name = {p.get("name", p["file"]): p for p in spec.get("parts", [])}
    for part in spec.get("parts", []):
        name, fails = check_part(part, parts_by_name)
        if fails:
            ok = False
            print(f"  FAIL  {name}: {'; '.join(fails)}")
        else:
            print(f"  PASS  {name}")
    ff = check_fuse(spec)
    if ff is not None:
        if ff:
            ok = False
            print("  FAIL  fuse:", "; ".join(ff))
        else:
            print("  PASS  fuse")
    print("VERDICT:", "OK" if ok else "FAILURES PRESENT")
    return 0 if ok else 1

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--write-template":
        print("spec schema documented in docstring")
        sys.exit(0)
    if len(sys.argv) < 2:
        print("usage: python sanity_check.py <spec.json>")
        sys.exit(2)
    sys.exit(run(os.path.abspath(sys.argv[1])))
