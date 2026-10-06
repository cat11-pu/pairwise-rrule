"""Behaviour tests for the recurrence rule kernel.

Run them from the project root:

    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rrule.core import Recurrence, RecurrenceError


class IntervalTest(unittest.TestCase):
    def test_the_interval_counts_whole_periods(self):
        daily = Recurrence(datetime(2025, 3, 3, 7, 0), "DAILY", interval=3)
        self.assertEqual(
            daily.occurrence_list(4),
            [
                datetime(2025, 3, 3, 7, 0),
                datetime(2025, 3, 6, 7, 0),
                datetime(2025, 3, 9, 7, 0),
                datetime(2025, 3, 12, 7, 0),
            ],
        )
        weekly = Recurrence(datetime(2025, 3, 3, 7, 0), "WEEKLY", interval=2)
        self.assertEqual(
            weekly.occurrence_list(4),
            [
                datetime(2025, 3, 3, 7, 0),
                datetime(2025, 3, 17, 7, 0),
                datetime(2025, 3, 31, 7, 0),
                datetime(2025, 4, 14, 7, 0),
            ],
        )
        monthly = Recurrence(datetime(2025, 1, 15, 7, 0), "MONTHLY", interval=3)
        self.assertEqual(
            monthly.occurrence_list(4),
            [
                datetime(2025, 1, 15, 7, 0),
                datetime(2025, 4, 15, 7, 0),
                datetime(2025, 7, 15, 7, 0),
                datetime(2025, 10, 15, 7, 0),
            ],
        )
        yearly = Recurrence(datetime(2025, 5, 15, 7, 0), "YEARLY", interval=2)
        self.assertEqual(
            yearly.occurrence_list(3),
            [
                datetime(2025, 5, 15, 7, 0),
                datetime(2027, 5, 15, 7, 0),
                datetime(2029, 5, 15, 7, 0),
            ],
        )


class MonthEndTest(unittest.TestCase):
    def test_a_monthly_anchor_comes_back_after_the_short_month(self):
        rule = Recurrence(datetime(2023, 1, 31, 12, 0), "MONTHLY")
        self.assertEqual(
            rule.occurrence_list(6),
            [
                datetime(2023, 1, 31, 12, 0),
                datetime(2023, 2, 28, 12, 0),
                datetime(2023, 3, 31, 12, 0),
                datetime(2023, 4, 30, 12, 0),
                datetime(2023, 5, 31, 12, 0),
                datetime(2023, 6, 30, 12, 0),
            ],
        )
        autumn = Recurrence(datetime(2024, 8, 31, 18, 45), "MONTHLY")
        self.assertEqual(
            autumn.occurrence_list(3),
            [
                datetime(2024, 8, 31, 18, 45),
                datetime(2024, 9, 30, 18, 45),
                datetime(2024, 10, 31, 18, 45),
            ],
        )


class LeapDayTest(unittest.TestCase):
    def test_a_leap_day_anchor_returns_on_the_next_leap_year(self):
        rule = Recurrence(datetime(2024, 2, 29, 6, 30), "YEARLY")
        self.assertEqual(
            rule.occurrence_list(6),
            [
                datetime(2024, 2, 29, 6, 30),
                datetime(2025, 2, 28, 6, 30),
                datetime(2026, 2, 28, 6, 30),
                datetime(2027, 2, 28, 6, 30),
                datetime(2028, 2, 29, 6, 30),
                datetime(2029, 2, 28, 6, 30),
            ],
        )
        plain = Recurrence(datetime(2023, 2, 28, 6, 30), "YEARLY")
        self.assertEqual(
            plain.occurrence_list(2),
            [datetime(2023, 2, 28, 6, 30), datetime(2024, 2, 28, 6, 30)],
        )


class ExclusionTest(unittest.TestCase):
    def test_an_exclusion_drops_one_exact_instant_only(self):
        start = datetime(2025, 3, 3, 9, 30)
        removed = Recurrence(start, "DAILY", count=4, exdates=[datetime(2025, 3, 5, 9, 30)])
        self.assertEqual(
            removed.occurrence_list(),
            [
                datetime(2025, 3, 3, 9, 30),
                datetime(2025, 3, 4, 9, 30),
                datetime(2025, 3, 6, 9, 30),
                datetime(2025, 3, 7, 9, 30),
            ],
        )
        kept = Recurrence(start, "DAILY", count=4, exdates=[datetime(2025, 3, 5, 8, 0)])
        self.assertEqual(
            kept.occurrence_list(),
            [
                datetime(2025, 3, 3, 9, 30),
                datetime(2025, 3, 4, 9, 30),
                datetime(2025, 3, 5, 9, 30),
                datetime(2025, 3, 6, 9, 30),
            ],
        )


class ReplacementTest(unittest.TestCase):
    def test_replacements_are_merged_in_order_and_deduplicated(self):
        start = datetime(2025, 3, 3, 9, 30)
        moved = Recurrence(
            start,
            "WEEKLY",
            count=4,
            rdates=[datetime(2025, 3, 2, 9, 30), datetime(2025, 3, 10, 9, 30)],
        )
        self.assertEqual(
            moved.occurrence_list(),
            [
                datetime(2025, 3, 2, 9, 30),
                datetime(2025, 3, 3, 9, 30),
                datetime(2025, 3, 10, 9, 30),
                datetime(2025, 3, 17, 9, 30),
            ],
        )
        repaired = Recurrence(
            start,
            "WEEKLY",
            count=3,
            exdates=[datetime(2025, 3, 10, 9, 30)],
            rdates=[datetime(2025, 3, 12, 14, 0)],
        )
        self.assertEqual(
            repaired.occurrence_list(),
            [
                datetime(2025, 3, 3, 9, 30),
                datetime(2025, 3, 12, 14, 0),
                datetime(2025, 3, 17, 9, 30),
            ],
        )

    def test_a_replacement_that_is_also_excluded_stays_out(self):
        rule = Recurrence(
            datetime(2025, 3, 3, 9, 30),
            "MONTHLY",
            count=4,
            rdates=[datetime(2025, 2, 20, 14, 0)],
            exdates=[datetime(2025, 2, 20, 14, 0)],
        )
        self.assertEqual(
            rule.occurrence_list(),
            [
                datetime(2025, 3, 3, 9, 30),
                datetime(2025, 4, 3, 9, 30),
                datetime(2025, 5, 3, 9, 30),
                datetime(2025, 6, 3, 9, 30),
            ],
        )


class BoundsTest(unittest.TestCase):
    def test_count_and_until_bound_the_sequence_that_is_left(self):
        start = datetime(2025, 3, 3, 9, 30)
        counted = Recurrence(start, "DAILY", count=4, exdates=[datetime(2025, 3, 4, 9, 30)])
        self.assertEqual(
            counted.occurrence_list(),
            [
                datetime(2025, 3, 3, 9, 30),
                datetime(2025, 3, 5, 9, 30),
                datetime(2025, 3, 6, 9, 30),
                datetime(2025, 3, 7, 9, 30),
            ],
        )
        self.assertEqual(
            counted.occurrence_list(2),
            [datetime(2025, 3, 3, 9, 30), datetime(2025, 3, 5, 9, 30)],
        )
        self.assertEqual(
            counted.next_after(datetime(2025, 3, 5, 9, 30)), datetime(2025, 3, 6, 9, 30)
        )
        self.assertIsNone(counted.next_after(datetime(2025, 3, 7, 12, 0)))
        bounded = Recurrence(start, "DAILY", until=datetime(2025, 3, 6, 9, 30))
        self.assertEqual(
            bounded.occurrence_list(),
            [
                datetime(2025, 3, 3, 9, 30),
                datetime(2025, 3, 4, 9, 30),
                datetime(2025, 3, 5, 9, 30),
                datetime(2025, 3, 6, 9, 30),
            ],
        )
        self.assertEqual(
            bounded.next_after(datetime(2025, 3, 6, 8, 0)), datetime(2025, 3, 6, 9, 30)
        )
        self.assertIsNone(bounded.next_after(datetime(2025, 3, 6, 10, 0)))


class SequenceShapeTest(unittest.TestCase):
    def test_every_sequence_starts_at_the_start_and_runs_forward(self):
        start = datetime(2025, 3, 3, 9, 0)
        for freq in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
            sequence = Recurrence(start, freq, count=5).occurrence_list()
            self.assertEqual(len(sequence), 5, freq)
            self.assertEqual(sequence[0], start, freq)
            self.assertEqual(len(set(sequence)), 5, freq)
            for earlier, later in zip(sequence, sequence[1:]):
                self.assertLess(earlier, later, freq)
            for moment in sequence:
                self.assertEqual(moment.time(), start.time(), freq)


class NextAfterTest(unittest.TestCase):
    def test_next_after_is_strictly_later_than_the_given_instant(self):
        start = datetime(2025, 3, 3, 9, 30)
        rule = Recurrence(start, "WEEKLY", interval=2)
        self.assertEqual(rule.next_after(start), datetime(2025, 3, 17, 9, 30))
        self.assertEqual(
            rule.next_after(datetime(2025, 3, 10, 9, 30)), datetime(2025, 3, 17, 9, 30)
        )
        self.assertEqual(
            rule.next_after(datetime(2025, 3, 16, 23, 0)), datetime(2025, 3, 17, 9, 30)
        )


class ErrorHandlingTest(unittest.TestCase):
    def test_rules_that_cannot_be_used_raise_recurrence_error(self):
        start = datetime(2025, 3, 3, 9, 30)
        cases = (
            ("unknown frequency", lambda: Recurrence(start, "FORTNIGHTLY")),
            ("interval zero", lambda: Recurrence(start, "DAILY", interval=0)),
            ("interval negative", lambda: Recurrence(start, "DAILY", interval=-2)),
            ("interval fractional", lambda: Recurrence(start, "DAILY", interval=1.5)),
            ("count zero", lambda: Recurrence(start, "DAILY", count=0)),
            ("count fractional", lambda: Recurrence(start, "DAILY", count=2.5)),
            (
                "timezone aware start",
                lambda: Recurrence(datetime(2025, 3, 3, 9, 30, tzinfo=timezone.utc), "DAILY"),
            ),
            (
                "start with microseconds",
                lambda: Recurrence(datetime(2025, 3, 3, 9, 30, 0, 1), "DAILY"),
            ),
            (
                "until before start",
                lambda: Recurrence(start, "DAILY", until=datetime(2025, 3, 1, 9, 30)),
            ),
            ("exdate that is not a datetime", lambda: Recurrence(start, "DAILY", exdates=["x"])),
            ("rdate that is not a datetime", lambda: Recurrence(start, "DAILY", rdates=[42])),
            ("unbounded without a limit", lambda: Recurrence(start, "DAILY").occurrence_list()),
            ("limit zero", lambda: Recurrence(start, "DAILY").occurrence_list(0)),
        )
        for label, build in cases:
            with self.subTest(case=label):
                with self.assertRaises(RecurrenceError):
                    build()


if __name__ == "__main__":
    unittest.main()
