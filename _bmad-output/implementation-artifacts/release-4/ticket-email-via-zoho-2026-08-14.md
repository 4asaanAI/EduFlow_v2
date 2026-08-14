# Ticket emails move to Zoho Mail, not Gmail

**Decided 2026-08-14 by Abhimanyu.** Nothing has been changed yet. This file is the
instruction sheet so the work can be picked up cold.

Related: `PROGRESS.md` in this folder (R4-5), which lists this as the last hop of the
ticket route.

---

## Why this exists

R4-5 gave the school a way to raise a ticket with Layaa AI. Everything works except the
final email. The record said that email was waiting on a Gmail sign-in being renewed in
n8n. **That is now the wrong fix.** The email is to go out through Zoho Mail instead.

## What the route looks like today

Three hops, and only the third one changes.

1. The school presses "report a problem" in EduFlow. EduFlow stores the ticket in
   LayaaStat. **Working.**
2. LayaaStat fires its webhook alert channel at n8n. **Working.**
3. n8n emails Abhimanyu and Shubham. **Broken.** It uses a Gmail step whose sign-in has
   expired.

The n8n workflow is `LayaaStat ticket to our inbox`, id `zGBva8cGLZybDhEh`, and it is
active. It has exactly two steps: a webhook called `A ticket was raised`
(`https://qwe123qwe.app.n8n.cloud/webhook/layaastat-ticket`) connected to a Gmail step
called `Email Abhimanyu and Shubham`.

The email body is already correct: subject is the first line of the message, body is the
rest, and it carries a LINK to the ticket rather than the screenshot itself. That was
decision 14 and does not change.

## The decision

**Swap the Gmail step for n8n's plain SMTP email step, pointed at Zoho.** Chosen over the
two alternatives on 2026-08-14:

- *Rejected: let LayaaStat send the email itself and retire n8n.* Fewer moving parts, but
  costs a code change and a deploy to LayaaStat for something that is one setting in n8n.
- *Rejected for now: Zoho's ZeptoMail transactional service.* Technically the best fit and
  a drop-in replacement for the dead Resend code, but it needs a new account and domain
  verification. Worth revisiting if plain mail-server sending proves unreliable.

**n8n has no Zoho Mail node.** The generic `Send Email` step
(`n8n-nodes-base.emailSend`, v2.1, operation `send`) is how Zoho is reached. Its parameters
are `fromEmail`, `toEmail`, `subject`, `emailFormat`, `text`, and it takes one credential
of type `smtp`. Do not go looking for a Zoho Mail integration; there isn't one.

**Recipients do not change:** `abhimanyu.singh@layaa.ai, shubham.sharma@layaa.ai`.

## Blocked on two things, both Abhimanyu's

### 1. A Zoho app password, entered by him, never shared in chat

- Zoho: My Account, Security, App Passwords, generate one, name it `n8n`.
- n8n: Credentials, New, search **SMTP**, name it **Zoho Mail**.
- Host: `smtp.zoho.in` for the India data centre, `smtp.zoho.com` for the global one.
  India is the likely one for a layaa.ai account set up in India. A wrong choice fails to
  connect immediately, so it is cheap to test.
- Port **465**, SSL on.
- User: the full Zoho mailbox address. Password: the app password, NOT the account password.

### 2. Which Zoho mailbox sends

Zoho will only send from a mailbox that actually exists in the account, so this cannot be
invented. Needed as the `fromEmail` value.

## What happens once those exist

1. Replace the Gmail step with a `Send Email` step carrying the same subject and body
   expressions, the same recipients, and the `Zoho Mail` credential.
2. Send one real ticket from EduFlow and watch it arrive.
3. **Do not record the route as working until that email has been seen in the inbox.**
   Every fault found in this part of R4-5 lived outside the code the tests call.

## Two consequences for the existing list

- **"Reconnect Gmail in n8n" is dead** and should not be carried forward. It is replaced
  by this.
- **Resend should now simply be deleted.** LayaaStat has a second, separate email path
  that posts to Resend's API (`src/app/api/cron/notify/route.ts`, the `email` channel).
  Its key has been dead with a 403 for a while, so those alerts were failing silently.
  With tickets going through Zoho, nothing needs it. A configured but dead sender is worse
  than no sender, because it reads as working.

---

| Date | Change |
|---|---|
| 2026-08-14 | Written. Decision taken, both blockers identified, nothing changed yet. |
