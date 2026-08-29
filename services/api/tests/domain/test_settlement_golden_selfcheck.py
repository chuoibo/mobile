"""Check the settlement corpus is internally consistent, without any production code.

WHAT THIS PROVES, and what it does not.

It recomputes, from the recorded obligations and receipts alone:

  * the netted balance of every person, by the rule transcribed by hand from
    spec section 8.8 (sum per directed pair first, subtract the confirmed
    receipt for that pair, drop pairs already cleared);
  * that the balances sum to exactly zero, and that total debt equals total
    credit to the dong;
  * that every zero-sum group recorded in the vector really sums to zero, that
    the groups are disjoint, and that together they cover exactly the people
    with a non-zero balance;
  * that the recorded group count is MAXIMAL, by brute force over every
    partition-into-zero-sum-subsets of the balance multiset;
  * that `chuyen_toi_thieu` equals N - K, the lower bound;
  * that `chuyen_cua_greedy` is what the largest-debtor-to-largest-creditor
    greedy actually produces.

Nothing here imports `app.domain`. The corpus stands on its own, which is the
point: the vectors were written before the algorithm, and this file is what
proves the hand arithmetic in them is not wrong.

It does NOT prove the corpus author read the contract correctly. This file and
the vectors have the same author, so a shared misreading -- of what "minimum
number of transfers" means, say -- would appear identically in both and stay
green. That is why every vector also carries `can_duoi`: the lower-bound
argument in prose, for a human reviewer to check independently of any code.
"""

from __future__ import annotations

import json
import pathlib
import unittest
from collections import defaultdict

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden_settlement"


def load_vectors():
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        for vector in json.loads(path.read_text(encoding="utf-8")):
            yield path.name, vector


def require_dong(value):
    """Integer dong only. `bool` is rejected explicitly because
    `isinstance(True, int)` is True in Python and True would become one dong."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AssertionError(f"khong phai so nguyen dong: {value!r}")
    return value


def balances_from_ledger(obligations, receipts):
    """Hand transcription of the netting rule. Deliberately not imported."""
    owed = defaultdict(int)
    for obligation in obligations:
        sender = obligation["sender_id"]
        recipient = obligation["recipient_id"]
        assert sender != recipient, "nghia vu tu no chinh minh"
        owed[(sender, recipient)] += require_dong(obligation["amount_vnd"])

    received = defaultdict(int)
    for receipt in receipts:
        received[(receipt["sender_id"], receipt["recipient_id"])] += require_dong(
            receipt["amount_vnd"]
        )

    positions = defaultdict(int)
    for pair, total in owed.items():
        remaining = total - received.get(pair, 0)
        if remaining <= 0:
            continue
        sender, recipient = pair
        positions[sender] -= remaining
        positions[recipient] += remaining
    return {person: amount for person, amount in sorted(positions.items()) if amount != 0}


def max_zero_sum_groups(balances):
    """Largest number of disjoint subsets that each sum to zero and cover all.

    Brute force over subsets, memoised on the remaining set. Exponential and
    only ever run on corpus-sized inputs, which is what makes it trustworthy as
    a cross-check: it does no pruning that could be subtly wrong.
    """
    people = sorted(balances)
    n = len(people)
    if n == 0:
        return 0
    amounts = [balances[p] for p in people]

    sums = [0] * (1 << n)
    for mask in range(1, 1 << n):
        low = (mask & -mask).bit_length() - 1
        sums[mask] = sums[mask ^ (1 << low)] + amounts[low]

    best = [-1] * (1 << n)
    best[0] = 0
    for mask in range(1, 1 << n):
        low = mask & -mask
        # Every partition puts the lowest remaining person in exactly one
        # group, so only submasks containing them need to be tried.
        sub = mask
        while sub:
            if sub & low and sums[sub] == 0 and best[mask ^ sub] >= 0:
                best[mask] = max(best[mask], best[mask ^ sub] + 1)
            sub = (sub - 1) & mask
    return best[(1 << n) - 1]


def greedy_transfers(balances):
    """Hand transcription of largest-debtor-to-largest-creditor greedy."""
    debtors = sorted(((p, -a) for p, a in balances.items() if a < 0), key=lambda x: (-x[1], x[0]))
    creditors = sorted(((p, a) for p, a in balances.items() if a > 0), key=lambda x: (-x[1], x[0]))
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, owed = debtors[i]
        creditor, due = creditors[j]
        amount = min(owed, due)
        transfers.append((debtor, creditor, amount))
        debtors[i] = (debtor, owed - amount)
        creditors[j] = (creditor, due - amount)
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers


class SettlementCorpusSelfCheck(unittest.TestCase):
    def test_corpus_is_not_empty(self):
        vectors = list(load_vectors())
        self.assertGreaterEqual(
            len(vectors), 6, "dieu kien nghiem thu doi it nhat 6 kich ban nhom"
        )

    def test_every_vector_is_internally_consistent(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                expect = vector["expect"]
                expected_balances = {k: require_dong(v) for k, v in expect["balances"].items()}

                recomputed = balances_from_ledger(
                    vector["input"]["obligations"], vector["input"]["receipts"]
                )
                self.assertEqual(
                    recomputed, expected_balances, "can doi tinh tay khong khop voi so"
                )

                # Rule of the task: total owed equals total due, difference zero.
                self.assertEqual(sum(expected_balances.values()), 0)
                debts = -sum(a for a in expected_balances.values() if a < 0)
                credits = sum(a for a in expected_balances.values() if a > 0)
                self.assertEqual(debts, credits, "tong no phai bang tong co")
                self.assertNotIn(0, expected_balances.values(), "nguoi lech 0 phai bi loai")

                self.assertEqual(
                    expect["nguoi_lech_khac_khong"],
                    len(expected_balances),
                    "so nguoi lech khac khong ghi sai",
                )

    def test_recorded_groups_really_partition_into_zero_sums(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                expect = vector["expect"]
                balances = expect["balances"]
                groups = expect["nhom_zero_sum"]

                seen = []
                for group in groups:
                    self.assertGreaterEqual(len(group), 2, "nhom zero-sum can >= 2 nguoi")
                    self.assertEqual(
                        sum(balances[p] for p in group), 0, f"nhom {group} khong tong 0"
                    )
                    seen.extend(group)

                self.assertEqual(len(seen), len(set(seen)), "cac nhom phai roi nhau")
                self.assertEqual(set(seen), set(balances), "cac nhom phai phu het nguoi lech")
                self.assertEqual(expect["so_nhom_toi_da"], len(groups))

    def test_recorded_group_count_is_actually_maximal(self):
        """The claim that catches an over-optimistic hand answer.

        If a vector says K = 2 while a partition into 3 zero-sum groups exists,
        the recorded minimum is too high and the whole vector is wrong.
        """
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                expect = vector["expect"]
                brute = max_zero_sum_groups(expect["balances"])
                self.assertEqual(
                    brute,
                    expect["so_nhom_toi_da"],
                    f"{vector['id']}: vet can luc ra K={brute}, vector ghi {expect['so_nhom_toi_da']}",
                )

    def test_minimum_transfers_equals_people_minus_groups(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                expect = vector["expect"]
                self.assertEqual(
                    expect["chuyen_toi_thieu"],
                    expect["nguoi_lech_khac_khong"] - expect["so_nhom_toi_da"],
                    "chuyen_toi_thieu phai bang N - K",
                )

    def test_recorded_greedy_count_matches_the_greedy_it_describes(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                expect = vector["expect"]
                transfers = greedy_transfers(expect["balances"])
                self.assertEqual(
                    len(transfers),
                    expect["chuyen_cua_greedy"],
                    "so lan chuyen cua greedy ghi sai",
                )
                # Greedy is never better than the optimum, by definition.
                self.assertGreaterEqual(
                    expect["chuyen_cua_greedy"], expect["chuyen_toi_thieu"]
                )

    def test_corpus_contains_a_case_where_greedy_is_not_minimal(self):
        """Without this, the corpus could not tell a minimal algorithm from the
        greedy one already in `ledger.py`, and the whole task would be untested."""
        gaps = [
            vector["id"]
            for _, vector in load_vectors()
            if vector["expect"]["chuyen_cua_greedy"] > vector["expect"]["chuyen_toi_thieu"]
        ]
        self.assertGreaterEqual(len(gaps), 2, f"can >= 2 ca greedy thua, dang co: {gaps}")

    def test_no_float_anywhere_in_the_corpus(self):
        def walk(node, path):
            if isinstance(node, float):
                raise AssertionError(f"float trong corpus tai {path}: {node!r}")
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{path}[{index}]")

        for path in sorted(GOLDEN_DIR.glob("*.json")):
            walk(json.loads(path.read_text(encoding="utf-8")), path.name)


class SelfCheckCatchesABadVector(unittest.TestCase):
    """The self-check above is only worth its green if it can go red.

    Same reasoning as `test_selfcheck_catches_mutants.py` for the allocator: a
    consistency check nobody has seen fail is not evidence.
    """

    def test_brute_force_finds_a_better_partition_than_a_wrong_claim(self):
        # {a,c} and {b,d} both sum to zero, so K is 2, not 1.
        balances = {"a": -100, "b": -200, "c": 100, "d": 200}
        self.assertEqual(max_zero_sum_groups(balances), 2)

    def test_brute_force_refuses_to_invent_groups_that_do_not_exist(self):
        # No proper subset sums to zero, so the only partition is the whole set.
        balances = {"a": -550, "b": -850, "c": 1050, "d": 350}
        self.assertEqual(max_zero_sum_groups(balances), 1)

    def test_greedy_transcription_reproduces_the_known_gap(self):
        balances = {"a": -500000, "b": -400000, "c": 200000, "d": 300000, "e": 400000}
        self.assertEqual(len(greedy_transfers(balances)), 4)
        self.assertEqual(max_zero_sum_groups(balances), 2)  # optimum is 5 - 2 = 3

    def test_balance_recompute_notices_a_receipt(self):
        obligations = [{"sender_id": "b", "recipient_id": "a", "amount_vnd": 300000}]
        self.assertEqual(balances_from_ledger(obligations, []), {"a": 300000, "b": -300000})
        receipts = [{"sender_id": "b", "recipient_id": "a", "amount_vnd": 300000}]
        self.assertEqual(balances_from_ledger(obligations, receipts), {})


if __name__ == "__main__":
    unittest.main()
