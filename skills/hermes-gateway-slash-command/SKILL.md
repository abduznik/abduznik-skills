---
name: hermes-gateway-slash-command
description: "Add a gateway-available slash command with message tracking and batch deletion capabilities. Covers the full lifecycle: registry, dispatch, adapter callback wiring, and cleanup."
license: MIT
version: 1.0.0
author: Hermes Agent (learned from session)
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, gateway, slash-commands, telegram, adapter, batch-delete]
    related_skills: [hermes-agent]
---




# Hermes Gateway Slash Commands

How to add a new slash command to the Hermes gateway (Telegram, Discord, etc.) that can also batch-delete tracked bot messages — e.g. a `/clear` command that wipes the chat UI and starts a fresh session while preserving backend history.

## Overview

A gateway slash command needs three layers:

1. **Registration** — `CommandDef` in `hermes_cli/commands.py`
2. **Dispatch** — handler in `gateway/run.py` in **both** the cold-path and running-agent-path
3. **Message tracking** (optional, for batch deletion) — adapter callback in `gateway/platforms/base.py` + runner tracking

## Step 1: Register the Command

In `hermes_cli/commands.py`, add a `CommandDef` to `COMMAND_REGISTRY`:

```python
CommandDef("clear", "Clear chat history and start a new session", "Session"),
```

Key attributes:

| Attribute | Purpose |
|-----------|---------|
| `name` | Canonical name, no leading slash |
| `description` | Human-readable, shows in `/help` and Telegram's `/` menu |
| `category` | Grouping for help output: `"Session"`, `"Configuration"`, etc. |
| `cli_only=True` | Only available in CLI, not gateway |
| `gateway_only=True` | Only available on messaging platforms |
| `aliases=("short",)` | Alternative names that resolve to this command |
| `args_hint="[name]"` | Usage hint shown in help |

**Note:** Setting `cli_only=True` excludes the command from `GATEWAY_KNOWN_COMMANDS`, `telegram_bot_commands()`, and `gateway_help_lines()`. To make a command available in both CLI and gateway, omit `cli_only` entirely.

## Step 2: Add Gateway Handlers

### 2a. Cold Path (no running agent)

In `gateway/run.py`, inside `_handle_message()`, add the dispatch after the check for `/new` (around line 7730+).

Pattern — simple dispatch:

```python
if canonical == "clear":
    # Optional: delete trigger message from chat (best-effort)
    _clear_adapter = self.adapters.get(source.platform)
    if _clear_adapter and hasattr(_clear_adapter, 'delete_message') and event.message_id:
        try:
            await _clear_adapter.delete_message(
                chat_id=source.chat_id,
                message_id=event.message_id,
            )
        except Exception:
            pass
    return await self._handle_reset_command(event)
```

Use `_maybe_confirm_destructive_slash()` for destructive commands (matches `/new` and `/undo` pattern):

```python
if canonical == "clear":
    async def _do_clear():
        return await self._handle_reset_command(event)
    return await self._maybe_confirm_destructive_slash(
        event=event,
        command="clear",
        title="/clear",
        detail="This deletes the /clear message and starts a fresh session.",
        execute=_do_clear,
    )
```

### 2b. Running-Agent Path (agent is busy)

Commands that must bypass the running-agent guard (like `/new`, `/clear`, `/stop`) need a dedicated handler **before** the catch-all rejection.

Place it right after the `/new` block and before `/queue`:

```python
if _cmd_def_inner and _cmd_def_inner.name == "clear":
    # Interrupt any running agent first
    await self._interrupt_and_clear_session(
        _quick_key, source,
        interrupt_reason=_INTERRUPT_REASON_RESET,
        invalidation_reason="clear_command",
    )
    # Optional: batch-delete tracked bot messages from this session
    _mids = self._clear_session_bot_message_ids(_quick_key)
    if _mids:
        _adapter = self.adapters.get(source.platform)
        if _adapter and hasattr(_adapter, 'delete_message'):
            for _mid in _mids:
                try:
                    await _adapter.delete_message(chat_id=source.chat_id, message_id=_mid)
                except Exception:
                    pass
    # Delete trigger message, then reset
    ...
    return await self._handle_reset_command(event)
```

**Important:** The running-agent path must come BEFORE the `_DEDICATED_HANDLERS` / catch-all check (line ~7476) or the command will be rejected with "Agent is running — wait or /stop first".

## Step 3: Add Batch Message Deletion (Optional)

For commands that should clean up the chat UI, you need to track bot message IDs and delete them on command.

### 3a. Adapter Callback in `base.py`

Add to `BasePlatformAdapter.__init__`:

```python
self._message_sent_callback: Optional[Callable[[str, str, str], None]] = None
```

Add setter:

```python
def set_message_sent_callback(self, callback):
    self._message_sent_callback = callback
```

Wire into `_send_with_retry` (catches ALL send paths — both command responses and agent replies):

```python
async def _send_with_retry(self, ..., session_key=None):
    result = await self.send(...)
    # Fire callback after successful send
    if result.success and result.message_id and self._message_sent_callback and session_key:
        try:
            self._message_sent_callback(session_key, chat_id, result.message_id)
        except Exception:
            pass
```

Pass `session_key=session_key` in all calls to `_send_with_retry`.

### 3b. Runner Tracking in `run.py`

Add to `GatewayRunner.__init__`:

```python
self._session_bot_message_ids: Dict[str, set[str]] = {}
```

Add tracking method:

```python
def _record_bot_message_id(self, session_key: str, message_id: str) -> None:
    if not session_key or not message_id:
        return
    ids = self._session_bot_message_ids.get(session_key)
    if ids is None:
        self._session_bot_message_ids[session_key] = {message_id}
    else:
        ids.add(message_id)

def _clear_session_bot_message_ids(self, session_key: str) -> set[str]:
    return self._session_bot_message_ids.pop(session_key, set())
```

Wire callback during adapter setup (in the adapter connection loop):

```python
adapter.set_message_sent_callback(
    lambda sk, cid, mid: self._record_bot_message_id(sk, mid)
)
```

## Pitfalls

- **Telegram API limitation:** In private chats (DMs), bots can only delete their own messages — user messages (including the `/clear` trigger) silently fail to delete. In supergroups where the bot is admin, both user and bot messages can be deleted. Always wrap `delete_message` in try/except.

- **`_send_with_retry` vs `adapter.send()`:** The stream consumer (agent conversational responses) may call `adapter.send()` directly, bypassing `_send_with_retry`. If the command needs to track ALL bot messages including agent replies, also instrument `adapter.send()` or the stream consumer `deliver_final` path.

- **Activity session bypass:** Any command that must work while an agent is running needs BOTH a handler in the running-agent path (line ~7322 block) AND must be resolvable by the gateway (not `cli_only`). The running-agent handler must come before the catch-all at `_DEDICATED_HANDLERS`.

- **Session key consistency:** The `session_key` used for tracking must match the key used in `_handle_reset_command`. It's derived from `build_session_key(event.source, ...)` in `base.py`.

- **Topic lane special case:** If the command touches session state in a Telegram DM topic lane, rebind the topic → session mapping after reset via `self._record_telegram_topic_binding(source, new_entry)`.

- **Config gate for cli_only:** A command with `cli_only=True` can be made conditionally available on the gateway by setting `gateway_config_gate="some.config.path"`. The config value must be truthy for the command to appear on gateway surfaces.

## Post-Command Side-Effects (Pattern)

Some slash commands should do more than just dispatch — they should register
subscriptions, send notifications, or update state as a side-effect of running.

### Example: `/kanban` auto-subscribe on create

When a task is created via `/kanban create`, the gateway handler also
**auto-subscribes the user** to terminal-event notifications for that task:

```python
# After calling run_slash() and getting the task ID
re.search(r"Created\s+(t_[0-9a-f]+)\b", output)  # parse task_id
kanban_db.add_notify_sub(
    conn, task_id=task_id,
    platform=platform_str,
    chat_id=chat_id,
    thread_id=thread_id,
    user_id=user_id or None,
)
```

The user then receives Telegram pings when the worker completes, blocks, or
crashes — without any extra `/kanban notify-subscribe` step.

### When to use this pattern

Apply post-command side-effects when:

1. **The user creates a resource** (task, ticket, reminder) and needs to hear
   back about it without polling.
2. **The command has a lifecycle** — the side-effect subscribes the requester
   to terminal states of the created resource.
3. **The command creates a cross-session artifact** — e.g., scheduling a cron
   job should log where it was scheduled from.

### Implementation pattern

```python
# 1. Dispatch the core command
output = await asyncio.to_thread(run_slash, args_text)

# 2. Detect what was created from the output
m = re.search(r"Created\s+(t_[0-9a-f]+)\b", output)
if m:
    task_id = m.group(1)
    # 3. Extract identity from the event source
    source = event.source
    platform = getattr(source, "platform", None)
    chat_id = str(getattr(source, "chat_id", "") or "")
    thread_id = str(getattr(source, "thread_id", "") or "")
    # 4. Register the subscription in a thread pool
    def _sub():
        conn = some_db.connect()
        some_db.add_sub(conn, task_id=task_id, platform=platform, ...)
    await asyncio.to_thread(_sub)
```

### Pitfall: don't block the dispatch

Side-effects should run after the dispatch, not before. The user should see
the command output first; the subscription is invisible to them unless they
check.

## Related

- `hermes_cli/commands.py` — Root slash command registry
- `gateway/run.py` — `_handle_message()` for cold path, running-agent dispatch block
- `gateway/platforms/base.py` — `BasePlatformAdapter`, `_send_with_retry`
- `GatewayRunner.__init__` — State initialization (around line ~1770)
