#!/usr/bin/env python3
"""Inspect Git object provenance without rewriting sealed historical files.

Run in a full checkout (fetch-depth: 0). A missing blob is UNKNOWN, not empty.
"""
import argparse
import json
import subprocess


def git(*args):
    return subprocess.run(["git", *args], text=True, capture_output=True)


def inspect(commit, path):
    obj = f"{commit}:{path}"
    size = git("cat-file", "-s", obj)
    if size.returncode:
        return {"commit": commit, "path": path, "status": "NOT_RETRIEVABLE",
                "detail": size.stderr.strip()}
    blob = git("rev-parse", obj)
    return {"commit": commit, "path": path, "status": "RETRIEVABLE",
            "size_bytes": int(size.stdout.strip()), "blob_sha": blob.stdout.strip()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--commit", required=True)
    p.add_argument("--path", required=True)
    args = p.parse_args()
    print(json.dumps(inspect(args.commit, args.path), ensure_ascii=False))


if __name__ == "__main__":
    main()
