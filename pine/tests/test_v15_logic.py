"""Unit tests for the SMC Metal Hunter V15.0 additions.

V15 is two scripts (TradingView allows 100,256 compiled tokens per script and
V14.7 already used almost all of them):
  ../SMC_Metal_Hunter_V15_0.pine  main strategy = V14.7 + token-neutral fixes
  ../SMC_MH15_Plus.pine           companion indicator: Elliott, rotation ladder, event mode, key levels
Each function is a line-for-line Python mirror of a Pine rule. The tests prove the
RULES and that nothing from V14.7 was removed or made bigger. They do not prove the Pine compiles:
compile it in TradingView.

Run:  python3 -m unittest discover -s pine/tests -v
"""
import math
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = open(os.path.join(HERE, "..", "SMC_Metal_Hunter_V14_7.pine"), encoding="utf-8").read()
NEW = open(os.path.join(HERE, "..", "SMC_Metal_Hunter_V15_0.pine"), encoding="utf-8").read()
PLUS = open(os.path.join(HERE, "..", "SMC_MH15_Plus.pine"), encoding="utf-8").read()


# ---------------------------------------------------------------- Elliott (section 27B)
def ew_q(prices, kinds, k, i):
    """Pivot i of the last k pivots, sign-flipped for a bear count (mirror of f_ewQ)."""
    n = len(prices)
    if k > i and n >= k:
        return prices[n - k + i] * (1.0 if kinds[n - k] == -1 else -1.0)
    return None


def ew_valid(prices, kinds, k, atr=1.0, min_atr=3.0, min_w2=23.6):
    """Mirror of f_ewValid."""
    q = [ew_q(prices, kinds, k, i) for i in range(6)]
    if q[2] is None:
        return False
    w1 = q[1] - q[0]
    ok = w1 > 0 and w1 >= atr * min_atr and q[2] > q[0] and q[2] < q[1] and (q[1] - q[2]) >= w1 * min_w2 / 100.0
    if ok and k >= 4:
        ok = q[3] > q[1]
    if ok and k >= 5:
        ok = q[4] > q[1] and q[4] < q[3]
    if ok and k == 6:
        ok = q[5] > q[3] and (q[3] - q[2]) >= min(w1, q[5] - q[4])
    return ok


def ew_stage(prices, kinds):
    for k in (6, 5, 4, 3):
        if ew_valid(prices, kinds, k):
            return k
    return 0


def ew_levels(prices, kinds, k):
    """Mirror of the level maths inside f_ewEngine. Returns (dir, invalid, level1, level2)."""
    n = len(prices)
    d = 1.0 if kinds[n - k] == -1 else -1.0
    a = prices[n - k:]
    w1 = abs(a[1] - a[0])
    if k == 3:
        return d, a[2], a[2] + d * w1, a[2] + d * w1 * 1.618
    if k == 4:
        return d, a[1], a[3] - d * abs(a[3] - a[2]) * 0.382, a[3] - d * abs(a[3] - a[2]) * 0.5
    if k == 5:
        ta, tb = a[4] + d * w1, a[4] + d * abs(a[3] - a[0]) * 0.618
        return d, a[4], (min(ta, tb) if d > 0 else max(ta, tb)), (max(ta, tb) if d > 0 else min(ta, tb))
    return d, a[5], a[5] - d * abs(a[5] - a[0]) * 0.382, a[5] - d * abs(a[5] - a[0]) * 0.618


BULL = ([100, 110, 104, 125, 116, 132], [-1, 1, -1, 1, -1, 1])
BEAR = ([132, 122, 128, 107, 116, 100], [1, -1, 1, -1, 1, -1])


class TestElliott(unittest.TestCase):
    def test_full_bull_impulse(self):
        self.assertEqual(ew_stage(*BULL), 6)

    def test_full_bear_impulse_is_the_mirror(self):
        self.assertEqual(ew_stage(*BEAR), 6)

    def test_stages_while_the_impulse_builds(self):
        p, k = BULL
        self.assertEqual(ew_stage(p[:3], k[:3]), 3)   # 0-1-2 done -> wave 3 setup
        self.assertEqual(ew_stage(p[:4], k[:4]), 4)   # wave 3 done -> wave 4 pullback
        self.assertEqual(ew_stage(p[:5], k[:5]), 5)   # wave 4 done -> wave 5 running

    def test_wave2_below_start_is_rejected(self):
        self.assertFalse(ew_valid([100, 110, 99], [-1, 1, -1], 3))

    def test_wave4_overlap_with_wave1_is_rejected(self):
        self.assertFalse(ew_valid([100, 110, 104, 125, 109], [-1, 1, -1, 1, -1], 5))

    def test_wave3_must_not_be_the_shortest(self):
        # wave 1 = 10, wave 3 = 7, wave 5 = 9 -> wave 3 shortest -> not an impulse
        self.assertFalse(ew_valid([100, 110, 105, 112, 110.5, 119.5], [-1, 1, -1, 1, -1, 1], 6))

    def test_wave1_too_small_is_noise(self):
        self.assertFalse(ew_valid([100, 102, 101], [-1, 1, -1], 3, atr=1.0, min_atr=3.0))

    def test_tiny_wave2_retrace_is_rejected(self):
        self.assertFalse(ew_valid([100, 110, 109], [-1, 1, -1], 3))   # 10 % < 23.6 %

    def test_wave3_targets_and_invalidation(self):
        p, k = BULL
        d, inv, t1, t2 = ew_levels(p[:3], k[:3], 3)
        self.assertEqual((d, inv), (1.0, 104))
        self.assertAlmostEqual(t1, 114.0)
        self.assertAlmostEqual(t2, 104 + 16.18)

    def test_wave4_zone_and_overlap_invalidation(self):
        p, k = BULL
        d, inv, z1, z2 = ew_levels(p[:4], k[:4], 4)
        self.assertEqual(inv, 110)                       # wave-1 end
        self.assertAlmostEqual(z1, 125 - 21 * 0.382)
        self.assertAlmostEqual(z2, 125 - 21 * 0.5)
        self.assertGreater(z2, inv)

    def test_wave5_targets_are_ordered_in_trade_direction(self):
        p, k = BULL
        d, inv, t1, t2 = ew_levels(p[:5], k[:5], 5)
        self.assertEqual(inv, 116)
        self.assertLessEqual(t1, t2)
        d, inv, t1, t2 = ew_levels(BEAR[0][:5], BEAR[1][:5], 5)
        self.assertEqual(d, -1.0)
        self.assertGreaterEqual(t1, t2)

    def test_correction_targets_after_five_waves(self):
        d, inv, c1, c2 = ew_levels(*BULL, 6)
        self.assertEqual(inv, 132)
        self.assertAlmostEqual(c1, 132 - 32 * 0.382)
        self.assertAlmostEqual(c2, 132 - 32 * 0.618)

    def test_failed_fifth_becomes_a_bear_setup(self):
        # wave 5 high below wave 3 high: the bull count is gone, last 3 pivots are a bear 1-2
        p, k = [100, 110, 104, 125, 116, 122], [-1, 1, -1, 1, -1, 1]
        self.assertFalse(ew_valid(p, k, 6))
        self.assertTrue(ew_valid(p, k, 3))
        self.assertEqual(ew_levels(p, k, 3)[0], -1.0)


# ---------------------------------------------------------------- rotation ladder (section 13H)
def rot_state(used, mvd, ev=False, full=100, near=85, awake=35):
    if used is None:
        return "n/a"
    if used >= full:
        return "EXPANSION (event)" if ev else "DONE - sleep"
    if used >= near:
        return "NEAR FULL"
    if used >= awake:
        return "MOVING UP" if (mvd or 0) >= 0 else "MOVING DOWN"
    return "FRESH (quiet)"


def rot_score(used, mvd, ses_ok, ev=False, full=100):
    room = 0.0 if used is None else ((15.0 if ev else 0.0) if used >= full else 100.0 - used)
    return 0.0 if room <= 0 else (room * 0.5 + min(abs(mvd or 0), 60.0)) * (1.0 if ses_ok else 0.5)


class TestRotation(unittest.TestCase):
    def test_states(self):
        self.assertEqual(rot_state(None, None), "n/a")
        self.assertEqual(rot_state(112, 80), "DONE - sleep")
        self.assertEqual(rot_state(90, 10), "NEAR FULL")
        self.assertEqual(rot_state(50, 20), "MOVING UP")
        self.assertEqual(rot_state(50, -20), "MOVING DOWN")
        self.assertEqual(rot_state(20, 5), "FRESH (quiet)")

    def test_done_asset_scores_zero_so_money_rotates(self):
        gold = rot_score(112, 90, True)
        us100 = rot_score(48, 40, True)
        self.assertEqual(gold, 0.0)
        self.assertGreater(us100, gold)

    def test_moving_asset_beats_a_sleeping_fresh_one(self):
        self.assertGreater(rot_score(50, 40, True), rot_score(20, 0, True))

    def test_off_session_asset_is_halved(self):
        self.assertAlmostEqual(rot_score(40, 30, False), rot_score(40, 30, True) / 2)

    def test_missing_data_never_wins(self):
        self.assertEqual(rot_score(None, None, True), 0.0)

    def test_event_day_full_adr_is_not_sleep(self):
        self.assertEqual(rot_state(130, 100, ev=True), "EXPANSION (event)")
        self.assertGreater(rot_score(130, 100, True, ev=True), 0.0)


# ---------------------------------------------------------------- event mode (section 13F)
def ev_phase(mins, clock_on=True, mode="Auto", pre=60, spike=30, follow=180):
    clk = clock_on and mode != "Off"
    if clk and -pre <= mins < 0:
        return 1
    if clk and 0 <= mins < spike:
        return 2
    if clk and spike <= mins < follow:
        return 3
    return 0


def ev_active(mode, ph, atr, atr_base, adr_used, vol_x=1.8, adr_pct=120):
    vol_ev = mode == "Auto" and (atr >= atr_base * vol_x or (adr_used or 0) >= adr_pct)
    return mode == "On (event day)" or ph >= 2 or vol_ev


def sc_vol(vol_healthy, sqz_release, ev_day, atr, atr_base):
    """Main script score factor V: with the "News / Event Days" input ON, extreme volatility still counts."""
    return vol_healthy or sqz_release or (ev_day and atr >= atr_base * 0.7)


class TestEventMode(unittest.TestCase):
    def test_clock_phases(self):
        self.assertEqual(ev_phase(-61), 0)
        self.assertEqual(ev_phase(-60), 1)
        self.assertEqual(ev_phase(-1), 1)
        self.assertEqual(ev_phase(0), 2)
        self.assertEqual(ev_phase(29), 2)
        self.assertEqual(ev_phase(30), 3)
        self.assertEqual(ev_phase(179), 3)
        self.assertEqual(ev_phase(180), 0)

    def test_off_and_no_clock_never_enter_a_phase(self):
        self.assertEqual(ev_phase(5, mode="Off"), 0)
        self.assertEqual(ev_phase(5, clock_on=False), 0)

    def test_pre_event_window_does_not_change_the_strategy(self):
        self.assertFalse(ev_active("Auto", 1, 1.0, 1.0, 40))

    def test_auto_switches_on_with_volatility(self):
        self.assertTrue(ev_active("Auto", 0, 1.9, 1.0, 40))
        self.assertTrue(ev_active("Auto", 0, 1.0, 1.0, 125))
        self.assertFalse(ev_active("Auto", 0, 1.2, 1.0, 60))

    def test_input_off_is_identical_to_v147(self):
        for atr in (0.5, 1.0, 2.0, 3.0):
            for healthy in (True, False):
                self.assertEqual(sc_vol(healthy, False, False, atr, 1.0), healthy)

    def test_extreme_volatility_counts_only_with_the_input_on(self):
        self.assertFalse(sc_vol(False, False, False, 3.0, 1.0))   # V14.7 rule
        self.assertTrue(sc_vol(False, False, True, 3.0, 1.0))     # no block on news days
        self.assertFalse(sc_vol(False, False, True, 0.5, 1.0))    # a dead market is still not tradable


# ---------------------------------------------------------------- key levels (section 13G)
def parse_lvls(csv):
    out = []
    for part in csv.replace(" ", "").split(","):
        try:
            out.append(float(part))
        except ValueError:
            pass
    return out


def next_lvl(a, direction, px):
    best = None
    for v in a:
        if (direction == 1 and v > px) or (direction == -1 and v < px):
            if best is None or (direction == 1 and v < best) or (direction == -1 and v > best):
                best = v
    return best


def scenario(close, pivot):
    return "ALIVE" if close >= pivot else "OVER"


class TestKeyLevels(unittest.TestCase):
    UPS = parse_lvls("4150,4200,4280")
    DNS = parse_lvls("4083, 4055,3875,3700")

    def test_parse_ignores_spaces_and_junk(self):
        self.assertEqual(self.DNS, [4083.0, 4055.0, 3875.0, 3700.0])
        self.assertEqual(parse_lvls("4150,,abc, 4200"), [4150.0, 4200.0])
        self.assertEqual(parse_lvls(""), [])

    def test_users_gold_example(self):
        self.assertEqual(next_lvl(self.UPS, 1, 4160), 4200)
        self.assertEqual(next_lvl(self.UPS, 1, 4200), 4280)
        self.assertEqual(next_lvl(self.DNS, -1, 4160), 4083)
        self.assertEqual(next_lvl(self.DNS, -1, 4083), 4055)
        self.assertEqual(scenario(4160, 4020), "ALIVE")
        self.assertEqual(scenario(4019.9, 4020), "OVER")
        self.assertEqual(next_lvl(self.DNS, -1, 4010), 3875)

    def test_no_level_left(self):
        self.assertIsNone(next_lvl(self.UPS, 1, 4300))
        self.assertIsNone(next_lvl(self.DNS, -1, 3600))


# ---------------------------------------------------------------- multi-asset sizing (section 16)
def quote_usd(currency, usd_base, close):
    """usd_base = ticker starts with "USD" (USDJPY, USDCHF ...)."""
    if currency == "USD":
        return 1.0
    if usd_base:
        return 1.0 / close
    return None


def xtb_lots(balance, risk_pct, fx, entry, stop, contract, q_usd, lot_step=0.01, min_lot=0.01):
    ok = q_usd is not None and contract > 0
    risk_usd = balance * risk_pct / 100.0 / fx
    dist = abs(entry - stop)
    raw = risk_usd / (dist * contract * q_usd) if dist > 0 and ok else 0.0
    lots = math.floor(raw / lot_step + 1e-9) * lot_step
    return lots if lots >= min_lot else 0.0


def position_size(equity, risk_pct, entry, stop, point_value, q_usd, qty_step=0.01, min_qty=0.01):
    risk_cash = equity * risk_pct / 100.0
    dist = abs(entry - stop)
    raw = risk_cash / (dist * point_value * (1.0 if q_usd is None else q_usd)) if dist > 0 else 0.0
    q = math.floor(raw / qty_step) * qty_step
    return q if q >= min_qty else 0.0


class TestMultiAssetSizing(unittest.TestCase):
    def test_gold_and_silver_unchanged_from_v146(self):
        self.assertAlmostEqual(xtb_lots(10000, 0.5, 1.0, 2650.0, 2640.0, 100, quote_usd("USD", False, 2650)), 0.05)
        self.assertAlmostEqual(xtb_lots(10000, 0.5, 1.0, 31.00, 30.70, 5000, quote_usd("USD", False, 31)), 0.03)

    def test_usdjpy_risk_is_converted_to_usd(self):
        q = quote_usd("JPY", True, 150.0)
        lots = xtb_lots(10000, 0.5, 1.0, 150.00, 149.70, 100000, q)       # 30 pips
        self.assertAlmostEqual(lots, 0.25)
        self.assertLessEqual(lots * 100000 * 0.30 * q, 50.0 + 1e-9)       # loss in USD <= 50
        qty = position_size(10000, 0.5, 150.00, 149.70, 1.0, q)
        self.assertAlmostEqual(qty * 0.30 * q, 50.0, places=1)

    def test_unknown_quote_currency_gives_no_lots(self):
        self.assertEqual(xtb_lots(10000, 0.5, 1.0, 0.86, 0.859, 100000, quote_usd("GBP", False, 0.86)), 0.0)


# ---------------------------------------------------------------- nothing removed from V14.7
class TestNoReduction(unittest.TestCase):
    KINDS = ["input.", "alertcondition(", "alert(", "f_row(", "f_pc(", "f_sc(", "f_mc(", "f_scr(", "label.new(",
             "line.new(", "box.new(", "plotshape(", "strategy.entry(", "strategy.exit(", "strategy.cancel("]

    def test_counts_never_go_down(self):
        for k in self.KINDS:
            self.assertGreaterEqual(NEW.count(k), OLD.count(k), k)

    def test_every_input_title_survives(self):
        titles = lambda s: set(re.findall(r'input\.\w+\(.*?, "([^"]+)"', s))
        missing = [t for t in re.findall(r'input\.\w+\([^"\n]*?, "([^"]+)"', OLD) if ('"' + t + '"') not in NEW]
        self.assertEqual(missing, [])
        self.assertIn('"News Rule"', NEW)
        self.assertGreater(len(titles(NEW)), len(titles(OLD)))

    def test_every_alertcondition_title_survives(self):
        for t in re.findall(r'alertcondition\([^"]*"([^"]+)"', OLD):
            self.assertIn('"' + t + '"', NEW)

    def test_pine_limits(self):
        self.assertLessEqual(NEW.count("request.security("), 40)
        self.assertLessEqual(len(re.search(r'shorttitle="([^"]*)"', NEW).group(1)), 10)
        self.assertNotIn("\t", NEW)
        self.assertIn('"V15.0 TERMINAL"', NEW)

    def test_main_script_is_not_bigger_than_v147(self):
        """V14.7 compiled under the 100,256 token limit; the V15 main script must not grow (CE10117)."""
        tok = re.compile(r'"[^"\n]*"|#[0-9a-fA-F]{6,8}|\d+\.\d+|\d+|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*|:=|==|!=|>=|<=|=>|\+=|-=|[-+*/%<>=?:,()\[\]]')
        count = lambda src: sum(len(tok.findall(re.sub(r'//[^"]*$', '', l))) for l in src.split("\n"))
        self.assertLessEqual(count(NEW), count(OLD))
        self.assertLess(count(PLUS), count(OLD) / 3)

    def test_companion_table_and_limits(self):
        rows = int(re.search(r"table\.new\(ctxPos, 5, (\d+)", PLUS).group(1))
        self.assertEqual(rows, 15)                                   # rows 7 + k (k = 0..6) and GO TRADE row 14
        self.assertLess(max(int(x) for x in re.findall(r"f_sc\(\d+, (\d+),", PLUS)), rows)
        self.assertLessEqual(PLUS.count("request.security("), 40)
        self.assertLessEqual(len(re.search(r'shorttitle="([^"]*)"', PLUS).group(1)), 10)
        self.assertNotIn("\t", PLUS)
        self.assertIsNone(re.search(r"strategy\.(entry|exit|close|cancel|order)", PLUS))   # information only, never orders


if __name__ == "__main__":
    unittest.main(verbosity=2)
