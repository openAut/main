"""Opt-in FC04 adapter pattern; no discovery, configuration, deployment or write API.

The caller supplies a reviewed client, unit ID and register allow-list. There is no
automatic integration with the generic edge_agent.read_point() stub.
"""

import math
import time


class ReadOnlyTransport:
    """One polling-thread client with transport-level health and bounded RTU recovery."""

    def __init__(self, client, *, device_id, blocks, reopen_after=3, stale_after=60,
                 monotonic=time.monotonic, wall_time=time.time):
        if type(device_id) is not int or not 1 <= device_id <= 247:
            raise ValueError("explicit unit ID must be in 1..247")
        if type(reopen_after) is not int or reopen_after < 1:
            raise ValueError("reopen_after must be positive")
        if isinstance(stale_after, bool) or not math.isfinite(stale_after) or stale_after <= 0:
            raise ValueError("stale_after must be finite and positive")
        allowed = frozenset(blocks)
        if not allowed or any(
            type(address) is not int or type(count) is not int
            or address < 0 or not 1 <= count <= 125 or address + count > 65536
            for address, count in allowed
        ):
            raise ValueError("explicit FC04 blocks must fit the register address space")
        self.client = client
        self.device_id = device_id
        self.blocks = allowed
        self.reopen_after = reopen_after
        self.stale_after = stale_after
        self.monotonic = monotonic
        self.wall_time = wall_time
        self.connected = False
        self.last_success = None
        self.last_success_monotonic = None
        self.consecutive_errors = 0
        self.transport_errors = 0

    def _transport_failure(self):
        self.consecutive_errors += 1
        self.transport_errors += 1
        if self.transport_errors >= self.reopen_after:
            self.connected = False
            self.transport_errors = 0
            try:
                self.client.close()
            except Exception:
                # A broken close must not prevent the next scheduled connection attempt.
                pass

    def read(self, address, count):
        """Return validated register words or None; retry only on the caller's next poll."""
        if type(address) is not int or type(count) is not int or (address, count) not in self.blocks:
            raise ValueError("block is outside the reviewed FC04 allow-list")
        try:
            if not self.connected:
                if not self.client.connect():
                    self._transport_failure()
                    return None
                self.connected = True
            response = self.client.read_input_registers(
                address, count=count, device_id=self.device_id
            )
        except Exception:
            self._transport_failure()
            return None

        # A device exception response is not a transport failure. Do not reopen a
        # serial port repeatedly to try to fix an illegal register address.
        self.transport_errors = 0
        if response.isError():
            self.consecutive_errors += 1
            return None
        words = response.registers
        if len(words) != count or any(type(word) is not int or not 0 <= word <= 65535 for word in words):
            self.consecutive_errors += 1
            return None
        self.last_success = int(self.wall_time())
        self.last_success_monotonic = self.monotonic()
        self.consecutive_errors = 0
        return list(words)

    def health(self):
        age = None if self.last_success_monotonic is None else self.monotonic() - self.last_success_monotonic
        values = {
            "field_protocol_healthy": (
                age is not None and 0 <= age <= self.stale_after
                and self.consecutive_errors == 0
            ),
            "field_protocol_consecutive_errors": self.consecutive_errors,
        }
        if self.last_success is not None:
            values["field_protocol_last_success_unixtime"] = self.last_success
        return values
