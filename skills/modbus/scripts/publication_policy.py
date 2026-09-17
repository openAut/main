"""Opt-in, single-thread publication filter before event creation and durable enqueue.

The caller still polls every scheduled interval and submits only validated observations.
No transport, scheduler, MQTT connection, spool or deployment is created here.
"""

import math
import time


class PublicationPolicy:
    """Per-metric periodic snapshots or change-only publication, with startup snapshots.

    enqueue(metric, value, ts, unit) must return only after durable acceptance, and
    raise on failure. It owns event-ID creation and must not re-enter this instance.
    Instantiate one policy per integration; state is deliberately not persisted.
    """

    def __init__(self, *, periodic, on_change, enqueue, monotonic=time.monotonic):
        intervals = dict(periodic)
        changes = frozenset(on_change)
        if not intervals and not changes:
            raise ValueError("an explicit publication profile is required")
        if any(not isinstance(metric, str) or not metric for metric in intervals.keys() | changes):
            raise ValueError("metric names must be nonempty strings")
        if intervals.keys() & changes:
            raise ValueError("a metric cannot be both periodic and change-only")
        for interval in intervals.values():
            if (isinstance(interval, bool) or not isinstance(interval, (int, float))
                    or not math.isfinite(interval) or interval <= 0):
                raise ValueError("publication intervals must be finite and positive")
        if not callable(enqueue) or not callable(monotonic):
            raise ValueError("enqueue and monotonic must be callable")
        self._periodic = intervals
        self._on_change = changes
        self._enqueue = enqueue
        self._monotonic = monotonic
        self._last_publication = {}
        self._last_value = {}

    def submit(self, metric, value, ts, unit):
        """Return True after enqueue, False when suppressed; never cache analog samples.

        ts is the observation's source epoch, not the publication time. The caller
        validates value, timestamp, unit and per-point freshness before calling.
        Do not submit cached process readings after a failed read. A health timestamp
        may intentionally retain an old last-success value: consumers must age it.
        """
        if metric not in self._periodic and metric not in self._on_change:
            raise ValueError("metric is outside the publication profile")
        now = self._monotonic()
        if metric in self._periodic:
            previous = self._last_publication.get(metric)
            if previous is not None and now - previous < self._periodic[metric]:
                return False
        elif metric in self._last_value:
            previous = self._last_value[metric]
            if type(previous) is type(value) and previous == value:
                return False

        # If persistence fails, keep the point due and a changed state unacknowledged.
        self._enqueue(metric, value, ts, unit)
        self._last_publication[metric] = now
        if metric in self._on_change:
            self._last_value[metric] = value
        return True
