"""Create, list and delete the fleet's RunPod pods through the REST API (v2).

Pods bill by the hour from creation, so `create` prints the plan and the hourly
price and does nothing without `--yes`. The API key comes from RUNPOD_API_KEY and
is never written anywhere; resolve it at launch, e.g.

    asm-exec -- env RUNPOD_API_KEY='{{resolve:secretsmanager:<secret-id>:SecretString:<key>}}' \\
      python src/prices/enrich/gpu/fleet/pods.py --work <dir> create --plan <dir>/pods.plan --gpu "NVIDIA A40" --yes

`create` writes into --work (the week's embed dir, never the repo) pods.txt
(id host port lo hi, what lib.sh reads as PODS_FILE) and pod_ids.tsv (fleet id,
RunPod id, GPU, $/h). `delete` only takes ids listed in pod_ids.tsv, i.e. pods
this driver created.

The public keys go in at create time (PUBLIC_KEY): added later they never reach
sshd, and without one port 22 never opens at all.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

API = "https://api.runpod.io/v2"
IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
READY_TIMEOUT_S = 600


def _call(method: str, path: str, body: dict | None = None) -> dict | list | None:
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        sys.exit(
            "RUNPOD_API_KEY is not set (resolve it with asm-exec, see the module docstring)"
        )
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def _plan(path: Path) -> list[list[str]]:
    rows = []
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            rows.append(line.split("\t"))
    return rows


def _keys(paths: list[str]) -> str:
    return "\n".join(Path(os.path.expanduser(p)).read_text().strip() for p in paths)


def create(a) -> None:
    plan = _plan(a.plan)
    body = {
        "image": IMAGE,
        "cloud": "SECURE",
        "gpu": {"id": a.gpu, "count": 1, "minCudaVersion": "12.8"},
        "disk": a.disk,
        "mounts": {"persistent": {"size": a.volume, "path": "/workspace"}},
        "ports": ["22/tcp"],
        "env": {"PUBLIC_KEY": _keys(a.pubkey)},
    }
    if a.datacenter:
        body["dataCenterIds"] = [a.datacenter]
    print(
        f"{len(plan)} pod(s) x {a.gpu} ({a.datacenter or 'any data center'}), {a.disk}G disk, {a.volume}G /workspace"
    )
    if not a.yes:
        print(
            "dry run: nothing created. Check the GPU's price and stock, then add --yes."
        )
        return
    ids, pods = [], []
    for pid, *_rest, lo, hi in plan:
        pod = _call("POST", "/pods", {**body, "name": f"po-embed-{pid}"})
        ids.append([pid, pod["id"], a.gpu, str(pod.get("cost", "?"))])
        print(f"{pid} created {pod['id']} ${pod.get('cost', '?')}/h", flush=True)
        if not pod.get("env", {}).get("PUBLIC_KEY"):
            print(
                f"{pid}: PUBLIC_KEY did not stick; this pod will never open ssh",
                flush=True,
            )
        pods.append((pid, pod["id"], lo, hi))
    (a.work / "pod_ids.tsv").write_text("".join("\t".join(r) + "\n" for r in ids))
    lines, t0 = {}, time.time()
    while len(lines) < len(pods) and time.time() - t0 < READY_TIMEOUT_S:
        for pid, rid, lo, hi in pods:
            if pid in lines:
                continue
            direct = ((_call("GET", f"/pods/{rid}") or {}).get("ssh") or {}).get(
                "direct"
            )
            if direct:
                lines[pid] = f"{pid}\t{direct['host']}\t{direct['port']}\t{lo}\t{hi}\n"
                print(f"{pid} ssh {direct['host']}:{direct['port']}", flush=True)
        if len(lines) < len(pods):
            time.sleep(15)
    (a.work / "pods.txt").write_text("".join(lines[p] for p, *_ in pods if p in lines))
    if len(lines) < len(pods):
        sys.exit(
            f"{len(pods) - len(lines)} pod(s) without ssh after {READY_TIMEOUT_S}s; see pod_ids.tsv"
        )


def _ours(work: Path) -> dict[str, str]:
    f = work / "pod_ids.tsv"
    return {r[0]: r[1] for r in _plan(f)} if f.exists() else {}


def show(a) -> None:
    for pid, rid in _ours(a.work).items():
        p = _call("GET", f"/pods/{rid}") or {}
        print(pid, rid, p.get("status"), p.get("cost"), p.get("dataCenterId"))


def delete(a) -> None:
    ours = _ours(a.work)
    for pid in a.pods:
        if pid not in ours:
            sys.exit(
                f"{pid} is not in pod_ids.tsv; this driver only deletes pods it created"
            )
    for pid in a.pods:
        _call("DELETE", f"/pods/{ours[pid]}")
        print(f"{pid} delete sent for {ours[pid]}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--work", type=Path, required=True, help="dir for pods.txt and pod_ids.tsv"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--plan", type=Path, required=True, help="pods.plan from plan.py")
    c.add_argument("--gpu", required=True, help='catalog GPU id, e.g. "NVIDIA A40"')
    c.add_argument("--datacenter", default=None)
    c.add_argument("--disk", type=int, default=60)
    c.add_argument("--volume", type=int, default=80)
    c.add_argument("--pubkey", nargs="+", default=["~/.ssh/id_ed25519.pub"])
    c.add_argument("--yes", action="store_true")
    c.set_defaults(fn=create)
    sub.add_parser("show").set_defaults(fn=show)
    d = sub.add_parser("delete")
    d.add_argument("pods", nargs="+", help="fleet ids (pod1 ...) from pod_ids.tsv")
    d.set_defaults(fn=delete)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
