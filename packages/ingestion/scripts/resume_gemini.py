#!/usr/bin/env python3
"""Resume Gemini parsing for PDFs with configurable concurrency, delay, and retries.

Usage examples:
  python packages/ingestion/scripts/resume_gemini.py --labels-dir data/labels --output-dir data/extracted-pdf --model gemini-2.5-flash --max-concurrent 2 --delay 2.5

The script skips outputs that already exist (basename.json or basename.json.gz) and retries on rate-limit/quota errors.
"""
import argparse
import concurrent.futures
import logging
import os
import subprocess
import sys
import time
from pathlib import Path


def run_single(pdf_path, output_dir, model, max_retries, base_delay):
    base = Path(pdf_path).stem
    out_json = Path(output_dir) / (base + ".json")
    if out_json.exists() or (out_json.with_suffix(out_json.suffix + ".gz")).exists():
        logging.info("Skipping %s (output exists)", pdf_path)
        return True

    cmd = [sys.executable, "-m", "ingestion.gemini_parser", str(pdf_path), "--output", str(output_dir), "--model", model]
    for attempt in range(1, max_retries + 1):
        logging.info("Running: %s (attempt %d)", " ".join(cmd), attempt)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            logging.info("Success: %s", pdf_path)
            return True

        stderr = (proc.stderr or "").lower()
        # Detect common quota/rate-limit signals
        if any(x in stderr for x in ("quota", "rate limit", "rate-limit", "429", "too many requests")):
            backoff = min(300, base_delay * (2 ** (attempt - 1)))
            logging.warning("Rate/quota detected for %s; sleeping %ds (attempt %d)", pdf_path, backoff, attempt)
            time.sleep(backoff)
            continue

        logging.error("Parsing failed for %s: %s", pdf_path, proc.stderr)
        return False

    logging.error("Exceeded retries for %s", pdf_path)
    return False


def gather_pdfs(labels_dir):
    p = Path(labels_dir)
    if p.is_file() and p.suffix.lower() in (".pdf",):
        return [p]
    files = sorted([f for f in p.rglob("*.pdf")])
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--max-concurrent", type=int, default=1)
    parser.add_argument("--delay", type=float, default=2.5, help="seconds between starting each job")
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="process at most N files (0 = all)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")

    labels_dir = Path(args.labels_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = gather_pdfs(labels_dir)
    if args.limit and args.limit > 0:
        pdfs = pdfs[: args.limit]

    total = len(pdfs)
    logging.info("Found %d PDFs to consider in %s", total, labels_dir)
    if total == 0:
        return

    # Use a ThreadPoolExecutor to allow limited concurrency.
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent) as exe:
        futures = []
        for i, pdf in enumerate(pdfs, start=1):
            # stagger starts to respect delay
            time.sleep(args.delay)
            futures.append(exe.submit(run_single, str(pdf), str(output_dir), args.model, args.max_retries, args.delay))

        # collect results
        success = 0
        for fut in concurrent.futures.as_completed(futures):
            try:
                ok = fut.result()
                if ok:
                    success += 1
            except Exception:
                logging.exception("Task exception")

    logging.info("Completed: %d/%d succeeded", success, total)


if __name__ == "__main__":
    main()
