"""Step `build` (PX-25, was ~/scratch/w42_build/chain_b.sh + resume_b.sh, tm.py, page.py, merge_nf.py).

Stage B's per-country outputs -> the global build, in this order, each sub-step in its
own `systemd-run --user --scope` unit with its own MemoryMax:

  assemble       prices.global_build assemble (rows dated after --as-of are dropped)
  rtcal          prices.global_build rtcal
  merge          prices.global_build merge
  typical_mass   leaf_typical_mass.csv from the measured donors and the piece rows
  nonfood        every country's nonfood/ files -> two global parquets
  8 pages        {rtcal,trusted} x {world,eap} x {explorer,dashboard}, one process each
                 (W42: rendered together the pages OOM'd at 23G + 7.7G swap)

Refuses when the build dir exists, unless --resume: then the sub-steps this build dir
already finished (week_dir/build/<build>.done) are skipped and the rest run, which is
what resume.sh and resume_b.sh did by hand after the W42 OOMs.

`--countries` builds from week_dir/build/<build>_stage_b/, one link per country to its
Stage B dir, so every sub-step sees only those countries. Every country in scope needs
a Stage B report.txt. TMPDIR is a folder next to the build dir, not /tmp.

`--train-stage-b` (with --countries) trains the global parts on a wider Stage B, e.g.
the 215 countries, and publishes only --countries. RT-CAL's gates, thresholds, global
and regional pruning and fills, and the pooled typical mass, all depend on every
country in the build, so a panel built alone gets different numbers. Three sub-steps
run first into --train-out (default <build dir's parent>/_train_<build>, kept):

  train_assemble      assemble over the training Stage B, with --train-decisions as
                      the classifier store when given (the panel tree holds only the
                      panel's decisions)
  train_rtcal         rtcal over that
  train_typical_mass  typical mass over that

and then `rtcal` copies the training rtcal/ into the build, every parquet with a
`country` column cut to --countries, and `typical_mass` copies the training csv.
The pages then show only --countries, world pages included.
"""

from __future__ import annotations

import glob
import os
import shutil
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from prices.weekly.status import Status
from prices.weekly.step import REPO_ROOT, _sha, _unit_active
from prices.weekly.steps import _common

MODULE = "prices.weekly.steps.build"
OBS = "global_prices_observations.parquet"
TYPICAL_MASS = "leaf_typical_mass.csv"
PAGES = [
    (v, r, p)
    for v in ("rtcal", "trusted")
    for r in ("world", "eap")
    for p in ("explorer", "dashboard")
]
# W42 peaks over 215 countries: assemble 3.3G, rtcal 13.6G, merge 2.4G, typical mass
# 21.1G, explorer 6.9G, world dashboard 22.9G (eap 16.9G).
MEMORY_GB = {
    "assemble": 6,
    "rtcal": 18,
    "merge": 6,
    "typical_mass": 24,
    "nonfood": 4,
    "explorer": 10,
    "dashboard": 24,
}
TM_COLS = [
    "coicop_code", "pricing_basis", "amount_value", "standard_unit", "country",
    "price_local", "currency", "count", "multiplier", "mass_source",
]
NONFOOD = [
    ("observations.parquet", "global_prices_nonfood_observations.parquet"),
    ("trusted_observations.parquet", "global_prices_nonfood_trusted_observations.parquet"),
]

_current_unit: str | None = None


def _wk(week: str) -> str:
    return "w" + week.split("-W")[1]


def typical_mass(out: Path) -> int:
    import pyarrow.dataset as ds

    from prices.build import leaf_typical_mass as ltm

    _common.setup_logging()
    target = out / TYPICAL_MASS
    if target.exists():
        print(f"{target} exists, not overwriting", flush=True)
        return 1
    # tm.py's row filter, pushed into the read: the 215-country frame peaked at 21.1G.
    f = ds.field
    keep = (
        f("coicop_code").is_valid()
        & f("standard_unit").is_valid()
        & (
            (f("pricing_basis").isin(sorted(ltm.MEASURED_BASES)) & (f("mass_source") == "measured"))
            | f("pricing_basis").isin(sorted(ltm.PIECE_BASES))
        )
    )
    data = ds.dataset(out / OBS)
    df = data.to_table(columns=TM_COLS, filter=keep).to_pandas(strings_to_categorical=True)
    print(f"rows {data.count_rows():,} -> {len(df):,} (measured donors + piece rows)", flush=True)
    df = df.drop(columns=["mass_source"])
    for c in ("pricing_basis", "standard_unit", "country", "coicop_code"):
        df[c] = df[c].astype(object)
    table = ltm.derive_typical_mass(df)
    table.to_csv(target, index=False)
    print(f"wrote {target}: {len(table)} leaves, {int(table['accepted'].sum())} accepted", flush=True)
    return 0


def nonfood(stage_b: Path, out: Path) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq

    for src, dest in NONFOOD:
        files = sorted(glob.glob(str(stage_b / "*" / "nonfood" / src)))
        if not files:
            print(f"no */nonfood/{src} under {stage_b}", flush=True)
            return 1
        schema = pa.unify_schemas([pq.read_schema(f) for f in files], promote_options="permissive")
        schema = schema.append(pa.field("country", pa.string()))
        target = out / dest
        if target.exists():
            print(f"{target} exists, not overwriting", flush=True)
            return 1
        tmp = target.with_suffix(".parquet.part")
        n = 0
        with pq.ParquetWriter(tmp, schema, compression="zstd") as w:
            for f in files:
                country = Path(f).parent.parent.name
                pf = pq.ParquetFile(f)
                for i in range(pf.num_row_groups):
                    t = pf.read_row_group(i)
                    t = t.append_column("country", pa.array([country] * len(t), pa.string()))
                    for name in schema.names:
                        if name not in t.column_names:
                            t = t.append_column(name, pa.nulls(len(t), schema.field(name).type))
                    w.write_table(t.select(schema.names).cast(schema))
                    n += len(t)
        tmp.rename(target)
        print(f"{dest}: {len(files)} countries, {n:,} rows, {target.stat().st_size / 1e9:.2f} GB", flush=True)
    return 0


def train_assemble(args) -> int:
    from prices import global_build
    from prices.enrich import config

    if args.train_decisions:
        config.CLASSIFIED_HIERLEX_PARQUET = args.train_decisions
    argv = ["assemble", "--stage-b", str(args.train_stage_b), "--out", str(args.train_out)]
    global_build.cli.main(argv + (["--as-of", args.as_of] if args.as_of else []), standalone_mode=False)
    return 0


def rtcal_subset(train: Path, out: Path, countries: list[str]) -> int:
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    src, dst = train / "rtcal", out / "rtcal"
    if dst.exists():
        print(f"{dst} exists, not overwriting", flush=True)
        return 1
    for p in sorted(src.rglob("*")):
        t = dst / p.relative_to(src)
        if p.is_dir():
            t.mkdir(parents=True, exist_ok=True)
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".parquet" and "country" in pq.read_schema(p).names:
            tab = ds.dataset(p).to_table(filter=ds.field("country").isin(countries))
            pq.write_table(tab, t)
            print(f"{t.relative_to(dst)}: {tab.num_rows:,} of {pq.ParquetFile(p).metadata.num_rows:,} rows", flush=True)
        else:
            shutil.copyfile(p, t)
            print(f"{t.relative_to(dst)}: copied", flush=True)
    return 0


def copy_typical_mass(train: Path, out: Path) -> int:
    target = out / TYPICAL_MASS
    if target.exists():
        print(f"{target} exists, not overwriting", flush=True)
        return 1
    shutil.copyfile(train / TYPICAL_MASS, target)
    print(f"copied {train / TYPICAL_MASS}", flush=True)
    return 0


def page(out: Path, spec: str) -> int:
    from prices import dashboards as d
    from prices import explorer, publish

    _common.setup_logging()
    variant, region, kind = spec.split(":")
    region = None if region == "world" else region
    d._rebase(publish.BUILD_DIR, out)
    vdir = out / "dashboards" / variant
    vdir.mkdir(parents=True, exist_ok=True)
    d._point_at(out, vdir, variant, region)
    tag = f"_{region}" if region else ""
    if kind == "explorer":
        explorer.run(vdir / f"global_prices_explorer{tag}.html", region)
    else:
        publish.publish(region=region, out_path=vdir / f"global_prices_dashboard{tag}.html")
    print(f"PAGE_OK {variant} {region or 'world'} {kind}", flush=True)
    return 0


def _substeps(args, stage_b: Path, out: Path) -> list[tuple[str, int, list[str]]]:
    """(name, MemoryMax in G, argv after `python -u`)."""
    gb = ["-m", "prices.global_build"]
    own = ["-m", MODULE, "--week", args.week, "--week-dir", str(args.week_dir), "--out", str(out)]
    as_of = ["--as-of", args.as_of] if args.as_of else []
    assemble = ("assemble", MEMORY_GB["assemble"], [*gb, "assemble", "--stage-b", str(stage_b), "--out", str(out), *as_of])
    if args.train_stage_b:
        train = ["-m", MODULE, "--week", args.week, "--week-dir", str(args.week_dir), "--out", str(args.train_out)]
        dec = ["--train-decisions", str(args.train_decisions)] if args.train_decisions else []
        sub = [*own, "--train-out", str(args.train_out), "--countries", args.countries]
        steps = [
            ("train_assemble", MEMORY_GB["assemble"],
             [*train, "--phase", "train_assemble", "--train-stage-b", str(args.train_stage_b),
              "--train-out", str(args.train_out), *dec, *as_of]),
            ("train_rtcal", MEMORY_GB["rtcal"], [*gb, "rtcal", "--out", str(args.train_out)]),
            ("train_typical_mass", MEMORY_GB["typical_mass"], [*train, "--phase", "typical_mass"]),
            assemble,
            ("rtcal", MEMORY_GB["nonfood"], [*sub, "--phase", "rtcal_subset"]),
            ("merge", MEMORY_GB["merge"], [*gb, "merge", "--out", str(out)]),
            ("typical_mass", 1, [*sub, "--phase", "copy_typical_mass"]),
        ]
    else:
        steps = [
            assemble,
            ("rtcal", MEMORY_GB["rtcal"], [*gb, "rtcal", "--out", str(out)]),
            ("merge", MEMORY_GB["merge"], [*gb, "merge", "--out", str(out)]),
            ("typical_mass", MEMORY_GB["typical_mass"], [*own, "--phase", "typical_mass"]),
        ]
    steps += [
        ("nonfood", MEMORY_GB["nonfood"], [*own, "--stage-b", str(stage_b), "--phase", "nonfood"]),
    ]
    for v, r, p in PAGES:
        steps.append((f"{v}_{r}_{p}", MEMORY_GB[p], [*own, "--phase", "page", "--page", f"{v}:{r}:{p}"]))
    return [(n, min(m, args.memory_cap or m), a) for n, m, a in steps]


def _stop_current(signum, frame):
    # Stopping the step's scope kills this runner only: each sub-step is a sibling
    # scope under the user manager, so it is stopped here by name.
    if _current_unit:
        subprocess.run(["systemctl", "--user", "stop", f"{_current_unit}.scope"])
    sys.exit(128 + signum)


def _unit(args, status: Status, name: str, mem: int, argv: list[str], tmp: Path) -> int:
    global _current_unit
    unit = re.sub(r"[^A-Za-z0-9_.-]", "-", f"po-weekly-{args.week}-build-{name}")
    if _unit_active(unit):
        _common.say(status, f"FAILED {name}: unit {unit}.scope is already active")
        return 1
    cmd = [
        "systemd-run", "--user", "--scope", "-q", f"--unit={unit}",
        "-p", f"MemoryMax={mem}G", "-p", f"MemorySwapMax={args.swap_max}G",
        "env", f"PYTHONPATH={REPO_ROOT / 'src'}", f"TMPDIR={tmp}",
        "/usr/bin/time", "-f", "   STEP_TIME %e s, peak %M KB",
        sys.executable, "-u", *argv,
    ]
    _common.say(status, f"{name} start, MemoryMax={mem}G")
    _current_unit = unit
    s = time.time()
    sys.stdout.flush()
    rc = subprocess.run(cmd, cwd=REPO_ROOT).returncode
    _current_unit = None
    _common.say(status, f"{name} rc={rc} {time.time() - s:.0f}s")
    return rc


def _scope(args, sb: Path, out: Path, countries: list[str] | None) -> Path | str:
    """The Stage B dir the sub-steps read, or why the build cannot start."""
    have = {p.parent.name for p in sb.glob("*/report.txt")}
    if not countries:
        return sb if have else f"no */report.txt under {sb}"
    missing = [c for c in countries if c not in have]
    if missing:
        return f"no Stage B report.txt under {sb} for {', '.join(missing)}"
    links = args.week_dir / "build" / f"{out.name}_stage_b"
    links.mkdir(parents=True, exist_ok=True)
    extra = sorted(p.name for p in links.iterdir() if p.name not in countries)
    if extra:
        return f"{links} holds links outside --countries: {', '.join(extra)}"
    for c in countries:
        if not (links / c).is_symlink():
            (links / c).symlink_to(sb / c)
    return links


def run(args, countries: list[str] | None) -> int:
    signal.signal(signal.SIGTERM, _stop_current)
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    status = Status(args.week_dir, "build")
    wk = _wk(args.week)
    sb = (args.stage_b or REPO_ROOT / "outputs" / "prices" / f"stage_b_{wk}").absolute()
    out = (args.out or REPO_ROOT / "outputs" / "prices" / f"build_{wk}").absolute()
    done_file = args.week_dir / "build" / f"{out.name}.done"
    if out.exists() and not args.resume:
        _common.say(status, f"FAILED {out} exists; refusing to overwrite (--resume continues it)")
        return 1
    if args.resume and not out.exists():
        _common.say(status, f"FAILED --resume but {out} does not exist")
        return 1
    if args.train_stage_b:
        if not countries:
            _common.say(status, "FAILED --train-stage-b needs --countries: the rows to publish")
            return 1
        args.train_out = (args.train_out or out.parent / f"_train_{out.name}").absolute()
        if args.train_out.exists() and not args.resume:
            _common.say(status, f"FAILED {args.train_out} exists; refusing to overwrite (--resume continues it)")
            return 1
    src = _scope(args, sb, out, countries)
    if isinstance(src, str):
        _common.say(status, f"FAILED {src}")
        return 1
    n = len(list(src.glob("*/report.txt")))
    n_nf = len(list(src.glob("*/nonfood/report.txt")))
    done = set(done_file.read_text().split()) if args.resume and done_file.exists() else set()
    if not args.resume:
        done_file.parent.mkdir(parents=True, exist_ok=True)
        done_file.write_text("")
    train = f"; trained on {args.train_stage_b} into {args.train_out}" if args.train_stage_b else ""
    _common.say(status, f"build {out} from {src} ({n} countries, {n_nf} with nonfood){train} @{_sha()}")
    tmp = out.parent / f"_tmp_{out.name}"
    out.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(exist_ok=True)
    for name, mem, argv in _substeps(args, src, out):
        if name in done:
            _common.say(status, f"{name} skipped: done in an earlier run")
            continue
        rc = _unit(args, status, name, mem, argv, tmp)
        if rc != 0:
            _common.say(status, f"FAILED {name} rc={rc}; --resume continues from it")
            return rc
        with open(done_file, "a") as f:
            f.write(name + "\n")
    if not any(tmp.iterdir()):
        tmp.rmdir()
    return 0


def main() -> int:
    ap = _common.parser("build")
    ap.add_argument("--stage-b", type=Path, default=None, help="default: <repo>/outputs/prices/stage_b_wNN")
    ap.add_argument("--out", type=Path, default=None, help="default: <repo>/outputs/prices/build_wNN")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD; assemble drops later rows (default today, UTC)")
    ap.add_argument("--memory-cap", type=int, default=None, help="GiB; caps every sub-step's MemoryMax")
    # The 215-country typical mass needs ~21G: under a 20G cap it fits only with swap.
    ap.add_argument("--swap-max", type=int, default=1, help="GiB of swap per sub-step")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--train-stage-b", type=Path, default=None, help="Stage B the global parts train on")
    ap.add_argument("--train-decisions", type=Path, default=None,
                    help="classified_hierlex.parquet whose parts cover --train-stage-b")
    ap.add_argument("--train-out", type=Path, default=None, help="default: <out parent>/_train_<out name>")
    ap.add_argument("--page", default=None)
    args = ap.parse_args()
    if args.phase == "train_assemble":
        return train_assemble(args)
    if args.phase == "rtcal_subset":
        return rtcal_subset(args.train_out, args.out, _common.countries(args.countries))
    if args.phase == "copy_typical_mass":
        return copy_typical_mass(args.train_out, args.out)
    if args.phase == "typical_mass":
        return typical_mass(args.out)
    if args.phase == "nonfood":
        return nonfood(args.stage_b, args.out)
    if args.phase == "page":
        return page(args.out, args.page)
    return run(args, _common.countries(args.countries))


if __name__ == "__main__":
    sys.exit(main())
