#!/usr/bin/env python3
"""Convert legacy parsed Markdown labels into graph-ready JSON.

The script performs a best-effort extraction of key herbicide metadata and
Directions for Use table rows. Outputs one JSON per Markdown input plus a
summary of files that lacked usable data.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, List, Optional


STATE_CODES = {
    "all states": ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"],
    "nsw": ["NSW"],
    "vic": ["VIC"],
    "qld": ["QLD"],
    "sa": ["SA"],
    "wa": ["WA"],
    "tas": ["TAS"],
    "nt": ["NT"],
    "act": ["ACT"],
    "western australia": ["WA"],
    "south australia": ["SA"],
    "queensland": ["QLD"],
    "victoria": ["VIC"],
    "new south wales": ["NSW"],
}


def normalise_states(raw: str) -> List[str]:
    tokens: List[str] = []
    for piece in re.split(r"[,/]|\band\b", raw.lower()):
        piece = piece.strip()
        if not piece:
            continue
        if piece in STATE_CODES:
            tokens.extend(STATE_CODES[piece])
        elif piece.endswith(" only") and piece[:-5] in STATE_CODES:
            tokens.extend(STATE_CODES[piece[:-5]])
    unique = []
    for state in tokens:
        if state not in unique:
            unique.append(state)
    return unique


def extract_numbers(text: str) -> List[float]:
    numbers = []
    for match in re.findall(r"\d+(?:\.\d+)?", text):
        try:
            numbers.append(float(match))
        except ValueError:
            continue
    return numbers


def extract_rate(rate_text: str) -> tuple[Optional[float], str]:
    numbers = extract_numbers(rate_text)
    value = max(numbers) if numbers else None
    unit_match = re.search(r"(m?L|g|kg)\s*/\s*ha", rate_text, re.IGNORECASE)
    unit = unit_match.group(0).replace(" ", "") if unit_match else rate_text.strip()
    return value, unit


def parse_table(lines: Iterable[str]) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in lines:
        if not line.strip().startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def process_markdown(md_path: Path) -> tuple[Optional[dict], Optional[str]]:
    text = md_path.read_text(encoding="utf-8")

    product_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    product_name = product_match.group(1).strip() if product_match else None

    apvma_match = re.search(r"APVMA Approval No:\s*([^\n]+)", text)
    apvma_number = apvma_match.group(1).replace(" ", "").strip() if apvma_match else None

    active_match = re.findall(r"Active Constituent:\s*([^\n]+)", text)
    active_constituents = [a.strip() for a in active_match]

    moa_match = re.search(r"GROUP\s+([A-Z0-9]+)\s+HERBICIDE", text)
    moa_legacy = moa_match.group(1) if moa_match else None

    directions_idx = text.lower().find("# directions for use")
    if directions_idx == -1:
        return None, "missing-directions"

    directions_block = text[directions_idx:].split("\n\n", 1)[-1]
    table_lines = []
    for line in directions_block.splitlines():
        if line.strip().startswith("|"):
            table_lines.append(line)
        elif table_lines:
            break
    table = parse_table(table_lines)

    if len(table) < 3:
        return None, "missing-table"

    # Remove header and divider rows
    header = table[0]
    body = [row for row in table[2:] if len(row) >= len(header)]
    usage = []
    crops = set()
    weeds = set()
    for row in body:
        if len(row) < 5:
            continue
        crop = row[0]
        weed_text = row[1]
        state_text = row[2]
        rate_text = row[3]
        comments = row[4] if len(row) > 4 else ""

        states = normalise_states(state_text)
        rate_value, rate_unit = extract_rate(rate_text)
        weed_names = [w.strip() for w in re.split(r",|/", weed_text) if w.strip()]

        crops.add(crop)
        weeds.update(weed_names)

        usage.append({
            "crop": crop,
            "weed_common_name": weed_names[0] if weed_names else weed_text.strip(),
            "weed_scientific_name": None,
            "states": states or ["All States"],
            "rate_value": rate_value or 0.0,
            "rate_unit": rate_unit,
            "rate_full_text": rate_text.strip(),
            "growth_stage_weed": None,
            "growth_stage_crop": None,
            "constraints": [{
                "type": "Timing",
                "description": comments.strip(),
            }] if comments.strip() else [],
        })

    if not usage:
        return None, "empty-usage"

    record = {
        "product_name": product_name,
        "apvma_number": apvma_number,
        "active_constituents": active_constituents,
        "moa_number": None,
        "moa_legacy_letter": moa_legacy,
        "identified_crops": sorted(crops),
        "identified_weeds": sorted(weeds),
        "usage_scenarios": usage,
    }

    if not all([product_name, apvma_number, active_constituents]):
        return record, "incomplete-metadata"

    return record, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed-dir", type=Path, default=Path("data/parsed"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/extracted-from-md"))
    parser.add_argument("--summary", type=Path, default=Path("data/extracted-from-md/summary.json"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "processed": [],
        "unsatisfactory": [],
    }

    for md_path in sorted(args.parsed_dir.glob("*.md")):
        record, status = process_markdown(md_path)
        if record is None:
            summary["unsatisfactory"].append({"file": md_path.name, "reason": status})
            continue

        output_path = args.output_dir / (md_path.stem + ".json")
        output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        entry = {"file": md_path.name}
        if status:
            entry["warning"] = status
        summary["processed"].append(entry)

    args.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
