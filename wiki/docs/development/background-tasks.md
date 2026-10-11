# Background tasks: queue work and return promptly

## Host-managed schedules (v1.1)

For a short bounded action, declare `scheduled_tasks` in `manifest.json` and an
explicit `tasks.background` permission. The host adds native interval, enabled,
Run now and result controls in Administration → Tasks. Schedules start off.

```json
{
  "id": "library-summary",
  "name": "Library summary",
  "description": "Reports the background administrator's library count.",
  "action_id": "scheduled-summary",
  "min_interval_minutes": 5,
  "max_interval_minutes": 10080,
  "default_interval_minutes": 1440
}
```

Declare the referenced action with a real handler and no confirmation. It receives
`{"_scheduled_task":{"id":"library-summary","trigger":"scheduled"}}` or a
`manual` trigger and uses the plugin's existing background administrator context.
It may return `{"completed":true,"summary":"Read 3 games"}`. The host retains
only this bounded public summary, enforces the action's live permission, prevents
overlapping runs of one job and uses the existing 30-second isolated action limit.
Plugin disable, permission withdrawal, an inactive administrator and runtime
outages pause the controls. User-targeted background operations still require the
existing opt-in subscriptions; scheduling does not broaden data access.

IDs must be stable and unique, with at most 32 tasks and integer intervals between
one minute and thirty days. The default must fit the declared bounds. Updates and
ordinary reinstall retain settings within the same installation identity. The
UI/API example includes this recipe. Long-running sync should retain its existing
supervised worker and durable queue approach below.

### Personal schedules (v1.1.11)

Set `scope: "user"` on a declaration to place it on Account → Background tasks.
The host binds each schedule to the account enabling it, checks that account's
background/action grants live and dispatches with its authenticated action context.
The default scope remains `server`; personal tasks cannot expose server maintenance
jobs or override the background identity of an existing server task.

For a resumable import, return `completed: false`, a bounded public `summary` and
`continue_after_seconds: 60`. The host clamps the delay to 60–3600 seconds, keeps
steps within the existing action limit and continues only while autosync remains
enabled. Return `completed: true` after the final checkpoint to restore the user's
chosen interval. Returning a failure without a delay waits for that interval.
Epic Games uses the same `sync` action for its Games menu and personal schedule.

## Goal

Have an action record durable work for one supervised worker.

## Prerequisites

Declare `tasks.background` and `plugin.storage` v1 with permission rationales.
Read Jellyfin's `sync_now`, `worker_tick` and entrypoint before adapting its queue.
The action below is only the producer; it requires a matching worker consumer.

## Minimal code

<!-- recipe: background -->
```python
import json
from uuid import uuid4
from sdk.plugin_protocol import request

def run(values: dict) -> dict:
    request("capabilities.check", "tasks.background", {})
    request("storage.put", "plugin.storage", {
        "key": "sync/requests/" + str(uuid4()),
        "value": json.dumps({"requested": True}),
    })
    return {"queued": True}
```

Unique request keys avoid an action overwriting the worker's progress. The worker
must consume bounded batches, save progress and only remove completed requests.
Recover outstanding requests after restart; record safe failures and retries.
Do not introduce another scheduler or assume one action process shares memory
with the entrypoint. See the [complete integration recipe](events-tasks.md).

## Test command

```sh
python -m pytest tests/test_feature_tutorials.py -k background
python -m pytest tests/test_jellyfin.py -k "worker_queue or queue_arriving"
```

## Expected result

The recipe checks background authority before writing a durable request and
returns `queued: true`. Denial prevents the write. Jellyfin's tests verify a
request arriving during sync survives and that retry/cursor state is durable.
The real host suite runs the supervised sync worker against a disposable service.

## Common mistakes

Running the sync in the action; using one mutable queue key for competing writes;
equating queued with completed; retrying irreversible side effects without
deduplication; continuing work after the live background grant is revoked.
