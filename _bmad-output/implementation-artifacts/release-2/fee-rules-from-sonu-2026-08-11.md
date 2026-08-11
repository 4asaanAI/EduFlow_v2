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

**5% off the session's fee**, and **only if the whole year is paid on or before 30 April**
(Abhimanyu, 2026-08-11, answer 3). A parent paying the full year in August does not
qualify. The printed fee sheet and Sonu agree on this.

*Ledger evidence:* 446 lines across 41 children carry a remark saying so in the office's
own words, most often "FULL FEES PAID 5 PER DISCOUNT", "5 PER DIS" and "5 DISC.".

### 1.2b The concessions do NOT stack

**A child entitled to both the employee discount and the sibling discount keeps the
employee discount only** (Abhimanyu, 2026-08-11, answer 2). Not both, and not the better
of the two by calculation: the employee one, by rule.

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

### 2.1 The 1,000 repeats. SETTLED

Abhimanyu, 2026-08-11, twice and the second time against a specific number: **a quarter
that stays unpaid takes a fresh 1,000 at every following quarter end.** A family that pays
nothing for the whole session is charged the 1,000 **four times**.

So an unpaid Q1 takes 1,000 on 1 July, again on 1 October, again on 1 January and again on
1 April. Only the daily 10 stops when the next quarter starts; the 1,000 does not.

*This was queried because the worked example that first described it ended with one 1,000
apiece, which reads the other way. The example was abbreviated. The rule above is the
one to build.*

### 2.2 The fine is charged on the whole bill, transport included

Corrected by Sonu on 2026-08-11, reversing what was said an hour earlier. **Transport is
added into the total before the fine is worked out.** There is no separate transport fine
and no separate transport due date: one outstanding figure, one daily fine, one 1,000.

So transport carries **no concession but the full fine**.

### 2.3 The 1,000 is NOT the re-admission charge

Two different things (Abhimanyu, 2026-08-11, answer 4). The 1,000 at quarter end is
automatic. The "1,000 per instalment" on the printed fee sheet is part of what a
struck-off child pays to be re-admitted, at the Principal's discretion. A family in
arrears can therefore meet both, and that is correct rather than double billing.

---

## 3. Transport

**No concession of any kind, for anybody.** No sibling discount, no employee discount, no
5% for paying the year up front. **But it is fined like everything else**, because it is
folded into the total before the fine is worked out (section 2.2).

The charge varies by distance, roughly 650 to 1,520 a month, and is billed monthly rather
than quarterly. 1,235 children pay it.

**Eleven months, not twelve. June is not charged**, because the school closes for the
summer and the buses do not run, although staff are paid and the school fee is still
charged for that quarter (Abhimanyu, 2026-08-11).

*Ledger evidence, and it is exact:* the ledger holds transport lines for April, May, July,
August, September, October, November, December, January, February and March. **There is
not one June transport line in 5,587 rows.** An earlier note in this repository claimed
the ledger showed all twelve months; that was wrong and is corrected here.

**The platform currently says not one of its 1,876 students uses the bus.** That is wrong,
and the ledger is what proves it.

---

## 3.1 Right to Education children

Sonu, 2026-08-11. Some children hold a **Right to Education** place from the government.
They **pay no school fee at all**. If they use the bus they pay the transport charge, and
that charge is fined on the ordinary schedule if it is late.

Their transport IS fined on the ordinary schedule, the 1,000 at quarter end included
(Abhimanyu, 2026-08-11, having checked with Sonu).

**The platform has no way of recording this today** and it is not a discount: the fee is
not reduced, it does not apply. Recording it as a 100% discount would be wrong, because it
would then interact with the concession rules and would be reversible by anyone who can
edit a discount.

**The list already exists and does not need to be asked for.** The student export
`Students-06-08-2026-12-08-00.xlsx` carries a column `IsRteStudent`, and **21 children are
marked Yes**. Nobody had looked, and the plan was about to ask the school for a list it
had already sent. The school marks them twice over: all 21 also carry "(RTE)" inside the
child's own name.

*Cross-checked against the ledger and it holds.* 13 of the 21 appear in it. **Not one was
charged a school fee.** Six were charged transport only, six had their school fee written
off in full, and the only other charge to any of them is a late fine of 140 on one child,
which confirms rather than contradicts the rule above.

**The 15067 discrepancy was closed on 2026-08-12 and was never real.** It was recorded
here as a child whose name said "RTE" while the flag said `No`. The child is **PIRTEEK
CHOUDHARY**: the letters r-t-e sit inside the spelling of the name, and the check that
found it was matching letters rather than whole words. All 21 genuine children write it in
brackets. The school's flag column and its naming agree everywhere.

**The 21 are confirmed** (Abhimanyu, 2026-08-11) and are loaded by migration 038.

---

## 4. Sonu's feature request: sibling tags

He asked for a child with a brother or sister in the school to be **tagged as a sibling,
with the other children's admission numbers shown on the record and on the fee screen**,
so the office can see at a glance who is owed which discount.

**The office is already doing this by hand, in the remarks column.** 2,308 payment lines
across 441 children carry a remark naming the sibling, usually in the form
`SIB NO - 221858`. That yields **414 sibling links stated explicitly by the school
itself**, which is evidence rather than inference and is the seed list to start from.

Beyond those, grouping the 1,723 children by father's name and mobile number finds **764
in a family of two or more**: 300 pairs, 44 threes, 6 fours and one family of eight. Those
are candidates, not facts.

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

## 5. What order to load this in

Abhimanyu, 2026-08-11, answer 6: **load the money actually collected and each child's
normal fee. Do not calculate any late fine yet.** The fines come last, once section 2.1 is
settled.

That instruction also disposes of the ledger's internal disagreement, which was only ever
about billed and outstanding totals. **Money collected agrees to the rupee**, and that is
the half being loaded.

---

## 6. Still open. Do not guess at these

| # | Question | Why it matters |
|---|---|---|
| 1 | **Is the extra charge on a late Right to Education child 100 or 1,000?** Written as "100 also gets added along with 10perday" on 2026-08-11. Everywhere else the quarter-end charge is 1,000, so this is most likely a typo, **but it is money and was not assumed.** | Ten times the charge, on the families least able to pay it. |
| ~~2~~ | ~~Confirm the 21 Right to Education children~~ | **Confirmed by Abhimanyu, 2026-08-11.** |
| ~~3~~ | ~~Admission 15067 has "RTE" in the child's name but the flag says No~~ | **Closed 2026-08-12: never real.** The child is PIRTEEK CHOUDHARY and the letters are inside the name. |

**Answered and closed on 2026-08-11:** the 1,000 repeats every quarter end, four times in
a full year of arrears (section 2.1); the 1,000 is not the re-admission charge; the
concessions do not stack and the employee discount wins; the 5% requires payment by
30 April; transport is fined because it sits inside the total; transport runs 11 months
with June excluded; and the ledger's billed-versus-outstanding disagreement is sidestepped
entirely by loading collections and normal fees only.
