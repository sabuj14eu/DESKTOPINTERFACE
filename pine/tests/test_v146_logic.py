"""Unit tests for the SMC Metal Hunter V14.6 reliability fixes.

Pine Script has no test runner, so each rule below is a line-for-line Python
mirror of the Pine logic in ../SMC_Metal_Hunter_V14_6.pine. These tests prove
the RULES are right (sizing maths, gate precedence, oil vote, monitor wording).
They do not prove the Pine compiles; compile it in TradingView.

Run:  python3 -m unittest discover -s pine/tests -v
"""
import itertools
import math
import unittest


# ---------------------------------------------------------------- sizing (section 16)
def f_position_size(equity, risk_pct, entry, stop, point_value, qty_step, min_qty):
    """Backtest qty in TradingView units (mirror of f_positionSize)."""
    risk_cash = equity * risk_pct / 100.0
    dist = abs(entry - stop)
    pv = max(point_value or 1.0, 0.000001)
    raw = risk_cash / (dist * pv) if dist > 0 else 0.0
    q = math.floor(raw / qty_step) * qty_step
    return q if q >= min_qty else 0.0


def f_xtb_lots(balance, risk_pct, fx, entry, stop, contract, lot_step=0.01, min_lot=0.01, price_usd=True):
    """XTB broker lots (mirror of f_xtbLots)."""
    risk_usd = balance * risk_pct / 100.0 / fx
    dist = abs(entry - stop)
    raw = risk_usd / (dist * contract) if dist > 0 and price_usd else 0.0
    lots = math.floor(raw / lot_step + 1e-9) * lot_step
    return lots if lots >= min_lot else 0.0


def loss_usd(lots, contract, dist):
    return lots * contract * dist


class TestXtbSizing(unittest.TestCase):
    GOLD_OZ = 100
    SILVER_OZ = 5000

    def test_gold_example(self):
        # 10,000 USD, 0.5 % risk = 50 USD, 10 USD stop on GOLD (100 oz/lot) -> 0.05 lots
        lots = f_xtb_lots(10000, 0.5, 1.0, 2650.0, 2640.0, self.GOLD_OZ)
        self.assertAlmostEqual(lots, 0.05)
        self.assertAlmostEqual(loss_usd(lots, self.GOLD_OZ, 10.0), 50.0)

    def test_silver_example(self):
        # 50 USD risk, 0.30 USD stop on SILVER (5000 oz/lot) -> 0.033 -> floor to 0.03
        lots = f_xtb_lots(10000, 0.5, 1.0, 31.00, 30.70, self.SILVER_OZ)
        self.assertAlmostEqual(lots, 0.03)
        self.assertLessEqual(loss_usd(lots, self.SILVER_OZ, 0.30), 50.0 + 1e-9)

    def test_never_risks_more_than_target(self):
        for dist in [0.5, 1, 2.5, 7.3, 10, 23, 55]:
            lots = f_xtb_lots(10000, 0.5, 1.0, 2650.0, 2650.0 - dist, self.GOLD_OZ)
            self.assertLessEqual(loss_usd(lots, self.GOLD_OZ, dist), 50.0 + 1e-9)

    def test_old_qty_was_100x_too_big_for_xtb_gold(self):
        # the V14.5 number shown as "QTY" assumed 1 unit = 1 oz (TradingView point value 1)
        old_qty = f_position_size(10000, 0.5, 2650.0, 2640.0, 1.0, 0.01, 0.01)
        self.assertAlmostEqual(old_qty, 5.0)
        self.assertAlmostEqual(loss_usd(old_qty, self.GOLD_OZ, 10.0), 5000.0)  # 100x the intended 50 USD

    def test_account_currency_conversion(self):
        # 40,000 PLN, 0.5 % = 200 PLN = 50 USD at 4.0 PLN/USD -> same 0.05 lots
        self.assertAlmostEqual(f_xtb_lots(40000, 0.5, 4.0, 2650.0, 2640.0, self.GOLD_OZ), 0.05)

    def test_below_min_lot_returns_zero(self):
        # 1,000 USD account, 5 USD risk, 30 USD stop -> 0.0017 lots < 0.01 min
        self.assertEqual(f_xtb_lots(1000, 0.5, 1.0, 2650.0, 2620.0, self.GOLD_OZ), 0.0)

    def test_non_usd_chart_is_rejected(self):
        self.assertEqual(f_xtb_lots(10000, 0.5, 1.0, 83661.0, 77081.0, self.SILVER_OZ, price_usd=False), 0.0)


# ---------------------------------------------------------------- entry gates (section 15)
def old_buy_setup(c):
    """V14.5 expression: `a and b and ... and not vetoBuy or trapBuy` ('and' binds before 'or')."""
    return (c["isExecTF"] and c["allowLong"] and c["confirmed"] and (c["trend"] or c["model"])
            and c["candle"] and c["scoreOK"] and c["macroOK"] and not c["veto"]) or c["trapBuy"]


def new_buy_setup(c, need_candle=False, need_score=False, need_macro=False):
    common = c["isExecTF"] and c["allowLong"] and c["confirmed"] and not c["veto"]
    std = (c["trend"] or c["model"]) and c["candle"] and c["scoreOK"] and c["macroOK"]
    trap_ok = (c["trapBuy"] and (not need_candle or c["candle"]) and (not need_score or c["scoreOK"])
               and (not need_macro or c["macroOK"]))
    return common and (std or trap_ok)


def trap_buy(c):
    """trapBuy itself already contains these (section 13C)."""
    return c["trapRaw"] and c["isExecTF"] and c["allowLong"] and not c["veto"]


KEYS = ["isExecTF", "allowLong", "trend", "model", "candle", "scoreOK", "macroOK", "veto", "trapRaw"]


def all_cases():
    for bits in itertools.product([False, True], repeat=len(KEYS)):
        c = dict(zip(KEYS, bits))
        c["confirmed"] = True          # traps are only detected on a closed bar
        c["trapBuy"] = trap_buy(c)
        yield c


class TestEntryGates(unittest.TestCase):
    def test_default_new_gates_equal_old_expression(self):
        for c in all_cases():
            self.assertEqual(new_buy_setup(c), old_buy_setup(c), c)

    def test_trap_never_bypasses_common_gates(self):
        for c in all_cases():
            if new_buy_setup(c):
                self.assertTrue(c["isExecTF"] and c["allowLong"] and not c["veto"], c)

    def test_trap_bypasses_score_candle_macro_by_default(self):
        c = dict.fromkeys(KEYS, False)
        c.update(isExecTF=True, allowLong=True, confirmed=True, trapRaw=True)
        c["trapBuy"] = trap_buy(c)
        self.assertTrue(new_buy_setup(c))                       # score/candle/macro all False
        self.assertFalse(new_buy_setup(c, need_score=True))
        self.assertFalse(new_buy_setup(c, need_candle=True))
        self.assertFalse(new_buy_setup(c, need_macro=True))


# ---------------------------------------------------------------- oil vote (section 13)
def oil_votes(oil_up, oil_dn, be_up, be_dn, oil_av=True, be_av=True):
    o_up, o_dn = oil_av and oil_up, oil_av and oil_dn
    b_up, b_dn = be_av and be_up, be_av and be_dn
    infl = (o_up and b_up) or (o_dn and b_dn)
    return int(infl and o_up), int(infl and o_dn), int(infl)   # bull vote, bear vote, counted


class TestOilChannel(unittest.TestCase):
    def test_falling_oil_alone_is_not_bearish(self):
        self.assertEqual(oil_votes(False, True, True, False), (0, 0, 0))    # growth scare
        self.assertEqual(oil_votes(False, True, False, False), (0, 0, 0))   # breakevens flat

    def test_disinflation_is_bearish(self):
        self.assertEqual(oil_votes(False, True, False, True), (0, 1, 1))

    def test_inflation_impulse_is_bullish(self):
        self.assertEqual(oil_votes(True, False, True, False), (1, 0, 1))

    def test_no_breakeven_data_means_no_vote(self):
        self.assertEqual(oil_votes(False, True, False, True, be_av=False), (0, 0, 0))


# ---------------------------------------------------------------- monitor + pending order (20B)
def monitor_step(in_pos, mon_pts, auto_cancel, order_live=True):
    """Returns (decision text, order still live after this bar)."""
    if in_pos:
        return ("EXIT NOW" if mon_pts >= 4 else "HOLD"), order_live
    if mon_pts >= 3:
        if auto_cancel:
            return "CANCELLED BY MONITOR", False
        return "CANCEL ADVISED - ORDER STILL LIVE", order_live
    return ("PENDING: CAUTION" if mon_pts >= 1 else "PENDING: VALID"), order_live


class TestPendingLifecycle(unittest.TestCase):
    def test_never_shows_cancel_pending_while_order_live(self):
        for pts in range(0, 8):
            for auto in (False, True):
                text, live = monitor_step(False, pts, auto)
                self.assertNotEqual(text, "CANCEL PENDING")
                if text.startswith("CANCELLED"):
                    self.assertFalse(live)
                if live and text.startswith("CANCEL"):
                    self.assertIn("ORDER STILL LIVE", text)

    def test_auto_cancel_really_cancels(self):
        self.assertEqual(monitor_step(False, 3, True), ("CANCELLED BY MONITOR", False))

    def test_manual_mode_keeps_order_and_says_so(self):
        self.assertEqual(monitor_step(False, 5, False), ("CANCEL ADVISED - ORDER STILL LIVE", True))


# ---------------------------------------------------------------- trap alert wording (13C)
def trap_alert(approved, why):
    return "BULL TRAP DETECTED (info only, NOT a trade) | " + (
        "sell candidate: wait for the SELL LIMIT order alert" if approved else "not approved: " + why)


class TestTrapAlert(unittest.TestCase):
    def test_detected_trap_has_no_trade_levels(self):
        for approved in (False, True):
            text = trap_alert(approved, "grade C below B; ")
            for word in (" E ", " SL ", " TP1 ", " TP2 "):
                self.assertNotIn(word, text)

    def test_unapproved_trap_states_reason(self):
        self.assertIn("not approved: grade C", trap_alert(False, "grade C below B; "))


if __name__ == "__main__":
    unittest.main(verbosity=2)
