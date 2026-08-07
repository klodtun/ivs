"""Relationship-based module boundaries (P17) — the graphify technique, in-house.

The prefix heuristic in modules.py groups tables only by name (bill1/bill2 → bill).
Real subsystems are defined by *relationships*: an order table linked to a customer
table belongs with it even though the names differ. This builds a weighted table
graph from signals already present in the OpenCLI artifacts (no raw data, no new
heavy dependency, Python 3.9-safe) and runs community detection to find modules.

Signals (all from the persisted manifest — nothing raw is read):
  * implied foreign keys  — a column `customer_id` in `orders` → edge orders↔customer
  * shared name prefix    — bill1/bill2/bill_item → weak edge (keeps prefix behaviour
                            as a baseline so clustering is never worse than modules.py)

Community detection uses networkx's greedy modularity when networkx is installed,
else a dependency-free weighted label-propagation fallback. Either way the output is
the same shape as modules.list_modules, so build_module_brief is unaffected.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from . import reader

# edge weights per signal (higher = stronger pull into the same module)
_W_FK = 4       # implied foreign key — strongest structural signal
_W_PREFIX = 1   # shared name prefix — weak baseline

_FK_SUFFIXES = ("_id", "_code", "_no", "_key", "id", "code")


def _prefix(table: str) -> str:
    """bill3 → bill, customer_location → customer (matches modules._module_of)."""
    head = table.split("_")[0]
    return re.sub(r"\d+$", "", head) or head


def _norm(name: str) -> str:
    """Normalize a table/entity name for FK matching: lowercase, drop a trailing
    plural 's' and trailing digits. orders→order, Customers→customer, bill3→bill."""
    n = re.sub(r"\d+$", "", name.strip().lower())
    if len(n) > 3 and n.endswith("s"):
        n = n[:-1]
    return n


def _tables_from_manifest(imp) -> dict[str, list[str]]:
    """{table_name: [column names]} for every table command in the manifest."""
    manifest = reader.read_manifest(imp) or []
    out: dict[str, list[str]] = {}
    for cmd in manifest:
        src = cmd.get("sourceFile", "")
        if src.startswith("table:"):
            out[src[len("table:"):]] = list(cmd.get("columns") or [])
    return out


def build_edges(tables: dict[str, list[str]]) -> dict[frozenset, float]:
    """Weighted undirected edges between table names from FK + prefix signals."""
    names = list(tables)
    norm_index: dict[str, list[str]] = defaultdict(list)
    for n in names:
        norm_index[_norm(n)].append(n)

    edges: dict[frozenset, float] = defaultdict(float)

    # 1) implied foreign keys from column names
    for t, cols in tables.items():
        for col in cols:
            cl = col.lower()
            base = None
            for suf in _FK_SUFFIXES:
                if cl.endswith(suf) and len(cl) > len(suf):
                    base = cl[: -len(suf)].rstrip("_")
                    break
            if not base:
                continue
            for target in norm_index.get(_norm(base), []):
                if target != t:
                    edges[frozenset((t, target))] += _W_FK

    # 2) shared prefix — weak baseline so prefix-family tables still cluster
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for n in names:
        by_prefix[_prefix(n)].append(n)
    for group in by_prefix.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                edges[frozenset((group[i], group[j]))] += _W_PREFIX

    return dict(edges)


def _detect_networkx(nodes: list[str], edges: dict[frozenset, float]) -> Optional[list[set]]:
    try:
        import networkx as nx
        from networkx.algorithms.community import greedy_modularity_communities
    except Exception:
        return None
    g = nx.Graph()
    g.add_nodes_from(nodes)
    for pair, w in edges.items():
        a, b = tuple(pair)
        g.add_edge(a, b, weight=w)
    try:
        comms = greedy_modularity_communities(g, weight="weight")
        return [set(c) for c in comms]
    except Exception:
        return None


def _detect_greedy(nodes: list[str], edges: dict[frozenset, float]) -> list[set]:
    """Dependency-free greedy modularity clustering (Clauset-Newman-Moore style):
    start every table in its own community, then repeatedly merge the connected
    community pair that most increases modularity Q, stopping when no merge helps.

    Unlike label propagation this resists 'hub' over-merge — a junction table that
    links two subsystems (e.g. po_product bridging po and product) does not collapse
    both into one blob, because that merge lowers modularity. O(n^3) worst case which
    is fine for the table counts OpenCLI sees; caller guards very large graphs."""
    deg: dict[str, float] = defaultdict(float)
    adj: dict[str, dict[str, float]] = {n: {} for n in nodes}
    m = 0.0
    for pair, w in edges.items():
        a, b = tuple(pair)
        adj[a][b] = adj[a].get(b, 0.0) + w
        adj[b][a] = adj[b].get(a, 0.0) + w
        deg[a] += w
        deg[b] += w
        m += w
    if m == 0:
        return [{n} for n in nodes]

    comm: dict[int, set] = {i: {n} for i, n in enumerate(nodes)}
    node_comm: dict[str, int] = {n: i for i, n in enumerate(nodes)}

    def modularity() -> float:
        L: dict[int, float] = defaultdict(float)  # internal edge weight per community
        D: dict[int, float] = defaultdict(float)  # total degree per community
        for c, members in comm.items():
            for n in members:
                D[c] += deg[n]
            for n in members:
                for nb, w in adj[n].items():
                    if node_comm[nb] == c:
                        L[c] += w
            L[c] /= 2.0  # each internal edge counted from both ends
        return sum(L[c] / m - (D[c] / (2 * m)) ** 2 for c in comm)

    improved = True
    while improved and len(comm) > 1:
        improved = False
        base_q = modularity()
        # candidate pairs = communities sharing at least one edge
        pairs: set[frozenset] = set()
        for n in nodes:
            for nb in adj[n]:
                if node_comm[n] != node_comm[nb]:
                    pairs.add(frozenset((node_comm[n], node_comm[nb])))
        best_gain, best_pair = 1e-12, None
        for pr in pairs:
            c1, c2 = tuple(pr)
            merged = comm[c1] | comm[c2]
            for x in merged:
                node_comm[x] = c1
            saved2 = comm.pop(c2)
            comm[c1] = merged
            q = modularity()
            # revert
            comm[c1] = comm[c1] - saved2
            comm[c2] = saved2
            for x in saved2:
                node_comm[x] = c2
            if q - base_q > best_gain:
                best_gain, best_pair = q - base_q, (c1, c2)
        if best_pair:
            c1, c2 = best_pair
            comm[c1] |= comm[c2]
            for x in comm[c2]:
                node_comm[x] = c1
            del comm[c2]
            improved = True

    return list(comm.values())


def _label_for(community: set[str]) -> str:
    """Human module name for a community: the most common name prefix, and if that
    prefix is not itself a table, the shortest table name (usually the parent)."""
    prefixes = defaultdict(int)
    for t in community:
        prefixes[_prefix(t)] += 1
    top = max(sorted(prefixes), key=lambda p: prefixes[p])
    if any(_prefix(t) == top and t == top for t in community) or prefixes[top] > 1:
        return top
    return min(sorted(community), key=len)


def graph_modules(imp) -> Optional[list[dict]]:
    """Relationship-clustered modules, or None if there is no usable signal (caller
    then falls back to the prefix grouping in modules.py). Same shape as
    modules.list_modules: [{module, tables, commands}]."""
    tables = _tables_from_manifest(imp)
    if len(tables) < 2:
        return None
    edges = build_edges(tables)
    if not edges:
        return None  # nothing related → prefix grouping is as good; let caller decide

    nodes = list(tables)
    if len(nodes) > 200:            # keep the O(n^3) greedy pass bounded
        comms = _detect_networkx(nodes, edges) or [{n} for n in nodes]
    else:
        comms = _detect_networkx(nodes, edges) or _detect_greedy(nodes, edges)

    # guard against a degenerate single blob swallowing everything
    if len(comms) == 1 and len(nodes) > 6:
        return None

    used: set[str] = set()
    modules: list[dict] = []
    for comm in comms:
        label = _label_for(comm)
        # keep labels unique (two communities can share a dominant prefix)
        base, k = label, 2
        while label in used:
            label = f"{base}{k}"
            k += 1
        used.add(label)
        modules.append({
            "module": label,
            "tables": sorted(comm),
            "commands": len(comm),
        })
    return sorted(modules, key=lambda m: m["module"])
