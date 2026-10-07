"""Recurrence rule expansion kernel.

The kernel turns a recurrence rule -- a start instant plus a frequency, an
interval and a few bounds -- into the sequence of local datetimes the rule
fires on.  It is plain arithmetic on naive local datetimes: no clock is read,
no timezone database is consulted, and nothing ever leaves the process, so
one rule always expands to the same sequence.

A rule is built with :class:`Recurrence`::

    Recurrence(start, freq, interval=1, count=None, until=None,
               exdates=(), rdates=())

``freq`` is one of ``DAILY``, ``WEEKLY``, ``MONTHLY`` and ``YEARLY``, and
``interval`` says how many whole periods lie between two base times.

The base times
--------------
``start`` is the first base time, and every later base time is the start
moved forward by a whole number of periods:

* ``DAILY``   -- whole days, so a day is a full turn of the local wall clock.
* ``WEEKLY``  -- whole weeks, counted as seven day steps each.
* ``MONTHLY`` -- whole months, anchored on the day of the start: the day of
  the start is kept whenever the target month is long enough, and clamped
  down to the end of the month when it is not.  The clamp is recomputed from
  the start day every time, so the sequence never walks down the calendar
  (31 Jan, 28 Feb, 31 Mar, 30 Apr).
* ``YEARLY``  -- whole years, anchored on the month and the day of the start,
  clamped the same way: a rule anchored on 29 February keeps the 29th in a
  leap year and falls back to 28 February in the years without one.

Every datetime the kernel handles is a local wall clock value with no
timezone attached; a timezone aware value is a mistake, and so is a value
carrying microseconds.  The time of day of the start is kept by every base
time, so a rule never drifts across midnight.

The final sequence
------------------
``count``, ``until``, ``exdates`` and ``rdates`` turn the base times into the
final sequence:

1. the base times, dropping everything later than ``until`` (an occurrence
   that lands exactly on ``until`` is still part of the sequence);
2. plus the replacement instants ``rdates``, which may sit anywhere, earlier
   than the start included, and which collapse into a base time they repeat;
3. minus the excluded instants ``exdates``, which remove one exact instant
   each; an instant that is both a replacement and an exclusion stays out;
4. sorted ascending, with duplicates collapsed;
5. cut down to ``count`` entries, counted on the sequence that is left.

:meth:`Recurrence.occurrence_list` returns that sequence, or its first
``limit`` entries.  A rule with neither ``count`` nor ``until`` is unbounded
and needs a limit.  :meth:`Recurrence.next_after` returns the first
occurrence strictly later than the given instant, or ``None`` when the rule
has no such occurrence within the search horizon.
"""

from datetime import datetime, timedelta

__all__ = ["FREQUENCIES", "HORIZON_STEPS", "Recurrence", "RecurrenceError"]

#: The frequencies a rule may be built with.
FREQUENCIES = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")

#: How many occurrences ``next_after`` looks at before it gives up.
HORIZON_STEPS = 5000

#: Length of every month of an ordinary year.
_MONTH_LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


class RecurrenceError(ValueError):
    """Raised when a rule, or a value handed to a rule, cannot be used."""


def _is_leap(year):
    """True when *year* carries a 29th of February."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _days_in_month(year, month):
    """Number of days in the given month of the given year."""
    if month == 2 and _is_leap(year):
        return _MONTH_LENGTHS[1] + 1
    return _MONTH_LENGTHS[month - 1]


def _shift_months(year, month, months):
    """The year and month lying *months* months after the given one."""
    index = year * 12 + (month - 1) + months
    return index // 12, index % 12 + 1


def _local(value, what):
    """Check that *value* is a naive datetime on a whole second."""
    if not isinstance(value, datetime):
        raise RecurrenceError("%s: expected a datetime, got %r" % (what, value))
    if value.tzinfo is not None:
        raise RecurrenceError("%s: expected a timezone free local datetime" % what)
    if value.microsecond:
        raise RecurrenceError("%s: microsecond must be zero" % what)
    return value


def _whole_number(value, what, low):
    """Check that *value* is an integer of at least *low*."""
    if not isinstance(value, int) or isinstance(value, bool) or value < low:
        raise RecurrenceError("%s: expected an integer >= %d, got %r" % (what, low, value))
    return value


class Recurrence:
    """One recurrence rule and the sequence it expands to.

    ``start`` is the first base time, ``freq`` and ``interval`` say how the
    base times step, ``count`` and ``until`` bound them, ``exdates`` removes
    instants from the result and ``rdates`` adds instants to it.
    """

    __slots__ = ("start", "freq", "interval", "count", "until", "exdates", "rdates")

    def __init__(self, start, freq, interval=1, count=None, until=None, exdates=(), rdates=()):
        self.start = _local(start, "start")
        if freq not in FREQUENCIES:
            raise RecurrenceError(
                "freq: expected one of %s, got %r" % (", ".join(FREQUENCIES), freq)
            )
        self.freq = freq
        self.interval = _whole_number(interval, "interval", 1)
        self.count = None if count is None else _whole_number(count, "count", 1)
        self.until = None if until is None else _local(until, "until")
        if self.until is not None and self.until < self.start:
            raise RecurrenceError("until: must not lie before start")
        self.exdates = frozenset(_local(moment, "exdate") for moment in exdates)
        self.rdates = frozenset(_local(moment, "rdate") for moment in rdates)

    def __repr__(self):
        return "Recurrence(%r, %r, interval=%r)" % (self.start, self.freq, self.interval)

    def _clock(self):
        """The local time of day every base time keeps."""
        return self.start.hour, self.start.minute, self.start.second

    def _base_times(self):
        """Yield the unbounded base sequence, ascending, one at a time."""
        step = self.interval
        if self.freq == "DAILY":
            span = timedelta(days=step)
            moment = self.start
            while True:
                yield moment
                moment = moment + span
        elif self.freq == "WEEKLY":
            span = timedelta(days=7 * step)
            moment = self.start
            while True:
                yield moment
                moment = moment + span
        elif self.freq == "MONTHLY":
            hour, minute, second = self._clock()
            anchor = self.start.day
            index = 0
            while True:
                year, month = _shift_months(self.start.year, self.start.month, index)
                if year > 9999:
                    return
                day = min(anchor, _days_in_month(year, month))
                yield datetime(year, month, day, hour, minute, second)
                index += step
        else:
            hour, minute, second = self._clock()
            index = 0
            while True:
                year = self.start.year + index * step
                if year > 9999:
                    return
                day = min(self.start.day, _days_in_month(year, self.start.month))
                yield datetime(year, self.start.month, day, hour, minute, second)
                index += 1

    def _timeline(self, budget):
        """The base times needed to fill *budget* final occurrences."""
        wanted = None
        if budget is not None:
            wanted = budget + len(self.exdates) + len(self.rdates) + 1
        times = []
        for moment in self._base_times():
            if self.until is not None and moment > self.until:
                break
            times.append(moment)
            if wanted is not None and len(times) >= wanted:
                break
        return times

    def _is_excluded(self, moment):
        """True when *moment* is one of the excluded instants."""
        return moment in self.exdates

    def _final_times(self, budget):
        """The final occurrence sequence, holding at most *budget* entries."""
        kept = [moment for moment in self._timeline(budget) if not self._is_excluded(moment)]
        kept.extend(moment for moment in self.rdates if not self._is_excluded(moment))
        ordered = sorted(set(kept))
        if budget is not None:
            ordered = ordered[:budget]
        return ordered

    def occurrence_list(self, limit=None):
        """The occurrence sequence, or its first *limit* entries.

        A rule holding neither ``count`` nor ``until`` is unbounded, and
        asking for the whole sequence of such a rule is an error.
        """
        if limit is not None:
            _whole_number(limit, "limit", 1)
        budget = self.count
        if limit is not None:
            budget = limit if budget is None else min(budget, limit)
        if budget is None and self.until is None:
            raise RecurrenceError("unbounded recurrence: count, until or a limit is needed")
        return self._final_times(budget)

    def next_after(self, moment):
        """The first occurrence strictly later than *moment*, or ``None``."""
        moment = _local(moment, "moment")
        for candidate in self.occurrence_list(limit=HORIZON_STEPS):
            if candidate > moment:
                return candidate
        return None
