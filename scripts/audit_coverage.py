#!/usr/bin/env python3
"""Python 3.11+: audit a coverage ledger; never assert semantic completeness."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

STATUSES = {"not_started", "partial", "complete"}
DISPOSITIONS = {"covered", "merged", "excluded", "pending"}
KINDS = {"concept", "claim", "method", "case", "number", "boundary",
         "counterexample", "question", "theme", "other"}

def audit(path):
    path = Path(path).resolve()
    d = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    def require(ok, message):
        if not ok:
            errors.append(message)
        return ok
    src = d["source"]
    pages = src["pages"]
    if type(pages) is not int or not 0 < pages <= 100000:
        raise ValueError("source.pages must be an integer from 1 to 100000")
    source = (path.parent / src["path"]).resolve()
    require(source.is_file(), "source file missing")
    digest = src.get("sha256", "")
    require(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", digest)),
            "source.sha256 must be 64 hex characters")
    if source.is_file():
        with source.open("rb") as stream:
            actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        require(actual_digest == digest.lower(), "source hash mismatch")
    def span(row, label):
        a, b = row.get("start"), row.get("end")
        if not require(type(a) is int and type(b) is int and 1 <= a <= b <= pages,
                       f"{label}: invalid page range"):
            return set()
        return set(range(a, b + 1))
    scopes = {}
    for name in ("included", "excluded"):
        scopes[name] = set()
        for i, row in enumerate(d["scope"][name]):
            s = span(row, f"{name}[{i}]")
            require(not (scopes[name] & s), f"overlap within scope.{name}")
            scopes[name] |= s
            if name == "excluded":
                require(bool(row.get("reason", "").strip()), "excluded range needs reason")
    included, excluded = scopes["included"], scopes["excluded"]
    require(bool(included), "no included pages")
    require(not included & excluded, "included/excluded ranges overlap")
    unaccounted = sorted(set(range(1, pages + 1)) - included - excluded)
    require(not unaccounted, f"unaccounted pages: {unaccounted[:30]}")
    units, unit_pages, mapped = {}, {}, set()
    for u in d["units"]:
        uid = u["id"]
        require(isinstance(uid, str) and bool(uid), "unit id must be nonempty text")
        require(uid not in units, f"duplicate unit id: {uid}")
        units[uid] = u
        s = span(u, uid)
        unit_pages[uid] = s
        mapped |= s
        require(s <= included, f"{uid}: unit outside included scope")
        require(bool(u.get("title", "").strip()), f"{uid}: missing title")
        require(u.get("review_status") in STATUSES, f"{uid}: invalid review_status")
        if u.get("review_status") == "complete":
            require(bool(u.get("review_notes", "").strip()), f"{uid}: completed unit needs review_notes")
    missing_units = sorted(included - mapped)
    require(not missing_units, f"included pages without units: {missing_units[:30]}")
    item_ids, by_unit, book_by_unit, book_counts = set(), Counter(), Counter(), Counter()
    reviewed_items = True
    for item in d["items"]:
        iid, uid = item["id"], item["unit_id"]
        require(isinstance(iid, str) and bool(iid), "item id must be nonempty text")
        require(iid not in item_ids, f"duplicate item id: {iid}")
        item_ids.add(iid)
        require(uid in units, f"{iid}: unknown unit")
        by_unit[uid] += 1
        locations = item.get("source_pages", [])
        valid_locations = isinstance(locations, list) and bool(locations) and all(
            type(n) is int and n in unit_pages.get(uid, set()) for n in locations)
        require(valid_locations, f"{iid}: source_pages must belong to its unit")
        require(bool(item.get("point", "").strip()), f"{iid}: missing point")
        require(item.get("kind") in KINDS, f"{iid}: invalid kind")
        require(item.get("attribution") in {"book", "editor"}, f"{iid}: invalid attribution")
        status, disposition = item.get("review_status"), item.get("disposition")
        require(status in STATUSES, f"{iid}: invalid review_status")
        require(disposition in DISPOSITIONS, f"{iid}: invalid disposition")
        reviewed_items &= status == "complete" and disposition != "pending"
        if item.get("attribution") == "book":
            book_counts[disposition] += 1
            book_by_unit[uid] += 1
        targets = item.get("targets", [])
        require(isinstance(targets, list), f"{iid}: targets must be a list")
        if disposition in {"covered", "merged"}:
            require(bool(targets), f"{iid}: missing output targets")
        if disposition in {"merged", "excluded"}:
            require(bool(item.get("reason", "").strip()), f"{iid}: disposition needs reason")
        for target in targets if isinstance(targets, list) else []:
            if not require(isinstance(target, str) and bool(target), f"{iid}: invalid target"):
                continue
            local = (path.parent / unquote(target.split("#", 1)[0])).resolve()
            require(local.is_relative_to(path.parent), f"{iid}: target outside delivery directory")
            require(local.is_file(), f"{iid}: missing target {target}")
    exceptions = {}
    for uid, unit in units.items():
        if "no_book_candidates_reason" in unit:
            reason = unit["no_book_candidates_reason"]
            if require(isinstance(reason, str) and bool(reason.strip()),
                       f"{uid}: no_book_candidates_reason must be nonempty text"):
                require(book_by_unit[uid] == 0, f"{uid}: exception conflicts with book candidates")
                exceptions[uid] = reason.strip()
        require(by_unit[uid] > 0 or uid in exceptions, f"{uid}: no recorded candidate items")
    empty_book_units = [uid for uid in units if not book_by_unit[uid]]
    reviewed_units = sum(u.get("review_status") == "complete" for u in units.values())
    return {
        "structure_valid": not errors,
        "source_pages": pages,
        "scope_accounted_pages": len(included | excluded),
        "included_pages": len(included),
        "included_pages_with_units": len(included & mapped),
        "units_reviewed": reviewed_units, "units_total": len(units),
        "recorded_book_items": dict(book_counts),
        "recorded_book_candidates_empty": not bool(book_counts),
        "units_without_book_candidates": empty_book_units,
        "book_candidate_exceptions": exceptions,
        "recorded_review_complete": not errors and bool(units) and bool(book_counts)
            and all(uid in exceptions for uid in empty_book_units)
            and reviewed_units == len(units) and reviewed_items,
        "semantic_completeness": "not_proven_by_this_script",
        "errors": errors,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage_json")
    args = parser.parse_args()
    try:
        result = audit(args.coverage_json)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = {"structure_valid": False, "semantic_completeness": "not_proven_by_this_script",
                  "errors": [f"Cannot validate ledger: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["structure_valid"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
