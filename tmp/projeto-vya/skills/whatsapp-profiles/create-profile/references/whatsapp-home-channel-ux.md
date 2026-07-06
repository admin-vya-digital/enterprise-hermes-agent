# WhatsApp home channel UX — avoid leaking `/sethome` onboarding

## Problem

If a WhatsApp profile has no `WHATSAPP_HOME_CHANNEL` in its profile `.env`, the gateway sends this notice on the first interaction of a new session/contact:

```text
📬 No home channel is set for Whatsapp. A home channel is where Hermes delivers cron job results and cross-platform messages.

Type /sethome to make this chat your home channel, or ignore to skip.
```

For customer-facing bots this is unacceptable UX because every new client can see internal Hermes onboarding before the real answer.

## Key finding

`HOME_NUMBER` is only governance metadata. The gateway check uses the env var resolved by `_home_target_env_var('whatsapp')`, i.e.:

```bash
WHATSAPP_HOME_CHANNEL=<chat_id_or_lid>
WHATSAPP_HOME_CHANNEL_THREAD_ID=
```

The `/sethome` command is just a chat-side way to persist those env values. If Root already knows the correct WhatsApp chat id/LID, it can write the env values directly in the profile `.env`.

## Bot-mode implication

In `WHATSAPP_MODE=bot`, the bridge intentionally ignores `fromMe=true` messages. Therefore a client cannot reliably set home by sending `/sethome` from the same number connected to the QR/self-chat: the bridge treats it as an echo/self message and skips it.

This does NOT mean the client needs two numbers for normal operations. It means provisioning should set `WHATSAPP_HOME_CHANNEL` automatically after QR validation.

## Recommended provisioning rule

After scanning QR and validating `session/creds.json`, derive the connected account's real LID/JID:

- prefer `creds.me.lid`, normalized from `<LID_EXEMPLO_3>:xx@lid` to `<LID_EXEMPLO_3>@lid`
- fallback to `creds.me.id`, normalized from `5511...:xx@s.whatsapp.net` to `5511...@s.whatsapp.net`

Then write to the profile `.env`:

```bash
WHATSAPP_HOME_CHANNEL=<normalized-lid-or-jid>
WHATSAPP_HOME_CHANNEL_NAME=<CLIENT_ID-or-business-name>
WHATSAPP_HOME_CHANNEL_THREAD_ID=
```

Restart the gateway so it reloads env.

## Operational note

Using the connected bot number as `WHATSAPP_HOME_CHANNEL` is mainly a technical default to suppress onboarding. It is not a good manual testing channel in bot mode. For end-to-end QA, use a second phone/contact to message the bot number.
