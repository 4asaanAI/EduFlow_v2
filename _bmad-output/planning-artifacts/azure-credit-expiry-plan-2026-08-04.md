# Azure credit has expired. What happens next, and what we do.

Written 2026-08-04, from the sponsorship billing screen and the live Azure account.

## The facts, not estimates

| | |
|---|---|
| Credit source | Azure startup sponsorship, **$5,000** |
| Effective | 18 April 2026 |
| **Expired** | **19 July 2026** (on a date, not when it ran out) |
| Balance now | **$0.00** |
| Charges 1 to 19 July | **$7,455.40** against $1,910.18 remaining |
| **Uncovered** | **about $5,545** |
| Spending limit | **Off**, which is why charges continued past the credit |

Two separate problems, and they need separating:

1. **A debt of roughly $5,545.** Disabling the card stops collection. It does not cancel
   the amount. Azure will chase it and eventually suspend the subscription.
2. **No credit from 19 July onward.** Every rupee of Azure use since then is billable.
   This is the one that ends AI access.

## What actually breaks

Checked against the code, not assumed.

**Stops working:**
- **Flo, completely.** Chat, every tool she can run, document drafting.
- **Reading photos** (`vision_service` uses the same Azure deployment).
- One AI helper inside the academics screen.

**Keeps working, untouched:**
- Attendance, fees, students, staff, timetable, transport, library, incidents, reports, exports.
- **Certificates and ID cards.** They are drawn by our own server and never touch Azure.
- Every tool screen, login, notifications, file uploads.

So the school keeps its records system. It loses its assistant.

## Why 99.7% of the bill was AI

Measured across June to August: **Rs 11.28 lakh of Rs 11.31 lakh was Foundry Models.**
App Service was Rs 1,221. Container Registry Rs 976. Storage Rs 7.

Nothing else is worth optimising. The AI is the entire cost.

## The options, with real numbers

### Option A — Groq free tier (Shubham has already built this)

His `local_testing` branch already runs Groq as the primary provider. This is no longer a
"reconcile the branches" question; it is the contingency plan, already written.

Free tier limits for `openai/gpt-oss-120b`, from Groq's own documentation:

| Limit | Value |
|---|---|
| Tokens per minute | **8,000** |
| Tokens per day | **200,000** |
| Requests per minute | 30 |
| Requests per day | 1,000 |

**The 8,000 per minute ceiling is the hard part, and it explains everything Shubham did.**

| Version | Tokens per owner message | Fits in 8,000/min? |
|---|---|---|
| Live code today | ~43,000 | **No, five times over** |
| After my cost work | ~17,000 | **No, still double** |
| With Shubham's tool trim (~34 tools) | ~6,000 to 8,000 | **Yes, just** |

So Groq only works with **his** trimming, not mine. Mine was sized for cost on Azure; his
was sized for this exact ceiling. His has to win.

At 200,000 tokens a day that is roughly **25 to 30 messages per day for the whole school.**
Recent real usage was about 118,000 tokens on 2 August alone, so this is tight but survivable
for light use, and will not survive a busy day.

Cost: **free.**

### Option B — Gemini, on the key you already own

The `GEMINI_API_KEY` sitting unused in the production settings **is live**. I tested it
today: it works and reaches `gemini-2.5-pro` and `gemini-2.5-flash`. Google's free tier needs
no billing account.

Nothing in EduFlow currently calls it, so this is real work, not a switch. But the key is
already yours and already paid for in the sense that it costs nothing.

Worth checking the exact per-model limits in Google AI Studio before committing, because the
public docs no longer publish them.

### Option C — Pay for Azure

Roughly $250 a month at July's rate. After the cost work now sitting on the branch, closer
to **$100 a month**. Requires a working payment method and settles the debt question.

### Option D — Apply for the next sponsorship milestone

The $25,000 tier. This is the actual fix, not a patch. It needs several actively used
workloads over about 60 days, which EduFlow demonstrably is. It will not arrive tomorrow, so
it does not solve this week.

## Recommendation, in order

1. **Today: turn the Azure spending limit back on.** Free, immediate, and it stops the debt
   growing while everything else is decided.
2. **Today: ship Shubham's provider work.** It is written, it is the only thing sized for
   Groq's ceiling, and it is the difference between Flo working and Flo stopping. Combine it
   with the correctness fixes on my branch, his trimming winning where they overlap.
3. **This week: wire Gemini as the second fallback**, using the key already in the account.
   Two free providers is meaningfully safer than one, given Groq's daily cap.
4. **This week: apply for the next milestone.**
5. **Decide separately what to do about the $5,545.** That is a commercial conversation, not
   an engineering one.

## What this changes about earlier decisions

- **The model comparison is moot for now.** luna and sol are both Azure. There is no point
  choosing between them while there is no way to pay for either.
- **The deploy plan changes.** "Close everything, then ship it all together" was right
  yesterday. Today the provider work is urgent and should not wait behind the rest.
- **My cost work matters more, not less.** A 60% cut is worth little at $250 a month and
  worth a great deal when the ceiling is 8,000 tokens a minute.
