"""Static safety checks for SMC Metal Hunter Pine files (no Pine compiler needed).

Catches the problems this script has actually hit in TradingView:
  * duplicate global declarations
  * local variables / function parameters that shadow a global (warning CW10013)
  * tab characters (Pine rejects them)
  * short title longer than 10 characters (SHORT_TITLE_TOO_LONG)
  * request.security calls over the 40 limit
  * drawings placed with a raw stored bar index that can be > history buffer
    (runtime error "historical offset beyond the historical buffer's limit")

Usage:  python3 pine/tests/pine_static_checks.py pine/SMC_Metal_Hunter_V14_7.pine
Exit code 1 if a hard problem is found.
"""
import collections
import re
import sys

TYPES = r"(?:var\s+)?(?:(?:float|int|bool|string|color|line|label|box|table|array<\w+>)\s+)?"


def main(path):
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    hard = []

    glob = collections.Counter()
    for l in lines:
        m = re.match(r"^" + TYPES + r"([A-Za-z_]\w*)\s*=(?!=)", l)
        if m:
            glob[m.group(1)] += 1
        m = re.match(r"^\[([^\]]+)\]\s*=", l)
        if m:
            for x in m.group(1).split(","):
                glob[x.strip()] += 1
    dups = [k for k, v in glob.items() if v > 1]
    if dups:
        hard.append(f"duplicate globals: {dups}")

    for i, l in enumerate(lines, 1):
        m = re.match(r"^\s+" + TYPES + r"([A-Za-z_]\w*)\s*=(?!=)", l)
        if m and m.group(1) in glob:
            print(f"WARN shadow line {i}: {m.group(1)}")
        m = re.match(r"^(f_\w+)\((.*)\)\s*=>", l)
        if m:
            for prm in m.group(2).split(","):
                n = prm.strip().split()[-1] if prm.strip() else ""
                if n in glob:
                    print(f"WARN parameter shadow line {i}: {m.group(1)}({n})")

    if "\t" in src:
        hard.append("tab characters found")

    m = re.search(r'shorttitle="([^"]*)"', src)
    if m and len(m.group(1)) > 10:
        hard.append(f"short title '{m.group(1)}' is {len(m.group(1))} chars (max 10)")

    n_sec = src.count("request.security(")
    print(f"request.security calls: {n_sec} / 40")
    if n_sec > 40:
        hard.append("more than 40 request.security calls")

    # stored bar indexes used as x1 of a drawing without clamp / bar_time
    risky = re.compile(r"(line|box|label)\.new\((\w+),")
    safe_x = {"bar_index", "x1", "x2", "sx1", "fx1", "tx", "t1", "t2", "wfTime", "wft1", "wft2", "gapTime", "b", "lastSHBar", "lastSLBar", "zzBar", "fx2", "gx2"}  # fx2/gx2 = bar_index + 20 (future)
    for i, l in enumerate(lines, 1):
        for m in risky.finditer(l):
            x = m.group(2)
            if x not in safe_x and "xloc=xloc.bar_time" not in l:
                print(f"CHECK drawing x from stored bar index, line {i}: {x}")

    print(f"lines: {len(lines)}")
    for h in hard:
        print("FAIL", h)
    print("RESULT:", "FAIL" if hard else "OK")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
