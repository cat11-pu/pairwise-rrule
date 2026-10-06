# rrule

A recurrence rule expansion kernel written with the Python standard library
only. There is nothing to install and no third party dependency.

A naive local `datetime` goes in as the start of the rule and the local
datetimes the rule fires on come out; the kernel never reads the system
clock, never touches the disk and never talks to the network.

## What is inside

* `rrule/core.py` - the rule object and the expansion of its sequence.
* `tests/test_core.py` - the acceptance tests for the kernel.

## Public interface

```python
from datetime import datetime
from rrule import Recurrence

daily = Recurrence(datetime(2025, 3, 3, 7, 0), "DAILY", interval=3)
daily.occurrence_list(3)                      # 03-03, 03-06, 03-09
daily.next_after(datetime(2025, 3, 6, 7, 0))  # 03-09, strictly later than the argument

monthly = Recurrence(datetime(2023, 1, 31, 12, 0), "MONTHLY")
monthly.occurrence_list(3)                    # 01-31, 02-28, 03-31

patched = Recurrence(
    datetime(2025, 3, 3, 9, 30),
    "WEEKLY",
    count=3,
    exdates=[datetime(2025, 3, 10, 9, 30)],
    rdates=[datetime(2025, 3, 12, 14, 0)],
)
patched.occurrence_list()                     # 03-03, 03-12 14:00, 03-17
```

* `freq` is one of `DAILY`, `WEEKLY`, `MONTHLY` and `YEARLY`; `interval` is a
  whole number of periods between two base times.
* Monthly and yearly rules are anchored on the day (and the month) of the
  start and clamp to the end of a short month without walking the anchor
  down, so a rule anchored on 31 January is back on 31 March.
* The final sequence is the base times plus `rdates` minus `exdates`, sorted,
  with duplicates collapsed. `exdates` remove one exact instant each; an
  instant that is both a replacement and an exclusion stays out.
* `count` cuts the final sequence, `until` is an inclusive bound, and a rule
  with neither of them is unbounded and needs a limit.
* Every occurrence keeps the time of day of the start.
* Anything unusable -- an unknown frequency, an interval below 1, a timezone
  aware or microsecond carrying datetime, a bound that cannot be met -- raises
  `RecurrenceError`, a subclass of `ValueError`.

## Running the tests

From the project root:

    python3 -m unittest discover -s tests -v

All of the tests have to pass.
