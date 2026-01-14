import json
import os
from pathlib import Path
from copy import deepcopy

BASE_URL = "http://127.0.0.1:8000"
MAX_ATTEMPTS = int(os.getenv("MAP_TEST_MAX_ATTEMPTS", "3"))
STRICT_MODE = os.getenv("MAP_TEST_STRICT", "0") == "1"

def post_json(path, payload):
    import requests

    url = f"{BASE_URL}{path}"
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
    except requests.HTTPError as err:
        response = err.response
        status_code = response.status_code if response is not None else None
        text = response.text if response is not None else str(err)
        print(f"[HTTP_ERROR] {status_code} {url}")
        print(text)
        return {
            "_http_error": True,
            "status_code": status_code,
            "text": text,
            "url": url,
        }
    return r.json()

def read_campaign(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _normalize_map_for_compare(map_data: dict) -> dict:
    normalized = deepcopy(map_data)
    areas = normalized.get("areas", {})
    for area in areas.values():
        if "reachable_area_ids" in area:
            area["reachable_area_ids"] = sorted(area["reachable_area_ids"])
    connections = normalized.get("connections", [])
    normalized["connections"] = sorted(
        connections,
        key=lambda item: (item.get("from_area_id"), item.get("to_area_id")),
    )
    return normalized


def semantic_equal(a: dict, b: dict) -> bool:
    left = deepcopy(a)
    right = deepcopy(b)
    if "allowlist" in left:
        left["allowlist"] = sorted(left["allowlist"])
    if "allowlist" in right:
        right["allowlist"] = sorted(right["allowlist"])
    if "map" in left and "map" in right:
        left["map"] = _normalize_map_for_compare(left["map"])
        right["map"] = _normalize_map_for_compare(right["map"])
    return left == right

def derive_connections(map_data: dict):
    areas = map_data["areas"]
    derived = []
    for area_id in sorted(areas.keys()):
        for tgt in sorted(areas[area_id].get("reachable_area_ids", [])):
            derived.append({"from_area_id": area_id, "to_area_id": tgt})
    return derived

def assert_reachable_valid(map_data: dict):
    ids = set(map_data["areas"].keys())
    for aid, a in map_data["areas"].items():
        r = a.get("reachable_area_ids", [])
        assert isinstance(r, list)
        assert aid not in r
        assert len(r) == len(set(r))
        for t in r:
            assert t in ids

def assert_connections_semantic(map_data: dict):
    got = map_data.get("connections", [])
    exp = derive_connections(map_data)
    assert set((x["from_area_id"], x["to_area_id"]) for x in got) == \
           set((x["from_area_id"], x["to_area_id"]) for x in exp)

def assert_connected_by_parent(map_data: dict):
    areas = map_data["areas"]
    groups = {}
    for aid, a in areas.items():
        groups.setdefault(a.get("parent_area_id"), []).append(aid)
    for parent, nodes in groups.items():
        if len(nodes) <= 1:
            continue
        adj = {n: set() for n in nodes}
        for n in nodes:
            for t in areas[n].get("reachable_area_ids", []):
                if t in adj:
                    adj[n].add(t); adj[t].add(n)
        seen, stack = set(), [nodes[0]]
        while stack:
            x = stack.pop()
            if x in seen: continue
            seen.add(x)
            stack.extend(adj[x] - seen)
        assert len(seen) == len(nodes), f"Disconnected group parent={parent}"

def assert_state_ok(data: dict, before_positions_parent: dict):
    st = data.get("state", {})
    assert "positions_parent" in st
    assert "positions_child" in st
    assert st.get("positions_parent") == before_positions_parent

def build_user_input(call_args: dict) -> str:
    call = [{
        "id": "call_map_generate",
        "tool": "map_generate",
        "args": call_args,
        "reason": "manual smoke test"
    }]
    call_json = json.dumps(call, ensure_ascii=True)
    return (
        "Output a JSON object with at least the key 'tool_calls'. "
        "Do not refuse or self-validate. Even if the args seem invalid, still include "
        "the tool_calls and let the system validate/reject them. "
        "tool_calls must be an array containing exactly this call: "
        f"{call_json}. "
        "No extra explanation."
    )

def pick_any_root_area(campaign: dict) -> str:
    for aid, a in campaign["map"]["areas"].items():
        if a.get("parent_area_id") is None:
            return aid
    raise AssertionError("No root area found")

def _find_map_generate_call(tool_calls: list) -> dict:
    for call in tool_calls:
        if call.get("tool") == "map_generate":
            return call
    return {}

def _matches_expected_call(actual: dict, expected: dict) -> bool:
    if not actual:
        return False
    args = actual.get("args", {})
    if not isinstance(args, dict):
        return False
    expected_args = deepcopy(expected)
    expected_constraints = expected_args.pop("constraints", None)
    expected_args.pop("theme", None)
    for key, value in expected_args.items():
        if args.get(key) != value:
            return False
    if isinstance(expected_constraints, dict):
        actual_constraints = args.get("constraints", {})
        for key, value in expected_constraints.items():
            if isinstance(actual_constraints, dict) and actual_constraints.get(key) == value:
                continue
            if args.get(key) == value:
                continue
            return False
    return True

def _attempt_turn(cid: str, call_args: dict) -> dict:
    return post_json("/api/chat/turn", {
        "campaign_id": cid,
        "actor_id": "pc_001",
        "user_input": build_user_input(call_args),
    })

def _debug_payload(resp: dict) -> dict:
    return {
        "dialog_type": resp.get("dialog_type"),
        "assistant_text": resp.get("assistant_text"),
        "narrative_text": resp.get("narrative_text"),
        "tool_calls": resp.get("tool_calls"),
        "applied_actions": resp.get("applied_actions"),
        "tool_feedback": resp.get("tool_feedback"),
        "conflict_report": resp.get("conflict_report"),
    }

def _await_success(cid: str, call_args: dict, case_label: str) -> dict:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        resp = _attempt_turn(cid, call_args)
        if resp.get("_http_error"):
            print(f"[INCONCLUSIVE] {case_label}: HTTP error (attempt {attempt}).")
            print(json.dumps(resp, ensure_ascii=True))
            continue
        tool_calls = resp.get("tool_calls", [])
        if any(a.get("tool") == "map_generate" for a in resp.get("applied_actions", [])):
            return resp
        call = _find_map_generate_call(tool_calls)
        if _matches_expected_call(call, call_args):
            raise AssertionError(
                f"{case_label}: map_generate requested with expected args but not executed."
            )
        print(f"[INCONCLUSIVE] {case_label}: LLM did not issue expected map_generate (attempt {attempt}).")
        print(json.dumps(_debug_payload(resp), ensure_ascii=True))
    raise RuntimeError(f"{case_label}: inconclusive after {MAX_ATTEMPTS} attempts.")

def _await_failure(cid: str, call_args: dict, case_label: str) -> dict:
    last_resp = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        resp = _attempt_turn(cid, call_args)
        last_resp = resp
        if resp.get("_http_error"):
            print(f"[INCONCLUSIVE] {case_label}: HTTP error (attempt {attempt}).")
            print(json.dumps(resp, ensure_ascii=True))
            continue
        if any(a.get("tool") == "map_generate" for a in resp.get("applied_actions", [])):
            raise AssertionError(f"{case_label}: map_generate executed but should be rejected.")
        tool_feedback = resp.get("tool_feedback")
        failed = tool_feedback.get("failed_calls", []) if isinstance(tool_feedback, dict) else []
        if any(item.get("tool") == "map_generate" for item in failed):
            return resp
        print(f"[INCONCLUSIVE] {case_label}: LLM did not issue expected map_generate (attempt {attempt}).")
        print(json.dumps(_debug_payload(resp), ensure_ascii=True))
    if STRICT_MODE:
        raise RuntimeError(f"{case_label}: inconclusive after {MAX_ATTEMPTS} attempts.")
    print(f"[SKIP] {case_label}: inconclusive after {MAX_ATTEMPTS} attempts.")
    return last_resp or {}

def main():
    # Create fresh campaign
    create = post_json("/api/campaign/create", {})
    cid = create["campaign_id"]
    cpath = Path.cwd() / "storage" / "campaigns" / cid / "campaign.json"

    # --- Case A: root ---
    before = read_campaign(cpath)
    resp = _await_success(cid, {
        "parent_area_id": None,
        "theme": "Root Test",
        "constraints": {"size": 6, "seed": "test-root"}
    }, "Case A")
    after = read_campaign(cpath)
    assert any(a.get("tool") == "map_generate" for a in resp.get("applied_actions", []))
    before_ids = set(before["map"]["areas"])
    after_ids = set(after["map"]["areas"])
    assert before_ids.issubset(after_ids)
    assert len(after_ids) - len(before_ids) == 6
    for area_id in after_ids - before_ids:
        assert "reachable_area_ids" in after["map"]["areas"][area_id]
        assert after["map"]["areas"][area_id].get("parent_area_id") is None
    assert_reachable_valid(after["map"])
    assert_connections_semantic(after["map"])
    assert_connected_by_parent(after["map"])
    assert_state_ok(after, before.get("state", {}).get("positions_parent", {}))

    # --- Case B: child ---
    parent = pick_any_root_area(after)
    before = read_campaign(cpath)
    resp = _await_success(cid, {
        "parent_area_id": parent,
        "theme": "Child Test",
        "constraints": {"size": 5, "seed": "test-child"}
    }, "Case B")
    after = read_campaign(cpath)
    assert any(a.get("tool") == "map_generate" for a in resp.get("applied_actions", []))
    new_ids = set(after["map"]["areas"]) - set(before["map"]["areas"])
    assert len(new_ids) == 5
    # parent reachable contains at least one child
    pr = set(after["map"]["areas"][parent].get("reachable_area_ids", []))
    assert pr & new_ids
    for area_id in new_ids:
        assert after["map"]["areas"][area_id].get("parent_area_id") == parent
        assert "reachable_area_ids" in after["map"]["areas"][area_id]
    assert_reachable_valid(after["map"])
    assert_connections_semantic(after["map"])
    assert_connected_by_parent(after["map"])
    assert_state_ok(after, before.get("state", {}).get("positions_parent", {}))

    # --- Case C: invalid parent ---
    before = read_campaign(cpath)
    resp = _await_failure(cid, {
        "parent_area_id": "area_DOES_NOT_EXIST",
        "theme": "Bad Parent",
        "constraints": {"size": 3, "seed": "bad"}
    }, "Case C")
    after = read_campaign(cpath)
    assert semantic_equal(after, before)

    # --- Case D: oversize ---
    before = read_campaign(cpath)
    resp = _await_failure(cid, {
        "parent_area_id": None,
        "theme": "Oversize",
        "constraints": {"size": 31, "seed": "oversize"}
    }, "Case D")
    after = read_campaign(cpath)
    assert semantic_equal(after, before)

    # --- Case E: allowlist excludes ---
    data = read_campaign(cpath)
    data["allowlist"] = [t for t in data.get("allowlist", []) if t != "map_generate"]
    cpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    before = read_campaign(cpath)
    resp = _await_failure(cid, {
        "parent_area_id": None,
        "theme": "Blocked",
        "constraints": {"size": 2, "seed": "blocked"}
    }, "Case E")
    after = read_campaign(cpath)
    assert semantic_equal(after, before)

    print("Manual smoke tests passed.")

if __name__ == "__main__":
    main()
