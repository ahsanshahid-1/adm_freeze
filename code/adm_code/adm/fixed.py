"""Fixed contract-driven workflow F (Section 11.1): no LLM, no task-ID branches."""
from __future__ import annotations


def plan_tables(contract: dict, catalog: dict) -> dict:
    """Pick the tables the contract requires, using only contract and catalog metadata."""
    req = set(contract["required_features"])
    joins = contract.get("joins", [])
    aggs = contract.get("aggregates", [])
    tables = []
    for j in joins:
        for t in (j["left"], j["right"]):
            if t not in tables:
                tables.append(t)
    child = [a["child_table"] for a in aggs]
    if not tables:
        best, best_cov = None, -1
        for name, t in sorted(catalog["tables"].items()):
            if t.get("grain") != "observation":
                continue
            cov = len(req & set(t.get("columns", {})))
            if cov > best_cov:
                best, best_cov = name, cov
        tables = [best]
    return {"tables": tables, "child": child}


def contract_graph(contract: dict, catalog: dict, extended: bool = False) -> dict:
    """F's graph. ``extended=True`` builds the oracle reference solver instead (solvability check, ABC II.7-II.8):
    it adds the general repairs for Tier-2 defects outside the declared specification. F itself never uses it."""
    plan = plan_tables(contract, catalog)
    nodes = []
    prepared = {}

    def prep(t: str) -> str:
        cols = catalog["tables"][t].get("columns", {})
        base = f"{t}_load"
        nodes.append({"id": base, "op": "load", "table": t,
                      "policy": "authoritative_verified" if extended else "authoritative"})
        cur = base
        nodes.append({"id": f"{t}_parse", "op": "parse_numeric", "input": cur, "columns": "all"})
        cur = f"{t}_parse"
        nodes.append({"id": f"{t}_canon", "op": "to_canonical", "input": cur})
        cur = f"{t}_canon"
        if extended:
            nodes.append({"id": f"{t}_infer", "op": "infer_representation", "input": cur})
            cur = f"{t}_infer"
        if "observation_id" in cols:
            nodes.append({"id": f"{t}_alias", "op": "map_alias", "input": cur, "key": "observation_id"})
            cur = f"{t}_alias"
            if extended:
                nodes.append({"id": f"{t}_normkey", "op": "normalize_key", "input": cur, "key": "observation_id"})
                cur = f"{t}_normkey"
        nodes.append({"id": f"{t}_dedupe", "op": "dedupe", "input": cur, "mode": "exact"})
        cur = f"{t}_dedupe"
        if extended and catalog["tables"][t].get("grain") == "observation":
            nodes.append({"id": f"{t}_dedupe_key", "op": "dedupe", "input": cur, "mode": "key", "key": "observation_id"})
            cur = f"{t}_dedupe_key"
        return cur

    for t in plan["tables"]:
        prepared[t] = prep(t)
    for t in plan["child"]:
        prepared[t] = prep(t)
    if contract.get("joins"):
        cur = prepared[contract["joins"][0]["left"]]
        for k, j in enumerate(contract["joins"]):
            nid = f"join_{k}"
            nodes.append({"id": nid, "op": "join", "left": cur, "right": prepared[j["right"]], "on": j["keys"],
                          "how": "left", "cardinality": j["required_cardinality"]})
            cur = nid
    else:
        cur = prepared[plan["tables"][0]]
    for k, a in enumerate(contract.get("aggregates", [])):
        aid = f"agg_{k}"
        nodes.append({"id": aid, "op": "aggregate", "input": prepared[a["child_table"]], "key": a["key"],
                      "series_column": a["series_column"], "value_column": a["value_column"], "stats": a["stats"]})
        jid = f"agg_join_{k}"
        nodes.append({"id": jid, "op": "join", "left": cur, "right": aid, "on": [a["key"]], "how": "left",
                      "cardinality": "one_to_one"})
        cur = jid
    nodes.append({"id": "features", "op": "project", "input": cur,
                  "columns": ["observation_id"] + list(contract["required_features"])})
    return {"nodes": nodes, "output": "features"}


def oracle_graph(contract: dict, catalog: dict) -> dict:
    return contract_graph(contract, catalog, extended=True)
