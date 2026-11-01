# Prior study: corporate catalysts on the S&P 500 (2016-2026)

Before this desk existed, the same discipline was applied by hand to one multi-agent design: news and SEC
filings, a triage of catalysts, market context, an analyst, and a core-plus-satellite portfolio. It was
evaluated step by step, with a pre-registration frozen before each step and amendments dated when the plan
changed. The data came from licensed vendors and is not part of this repository; only aggregate results
are reported here. Porting the code to the desk is spec 0016.

## Setup

- **Universe:** S&P 500 members at each date (point in time), 2016-01 to 2026-06.
- **Events:** 91,800 dated 8-K filings, earnings releases and insider transactions. EDGAR acceptance
  times are converted from UTC to New York before an event is assigned to a session.
- **Outcome:** cumulative return over 21 sessions after the event, relative to the sector.
- **Statistics:** block bootstrap over 42-session calendar blocks, because 21-session windows overlap.
  Benjamini-Hochberg across tests.
- **Windows:** design 2016-2021, holdout 2022-2025, reserve 2026.

## Results

| Step | Question | Result |
|---|---|---|
| 1 | Are the event timestamps right? | Yes: reaction on the event day 3.6 times a normal day; the day before, 1.06 times |
| 2 | Does a triage by 8-K item find events that move prices? | Yes, in magnitude, not direction: catalysts move prices 1.52 times more than noise, mostly earnings (item 2.02) |
| 3 | Does market context (trend, volume, insiders) add direction? | No: 0 of 6 interactions significant; post-event drift about zero |
| 4 | Does a combined catalyst score rank stocks? | No: rank IC of the score 0.002, below its best part. Only the size of insider purchases carried signal (rank IC 0.065, p = 0.005) |
| 5 | Does a catalyst satellite improve the core portfolio? | No: the pre-registered net-alpha filter blocked every trade (expected 8 bp against 24 bp of costs). Without the filter (exploratory, not pre-registered), the satellite would have cost about 2.4 percentage points a year |

## What it taught the design of this desk

- The most valuable component was a deterministic risk rule that refused to trade an edge smaller than
  its costs. That became attack A3 and the rule that verdicts come from code.
- Magnitude is easier to predict than direction. A system that only reports "significant" results would
  have found something in step 2 and lost money in step 5.
- Insider purchase size was the one lead. It is a new pre-registered thesis with new data, not a
  re-test on data already seen, because the 2026 window was seen when step 5 was published.
- Every step was cheap to run and expensive to interpret. Automating the interpretation, and measuring
  how often that interpretation is wrong, is what this repository does.
