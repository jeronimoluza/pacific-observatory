# MVP panel timers on a8 (systemd --user)

| Unit | When | Runs (in `~/po-worktrees/panel36`) |
|---|---|---|
| `po-text-panel` | daily 09:00 UTC | `python run.py text panel --countries text36eap run` (stops at AWAITING_SIGNOFF) |
| `po-prices-panel` | Mon 09:30 UTC, waits while `po-text-panel` is running | `python run.py prices weekly --countries panel36 --logs-root ~/prices_panel/logs run` |
| `po-deadman` | hourly | `python run.py graph deadman` |

Every STATUS line that ends a step BLOCKED / FAILED / ABORTED, a run AWAITING_SIGNOFF, and a
run DONE goes to `po notify`. Backend and dead-man expectations: `src/configs/notify.yaml`.
Until `telegram.secret_id` is set, alerts go to `/mnt/backup5tb/po-alerts/alerts.log` and
`~/po-alerts/latest.md`.

## Before installing

1. Pin the tree to a tag that holds `mvp/autonomy` and `mvp/text36eap` (the `text36eap` panel
   and AWAITING_SIGNOFF live there). `<TAG>` is yours to name, e.g. `panel36-run-20261019`:

```
ssh a8 'cd ~/po-worktrees/panel36 && git fetch origin && git tag <TAG> <SHA> && git push origin <TAG> && git checkout --detach <TAG> && git log --oneline -1'
```

2. Dry-run what the timers will run:

```
ssh a8 'cd ~/po-worktrees/panel36 && ~/venv/bin/python run.py text panel --countries text36eap --dry-run run && ~/venv/bin/python run.py prices weekly --countries panel36 --logs-root ~/prices_panel/logs run --dry-run && ~/venv/bin/python run.py graph deadman; echo rc=$?'
```

3. Check the units:

```
ssh a8 'cd ~/po-worktrees/panel36/scripts/mvp/systemd && systemd-analyze --user verify po-*.service po-*.timer'
```

## Install

Linger is already on for jeronimoluza (`loginctl show-user jeronimoluza -p Linger` = yes); the
`enable-linger` line is a no-op then, kept so the commands work on a fresh box.

```
ssh a8 'loginctl enable-linger "$USER" && D=~/po-worktrees/panel36/scripts/mvp/systemd && \
  systemctl --user link $D/po-text-panel.service $D/po-prices-panel.service $D/po-deadman.service && \
  systemctl --user enable --now $D/po-text-panel.timer $D/po-prices-panel.timer $D/po-deadman.timer && \
  systemctl --user list-timers --no-pager "po-*"'
```

Until the first text run (and the first Monday prices run) writes a STATUS_run, `po-deadman`
raises one rojo for each (`no ~/text_panel/logs/*/STATUS_run`), once per expected time. To
avoid that, enable `po-deadman.timer` after the first runs.

`link` symlinks the files from the tree into `~/.config/systemd/user/`: moving the tree to a new
tag changes the units too. After that, run `systemctl --user daemon-reload`.

## Telegram

When the secret exists, put its id in `src/configs/notify.yaml` (`telegram.secret_id`, keys
`token` and `chat_id`) on the tag, and check `asm-exec` is on the PATH of the user manager
(`systemctl --user show-environment | grep ^PATH=`). Test:

```
ssh a8 'cd ~/po-worktrees/panel36 && ~/venv/bin/python run.py notify --severity info "telegram test"'
```

It prints `telegram` when sent, or `file (<why>): ...` when it fell back.

## Run one by hand, logs

```
ssh a8 'systemctl --user start po-deadman.service; journalctl --user -u po-deadman.service -n 30 --no-pager'
```

## Uninstall

```
ssh a8 'systemctl --user disable --now po-text-panel.timer po-prices-panel.timer po-deadman.timer && \
  systemctl --user stop po-text-panel.service po-prices-panel.service po-deadman.service; \
  systemctl --user disable po-text-panel.service po-prices-panel.service po-deadman.service; \
  rm -f ~/.config/systemd/user/po-text-panel.* ~/.config/systemd/user/po-prices-panel.* ~/.config/systemd/user/po-deadman.* && \
  systemctl --user daemon-reload && systemctl --user list-timers --no-pager "po-*"'
```

Stopping a service does not stop a step already running in its own scope; list and stop those:

```
ssh a8 'systemctl --user list-units --no-pager "po-weekly-*.scope"; systemctl --user stop "po-weekly-*.scope"'
```

`loginctl disable-linger` is not part of uninstalling: other user units may rely on it.
