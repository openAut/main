# Read-only transport reliability pattern

`scripts/readonly_transport.py` is an opt-in reference for a reviewed equipment-specific bridge.
It accepts an already constructed pymodbus-compatible client, an explicit unit ID and an exact
FC04 block allow-list. It neither discovers devices nor deploys services and has no write method.
It is tested with fake clients; it is an extraction of lab lessons, not the deployed lab artifact.

Use one instance per integration in one polling thread. The caller schedules reads and owns the
client's configuration, shutdown, dependencies, spool and MQTT namespace. After three consecutive
transport exceptions the adapter closes the client; the next scheduled read attempts connection.
It also handles failed/throwing connect and throwing close operations. Device exception responses
and malformed register data report errors without serial reopen churn.

Health records the latest valid response and monotonic freshness. Any current error makes the
reference adapter unhealthy; successful reading resets the error count. The latest success epoch
is omitted until a valid response exists. Publish health through the bridge's normal event-ID and
spool path. Consumers must evaluate its age; a retained boolean can outlive the running process.
One successful block proves transport reachability, not freshness of every point. Track unavailable
blocks separately and never derive a false aggregate alarm-clear state from missing alarm words.

The generic IOT2050 `read_point()` remains a stub. A case-scoped equipment adapter must explicitly
adopt this pattern and verify the exact pymodbus version and firmware behavior before deployment.
The tests do not prove automatic recovery from a physical serial adapter fault.

Use the separate [polling/publication policy](polling-publication.md) to keep faster reads from
increasing durable enqueue and database frequency. It also throttles last-success timestamps
without throttling health transitions, and preserves change-only alarm publication.
