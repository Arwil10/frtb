"""
main.py — Basel IV FRTB full runner.

Pipeline:
  1. Bank-wide backtesting -> multiplier m.             MAR32.4-32.15
  2. Per desk: compute RWA_IMA and RWA_SA independently.
  3. Run backtesting per desk -> green / red.           MAR32.16-32.19
  4. Run PLAT per desk -> pass / amber / fail.          MAR32.20-32.44
  5. Desk eligible for IMA only if BOTH tests pass.     MAR32.19 + MAR32.43
  6. Apply output floor (72.5% × total SA) on aggregate. CRR3 art. 89
"""

from dataclasses import dataclass

from config import OUTPUT_FLOOR
from portfolio.desks import DESKS
from sa.engine    import run_sa,               SAResult
from ima.engine   import run_ima,              IMAResult
from plat         import run_plat,             PLATResult,          generate_mock_pnl
from backtesting  import (
    run_backtest_desk,     DeskBacktestResult,
    run_backtest_bankwide, BankwideBacktestResult,
    generate_mock_var,
)


# Override for live feeds:
PLAT_SCENARIOS   = {'FX': 'fail',  'Eq': 'pass'}
BT_SCENARIOS     = {'FX': 'green', 'Eq': 'green'}
BT_BW_SCENARIO   = 'green'   # bank-wide scenario — override for live data


@dataclass
class DeskCapital:
    desk_id:       str
    ima:           IMAResult
    sa:            SAResult
    plat:          PLATResult
    bt:            DeskBacktestResult    # ← desk-level, brak multiplier
    rwa_used:      float
    source:        str
    capital_cliff: float


def main() -> dict:
    print('\n' + '#' * 65)
    print('  BASEL IV FRTB — FULL RUN (IMA + SA + BT + PLAT)')
    print('#' * 65)

    # ------------------------------------------------- Bank-wide backtesting
    # MAR32.4-32.15 — jeden wynik dla całego banku, mnożnik m do MAR33.41
    print(f"\n{'=' * 65}\n  BANK-WIDE BACKTESTING\n{'=' * 65}")
    bw_var_99, _, bw_apl, bw_hpl = generate_mock_var(
        'bankwide', scenario=BT_BW_SCENARIO
    )
    bw_bt: BankwideBacktestResult = run_backtest_bankwide(
        bw_var_99, bw_apl, bw_hpl, verbose=True
    )
    # mnożnik przekazywany do IMA engine poniżej
    m = bw_bt.multiplier   # MAR32.9 Table 1 → MAR33.41

    desk_results: dict[str, DeskCapital] = {}
    rwa_sa_total_all = 0.0

    for desk_id, desk in DESKS.items():
        print(f"\n{'-' * 65}\n  DESK: {desk_id}\n{'-' * 65}")

        print(f"\n[IMA]  Desk {desk_id}")
        ima = run_ima(desk, multiplier=m)   # ← m z bank-wide BT

        print(f"\n[SA]   Desk {desk_id}")
        sa  = run_sa(desk, verbose=True)

        # Desk-level backtesting — MAR32.16-32.19
        print(f"\n[BT]   Desk {desk_id}")
        bt_scenario                  = BT_SCENARIOS.get(desk_id, 'green')
        var_99, var_975, apl, hpl_bt = generate_mock_var(desk_id, scenario=bt_scenario)
        bt = run_backtest_desk(desk_id, var_99, var_975, apl, hpl_bt, verbose=True)

        # PLAT — MAR32.20-32.44
        print(f"\n[PLAT] Desk {desk_id}")
        plat_scenario = PLAT_SCENARIOS.get(desk_id, 'pass')
        hpl, rtpl     = generate_mock_pnl(desk_id, scenario=plat_scenario)
        plat          = run_plat(desk_id, hpl, rtpl, verbose=True)

        # MAR32.19 + MAR32.43 — oba testy muszą przejść
        ima_eligible = bt.ima_eligible and plat.ima_eligible

        if ima_eligible:
            rwa_used, source, cliff = ima.rwa_total, 'IMA', 0.0
        else:
            rwa_used = sa.rwa_total
            source   = f'SA (BT:{bt.status}/PLAT:{plat.status})'
            cliff    = sa.rwa_total - ima.rwa_total

        rwa_sa_total_all += sa.rwa_total

        desk_results[desk_id] = DeskCapital(
            desk_id=desk_id, ima=ima, sa=sa, plat=plat, bt=bt,
            rwa_used=rwa_used, source=source, capital_cliff=cliff,
        )

    # ------------------------------------------------------------- aggregate
    rwa_portfolio = sum(d.rwa_used      for d in desk_results.values())
    total_cliff   = sum(d.capital_cliff for d in desk_results.values())
    floor_thr     = OUTPUT_FLOOR * rwa_sa_total_all
    rwa_final     = max(rwa_portfolio, floor_thr)
    floor_binding = rwa_portfolio < floor_thr

    # ---------------------------------------------------------------- output
    print('\n\n' + '=' * 75)
    print('  CAPITAL SUMMARY — PER DESK')
    print('=' * 75)
    print(f"  {'Desk':<6} {'RWA_IMA':>11} {'RWA_SA':>11} "
          f"{'BT':>7} {'PLAT':>8} {'Source':>20} {'Cliff':>11}")
    print(f"  {'-'*6} {'-'*11} {'-'*11} {'-'*7} {'-'*8} {'-'*20} {'-'*11}")
    for d in desk_results.values():
        print(f"  {d.desk_id:<6} {d.ima.rwa_total:>11.2f} {d.sa.rwa_total:>11.2f} "
              f"{d.bt.status:>7} {d.plat.status:>8} "
              f"{d.source:>20} {d.capital_cliff:>11.2f}")

    print(f"\n{'=' * 75}")
    print(f"  BANK-WIDE BACKTESTING: {bw_bt.status.upper()}  "
          f"multiplier m={bw_bt.multiplier:.2f}")     # MAR32.9 Table 1
    print(f"{'=' * 75}")
    print(f"  OUTPUT FLOOR (CRR3 art. 89)")
    print(f"{'=' * 75}")
    print(f"  RWA portfolio (post-BT/PLAT): {rwa_portfolio:>10.2f} mln EUR")
    print(f"  RWA SA total:                 {rwa_sa_total_all:>10.2f} mln EUR")
    print(f"  Floor (72.5% x SA):           {floor_thr:>10.2f} mln EUR")
    print(f"  Floor binding?                {'YES' if floor_binding else 'NO'}")
    print(f"  {'-' * 45}")
    print(f"  RWA FINAL:                    {rwa_final:>10.2f} mln EUR")
    print(f"{'=' * 75}")

    if total_cliff > 0:
        ima_sum = sum(d.ima.rwa_total for d in desk_results.values())
        pct     = total_cliff / ima_sum * 100 if ima_sum > 0 else 0.0
        print(f"\n  CAPITAL CLIFF: {total_cliff:.2f} mln EUR (+{pct:.1f}% vs pure IMA)")
        for d in desk_results.values():
            if d.capital_cliff > 0:
                print(f"    - {d.desk_id}: IMA={d.ima.rwa_total:.2f} -> "
                      f"SA={d.sa.rwa_total:.2f} (+{d.capital_cliff:.2f})")
    if floor_binding:
        print(f"\n  Output floor adds {floor_thr - rwa_portfolio:.2f} mln EUR "
              f"on top of post-BT/PLAT RWA.")
    else:
        print(f"\n  Portfolio is {rwa_portfolio - floor_thr:.2f} mln EUR "
              f"above the output floor.")

    return {
        'rwa_final':       rwa_final,
        'rwa_portfolio':   rwa_portfolio,
        'rwa_sa_total':    rwa_sa_total_all,
        'floor_threshold': floor_thr,
        'floor_binding':   floor_binding,
        'capital_cliff':   total_cliff,
        'bw_bt_status':    bw_bt.status,
        'bw_bt_multiplier':bw_bt.multiplier,
        'desks': {
            k: {
                'rwa_ima':   d.ima.rwa_total,
                'rwa_sa':    d.sa.rwa_total,
                'bt_status': d.bt.status,
                'plat':      d.plat.status,
                'rwa_used':  d.rwa_used,
                'source':    d.source,
                'cliff':     d.capital_cliff,
            }
            for k, d in desk_results.items()
        },
    }


if __name__ == '__main__':
    main()
