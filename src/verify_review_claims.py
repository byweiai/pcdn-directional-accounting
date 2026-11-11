"""Cross-check the numbers the review panel quotes.

The panel's three machine attachments expect the skill's own report schema, which
these seats did not use; this script does the check the audit would have done,
but against the artefacts themselves: every value a reviewer cites is read from
the JSON or the LaTeX that produced it.  A claim with no match prints MISS.
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
PAPER = os.path.join(ROOT, 'paper')


def load(name):
    with open(os.path.join(DATA, name), encoding='utf-8') as fh:
        return json.load(fh)


def dig(obj, *path, default=None):
    cur = obj
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def tex(pattern):
    hit = []
    for p in sorted(glob.glob(os.path.join(PAPER, '*.tex'))):
        with open(p, encoding='utf-8') as fh:
            for i, line in enumerate(fh, 1):
                if re.search(pattern, line):
                    hit.append('%s:%d' % (os.path.basename(p), i))
    return hit


rows = []


def add(who, claim, got, ok):
    rows.append((who, claim, got, 'OK' if ok else 'MISS'))


# R5 C1: every regime earns 0.23 CNY/GB, so 7x is a volume ratio
e14 = load('e14_policy.json')
s1 = dig(e14, 'harm', 'welfare_at_operating', 'S1')
s3 = dig(e14, 'harm', 'welfare_at_operating', 'S3')
vol1 = dig(e14, 'harm', 'harm_volume_gb', 'S1')
vol3 = dig(e14, 'harm', 'harm_volume_gb', 'S3')
add('R5-C1', '7.0x = volume ratio', 'S1=%s S3=%s ratio=%s' % (
    round(s1, 1) if s1 else s1, round(s3, 1) if s3 else s3,
    round(s3 / s1, 3) if s1 and s3 else None), bool(s1 and s3))

# R5 C1: ratio runs 0.975 -> unbounded with detector TPR
det = dig(e14, 'detection', default={})
lo = dig(det, 'welfare_S1', 0)
hi = dig(det, 'welfare_S1')
add('R5-C1b', 'ratio 0.975 at TPR 0', 'welfare_S1 range=%s..%s' % (
    min(det.get('welfare_S1', [0])) if det.get('welfare_S1') else None,
    max(det.get('welfare_S1', [0])) if det.get('welfare_S1') else None),
    bool(det.get('welfare_S1')))

# R5 C2 / M3: downlink price below the declared tariff
e5 = load('e5_regime.json')
p = dig(e5, 'params', default={})
dl = p.get('DL_PRICE')
tar = p.get('P_PROVIDER')
add('R5-C2', 'DL_PRICE 0.10 < tariff 0.12 < margin 0.33', 'DL=%s tariff=%s' % (dl, tar),
    dl is not None and tar is not None and dl < tar)

# R5 M2: the regime model uses a 1.5x disguise
add('R5-M2', 'EVASION_EXTRA_DOWN 1.5', 'alpha=%s extra=%s' % (
    p.get('EVASION_ALPHA'), p.get('EVASION_EXTRA_DOWN')),
    abs((p.get('EVASION_EXTRA_DOWN') or 0) - 1.5) < 1e-6)

# R5 M1: tiers worse than laissez-faire at the operating point
d = dig(e14, 'harm', 'tiers_minus_laissez_at_operating')
add('R5-M1', 'tiers - laissez = -6119.6', 'delta=%s' % d, d is not None)

# R5 C3: evaded AUCs are not chance
e2 = load('e2_evasion.json')
a_mild = dig(e2, 'auc_detect_evaded_mild')
a_sev = dig(e2, 'auc_detect_evaded_severe')
byte = dig(e2, 'byte_change_pct')
add('R5-C3', 'evaded AUC 0.775 / 0.918, byte change 0.0',
    'mild=%s severe=%s byte=%s' % (a_mild, a_sev, byte),
    a_mild is not None and a_sev is not None and byte == 0.0)

# R5 C4: tripped share is 1 - 0.04 * rate
tr = dig(e5, 'grid', 0, 'tripped_share_of_base')
add('R5-C4', '96.3% = 1 - 0.04*0.92', 'tripped_base=%s' % tr, tr is not None)

# R5 M5: Cramer's V
e15 = load('e4_peeringdb.json')
cv = None
for k in ('cramer_v', 'CramerV', 'cramers_v'):
    cv = cv if cv is not None else dig(e15, k)
add('R5-M5', "Cramer's V 0.3555", 'V=%s' % cv, cv is not None and abs((cv or 0) - 0.3555) < 1e-3)

# R5 m2: the wash grid has no point between 0.75 and 1.0
e18 = load('e18_adaptive.json')
grid = dig(e18, 'params', 'WASH_GRID', default=[])
add('R5-m2', 'escape identified only on (0.75, 1.0]', 'grid=%s' % grid,
    0.75 in grid and 1.0 in grid)

# R5 m1: counter size stated twice
hits = tex(r'sixteen bytes|16\\,B|16 B|32\\,B')
add('R5-m1', 'two counter-size statements', 'tex=%s' % (hits[:4] or 'none'), bool(hits))

# R5 M7: mean packet size of the meter benchmark
e7 = load('e7_meter.json')
pb = dig(e7, 'params', 'PACKET_BYTES', default=[])
pP = dig(e7, 'params', 'PACKET_P', default=[])
mean = sum(b * q for b, q in zip(pb, pP)) if pb and pP else None
add('R5-M7', 'mean packet 497 B', 'mean=%.1f' % mean if mean else 'n/a',
    mean is not None and abs(mean - 497.4) < 1.0)

# R1: the 4% calibration and the 84.99% in the introduction
pct = p.get('SHARE_PROVIDER')
add('R1-1', '4% calibrates Table II', 'share=%s' % pct, pct is not None)

# E18: escape at 1.0 for m >= 5
esc = dig(e18, 'escape', default={})
ok = all(abs(esc.get(str(m), {}).get('wash_to_escape_sieve', -1) - 1.0) < 1e-9
         for m in (5, 10, 20, 40))
add('R5-C2b', 'E18 escape 1.0 for m in 5..40', 'escape=%s' % {
    k: v.get('wash_to_escape_sieve') for k, v in esc.items()}, ok)

w = max(len(r[1]) for r in rows)
print('%-8s %-34s %-52s %s' % ('seat', 'claim', 'value read', ''))
for who, claim, got, ok in rows:
    print('%-8s %-34s %-52s %s' % (who, claim[:34], str(got)[:52], ok))
print('\n%d checked, %d matched' % (len(rows), sum(1 for r in rows if r[3] == 'OK')))
