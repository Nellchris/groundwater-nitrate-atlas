"""Print the gate check for the Groundwater Nitrate Atlas."""
import argparse
import json
import pathlib

import pandas as pd

TOTAL_MIN = 150
PER_CAT_MIN = 30
# Categories the atlas intends to compare.
COMPARE = ["Chalk", "Greensand", "Clay / low-permeability"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="gate_check_results.csv")
    ap.add_argument("--data", default="data")
    a = ap.parse_args()

    d = pd.read_csv(a.csv)
    meta = json.loads((pathlib.Path(a.data) / "ea_fetch_metadata.json").read_text())
    bb = meta["bbox_wgs84"]

    line = "=" * 72
    print(line)
    print("GATE CHECK - GROUNDWATER NITRATE ATLAS")
    print(line)
    print(f"Study bbox (WGS84)   : {bb['west']}W .. {bb['east']}W, "
          f"{bb['south']}N .. {bb['north']}N")
    print(f"Window               : {meta['window']['years']} years ending "
          f"{meta['window']['end']}")
    print(f"Determinand          : 0117 Nitrate as N "
          f"(converted to mg/l as NO3, x4.427)")
    print(f"Sampling point types : {meta['sampling_point_types']} "
          "(ambient groundwater; landfill/waste boreholes excluded)")
    print(f"Observations          : {len(d['n_samples']) and int(d['n_samples'].sum())} "
          f"samples over {len(d)} wells")
    print(f"Sample dates         : {d['first_sample'].min()[:10]} .. "
          f"{d['last_sample'].max()[:10]}")
    print()

    total = len(d)
    print("-- TOTAL WELLS WITH NITRATE DATA " + "-" * 39)
    ok_total = total >= TOTAL_MIN
    print(f"  {total} wells   (criterion: >= ~{TOTAL_MIN})   "
          f"{'PASS' if ok_total else 'FAIL'}")
    print()

    print("-- WELLS PER AQUIFER CATEGORY " + "-" * 42)
    vc = d["aquifer_category"].value_counts()
    med = d.groupby("aquifer_category")["nitrate_median_mg_L_as_NO3"].median()
    print(f"  {'category':<30}{'wells':>7}{'median NO3':>14}   gate")
    for cat, n in vc.items():
        gate = ""
        if cat in COMPARE:
            gate = "PASS" if n >= PER_CAT_MIN else f"FAIL (<{PER_CAT_MIN})"
        print(f"  {cat:<30}{n:>7}{med[cat]:>14.2f}   {gate}")
    print()

    print("-- PASS CRITERIA " + "-" * 55)
    print(f"  total >= ~{TOTAL_MIN} wells            : "
          f"{'PASS' if ok_total else 'FAIL'} ({total})")
    compared = {c: int(vc.get(c, 0)) for c in COMPARE}
    for c, n in compared.items():
        print(f"  >= ~{PER_CAT_MIN} wells in {c:<22}: "
              f"{'PASS' if n >= PER_CAT_MIN else 'FAIL'} ({n})")
    print()
    viable = [c for c, n in compared.items() if n >= PER_CAT_MIN]
    blocked = [c for c, n in compared.items() if n < PER_CAT_MIN]
    print(f"  Categories viable for comparison : {', '.join(viable) or 'none'}")
    if blocked:
        print(f"  Categories below threshold       : "
              f"{', '.join(f'{c} ({compared[c]})' for c in blocked)}")
    overall = "PASS" if ok_total and not blocked else "PARTIAL PASS" \
        if ok_total and len(viable) >= 2 else "FAIL"
    print()
    print(f"  OVERALL: {overall}")
    print(line)


if __name__ == "__main__":
    main()
