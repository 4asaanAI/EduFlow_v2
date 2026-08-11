# How the school actually charges fees

**Source:** Sonu Ruhal, the school's accountant head, by telephone to Abhimanyu on
2026-08-11. Abhimanyu relayed it in writing the same day. **This document is the authority
on fee calculation.** Where it disagrees with anything else in the repository, including
the Vedmarg exports in `aaryans_database/`, this wins.

**Checked, not just recorded.** Every rule below was tested against the school's own
payment ledger, `aaryans_database/Fees-log-detailed-11-08-2026-17-36.xlsx`: 10,720 fee
lines, 3,177 receipts, 1,723 children, 23 January to 7 August 2026. Where the ledger
confirms a rule, the evidence is written on the line. Where it cannot confirm it, that is
said instead of assumed.

---

## 1. The four concessions, and nothing else recurring

Sonu's list is closed: these are the only recurring concessions the school gives.

### 1.1 Sibling discount

**The youngest child in a family always pays the full fee. Every other child in that
family gets the discount.** With two children, the elder is discounted and the younger
pays full. With three or more, only the youngest pays full and all the rest are
discounted.

The amount is **flat per quarter and depends on the discounted child's own class band**,
from the school's 2026-27 fee sheet: 1,410 / 1,560 / 1,650 / 1,800 / 2,100 / 2,610 /
2,910. These seven values are already loaded into the platform correctly and must not be
recreated.

*Ledger evidence:* 853 payment lines carry a discount at exactly one of those seven
values, across 503 children. The rule is real and in daily use.

### 1.2 Employee's child

**50% off, for the child of any employee of the school, whatever their job.**

*Ledger evidence:* 154 lines carry a discount of exactly half the quarterly fee for that
child's class.

### 1.3 Paying the whole year at once

**5% off the session's fee** when a parent pays the full year rather than by quarter.

*Not yet confirmed from the ledger*, because a 5% line cannot be told apart from an
ordinary custom amount by its value alone. See the open questions.

### 1.4 One-time discounts at admission

Not a rule, a decision. A family with a connection to the school asks; **Aman and Adesh
decide**; if they agree they tell Sonu an amount, and he applies it **once**, when the
family pays its first instalment.

*Ledger evidence:* round amounts appear repeatedly outside every band above, most often
6,000 (74 lines), 7,000, 6,500 and 8,000. That is the shape of a negotiated figure.

**What this means for the platform:** a one-time discount must record **who authorised
it**, and must not repeat itself in later quarters. Sonu applies it; he does not decide
it.

---

## 2. Late fines. The school's method, not Vedmarg's

Fees are charged quarterly, and each quarter has a 15-day window to pay.

| Quarter | Covers | Due by | Daily fine runs | 1,000 charged |
|---|---|---|---|---|
| Q1 | April to June | 15 April | 16 April to 30 June | 1 July |
| Q2 | July to September | 15 July | 16 July to 30 September | 1 October |
| Q3 | October to December | 15 October | 16 October to 31 December | 1 January |
| Q4 | January to March | 15 January | 16 January to 31 March | 1 April |

**The rule in one sentence: 10 rupees a day from the 16th until the quarter ends, then a
single 1,000 when the next quarter begins, and the daily fine then stops for good on that
quarter.**

Worked through on Sonu's own example. A family that has paid nothing:

1. **1 to 15 April.** The normal Q1 fee, after whatever concession applies.
2. **16 April to 30 June.** 10 a day accumulating. That is 76 days, so 760 by 30 June.
3. **1 July.** 1,000 is added. Q1 now stands at fee + 760 + 1,000, **and stops growing.**
4. **1 to 15 July.** Q2's normal fee is added on top of that.
5. **16 July to 30 September.** 10 a day, **on Q2 only.**
6. **1 October.** Another 1,000, for Q2. Q1 is untouched.

**This is exactly where Vedmarg is wrong and must not be copied.** Vedmarg keeps Q1's
daily fine running after Q2 begins, so two daily fines accrue at once and families are
overcharged. **Only one daily fine ever runs at a time: the current quarter's.**

*Ledger evidence:* every one of the 1,217 fine lines in the school's ledger is an exact
multiple of 10, across 992 children. Eight lines are exactly 1,000.

**All of section 2 applies to school fees only. Transport is not fined.**

---

## 3. Transport

**No concession of any kind, for anybody.** No sibling discount, no employee discount, no
5% for paying the year up front.

The charge varies by distance, roughly 650 to 1,520 a month, and is billed monthly rather
than quarterly. 1,235 children pay it.

**The platform currently says not one of its 1,876 students uses the bus.** That is wrong,
and the ledger is what proves it.

---

## 4. Sonu's feature request: sibling tags

He asked for a child with a brother or sister in the school to be **tagged as a sibling,
with the other children's admission numbers shown on the record and on the fee screen**,
so the office can see at a glance who is owed which discount.

**Feasible, and the ledger gives a strong starting list.** Grouping the 1,723 children in
it by father's name and mobile number finds **764 children in a family of two or more**:
300 pairs, 44 threes, 6 fours and one family of eight.

**But it cannot be switched on unattended, for two reasons.**

1. **Matching is not proof.** 111 children who actually receive the sibling discount today
   are not detected by father plus mobile, and matching on mobile alone finds more
   families but would group unrelated children who share a number. A wrong match either
   overcharges a family or gives away money.
2. **The discount depends on who is youngest, and the platform often does not know.** 787
   children have no date of birth recorded. Class is a poor substitute: two children can
   sit in the same class.

So the right shape is **the platform proposes the family groups and a person confirms
them**, which also gives Sonu the screen he asked for.

---

## 5. Open questions. Do not guess at these

| # | Question | Why it matters |
|---|---|---|
| 1 | Does a quarter left unpaid take **one** 1,000 only, or another 1,000 at every following quarter end? | Sonu's example shows Q1 taking one and then standing still, but the phrase "only quarter end fine keeps on going" could mean the opposite. Over a year the difference is 3,000 per family. |
| 2 | Do the concessions **stack**? An employee with two children: 50% and the sibling discount, or the better of the two? | It changes real bills today. |
| 3 | Is the 5% conditional on paying **before 30 April**, as the school's printed fee sheet says, or available whenever a parent pays the year up front, as Sonu described it? | Decides whether a payment in August qualifies. |
| 4 | Is the 1,000 at quarter end the **same charge** as the "1,000 per instalment" the printed fee sheet attaches to re-admission after a strike-off, or two different charges? | If they are the same thing, one of the two descriptions is wrong and a family could be billed twice. |
| 5 | Are unpaid **transport** dues fined at all? | Sonu said the fine rules are school fees only, which may mean transport is never fined or may simply not have been covered. |
| 6 | The ledger's own summary line disagrees with its own rows: 4.29 crore billed against 4.12 crore, and about 9 lakh outstanding against 3.5 lakh. Collected money agrees exactly. | An outstanding figure becomes a family's bill. Still open from the previous session. |
