"""
sa/drcima.py — SA Default Risk Charge, equity only.

Two methods:
  bucket   : K_b = max(ΣJtD_long − HBR·ΣJtD_short, 0) × RW_b
  pd_based : per-position EL = PD·LGD·|N|, aggregated with HBR from JtD

HBR: HBR = ΣJtD_long_net / (ΣJtD_long_net + |ΣJtD_short_net|)
"""

from collections import defaultdict
from dataclasses import dataclass

from config import SA_DRC_RW_NON_SEC, SA_DRC_RW_BUCKET as DRC_RW, CONVERSION_FACTOR
from portfolio.drc import DRCPosition


# ============================================================================
# Result dataclasses
# ============================================================================
@dataclass
class ObligorNetting:
    obligor_id: str
    bucket:     str
    jtd_long:   float
    jtd_short:  float
    jtd_net:    float


@dataclass
class BucketDRC:
    bucket:       str
    rw:           float
    jtd_long:     float
    jtd_short:    float
    hbr:          float
    drc_net:      float
    drc_weighted: float


@dataclass
class DRCResult:
    desk_id:         str
    method:          str
    obligor_netting: list[ObligorNetting]
    buckets:         list[BucketDRC]
    drc_total:       float
    rwa_total:       float


# ============================================================================
# Step 1–2: net per obligor
# ============================================================================
def _net_by_obligor(positions: list[DRCPosition]) -> list[ObligorNetting]:
    groups: dict[str, dict] = defaultdict(
        lambda: {'jtd_long': 0.0, 'jtd_short': 0.0, 'bucket': 'NR'}
    )
    for p in positions:
        g = groups[p.obligor_id]
        g['bucket'] = p.rating_bucket
        jtd = p.jtd_gross
        if jtd >= 0:
            g['jtd_long']  += jtd
        else:
            g['jtd_short'] += abs(jtd)

    return [
        ObligorNetting(
            obligor_id = oid,
            bucket     = g['bucket'],
            jtd_long   = g['jtd_long'],
            jtd_short  = g['jtd_short'],
            jtd_net    = g['jtd_long'] - g['jtd_short'],
        )
        for oid, g in groups.items()
    ]


# ============================================================================
# Step 3–4: bucket method
# ============================================================================
def _drc_bucket_method(netting: list[ObligorNetting]) -> list[BucketDRC]:
    agg: dict[str, dict] = defaultdict(lambda: {'long': 0.0, 'short': 0.0})
    for ob in netting:
        if ob.jtd_net >= 0:
            agg[ob.bucket]['long']  += ob.jtd_net
        else:
            agg[ob.bucket]['short'] += abs(ob.jtd_net)

    out = []
    for bucket, sums in agg.items():
        long_, short_ = sums['long'], sums['short']
        rw  = DRC_RW.get(bucket, DRC_RW['NR'])
        hbr = long_ / (long_ + short_) if (long_ + short_) > 0 else 0.0
        net = max(long_ - hbr * short_, 0.0)
        out.append(BucketDRC(bucket, rw, long_, short_, hbr, net, net * rw))
    return out


# ============================================================================
# PD-based method (granular)
# ============================================================================
def _drc_pd_method(positions: list[DRCPosition]) -> list[BucketDRC]:

    agg: dict[str, dict] = defaultdict(
        lambda: {'el_long': 0.0, 'el_short': 0.0,
                 'jtd_long': 0.0, 'jtd_short': 0.0}
    )
    for p in positions:
        bucket = p.rating_bucket
        g      = agg[bucket]
        el     = p.pd * p.lgd * abs(p.notional_eur)
        jtd    = abs(p.jtd_gross)
        if p.notional_eur >= 0:
            g['el_long']  += el
            g['jtd_long'] += jtd
        else:
            g['el_short']  += el
            g['jtd_short'] += jtd

    out = []
    for bucket, g in agg.items():
        l_jtd, s_jtd = g['jtd_long'], g['jtd_short']
        rw  = DRC_RW.get(bucket, DRC_RW['NR'])
        hbr = l_jtd / (l_jtd + s_jtd) if (l_jtd + s_jtd) > 0 else 0.0
        net = max(g['el_long'] - hbr * g['el_short'], 0.0)
        out.append(BucketDRC(bucket, rw, l_jtd, s_jtd, hbr, net, net))
    return out


# ============================================================================
# Runner
# ============================================================================
def compute_drc(
    positions: list[DRCPosition],
    desk_id:   str,
    method:    str = 'pd_based',
) -> DRCResult:
    if not positions:
        return DRCResult(desk_id, method, [], [], 0.0, 0.0)

    netting = _net_by_obligor(positions)
    buckets = (_drc_bucket_method(netting) if method == 'bucket'
               else _drc_pd_method(positions))

    drc_total = sum(b.drc_weighted for b in buckets)
    return DRCResult(
        desk_id         = desk_id,
        method          = method,
        obligor_netting = netting,
        buckets         = buckets,
        drc_total       = drc_total,
        rwa_total       = drc_total * CONVERSION_FACTOR,
    )
