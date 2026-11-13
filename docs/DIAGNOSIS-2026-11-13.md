# Diagnosis, 13 November 2026: why two months produced no interview

The owner's report: no job, no interview, and "every agent just sends me their leads and
nothing has been applied". Eight agents each measured one angle from this repository; a
second agent re-derived every number with its own scripts; a final critic ranked the causes.
Nothing here comes from the live tracker, the SEEK account or a phone log, so every count of
submissions is a floor. Corrections made by the checkers are already applied below.

## 1. Two separate problems

**A. Applications were not being submitted** (28 September to 13 November).

| Measure | Number |
|---|---|
| Records written by the runners | 257 |
| Of those, ready to act on | 180 (62 SEEK packs, 59 employer-site packs, 59 prepared emails) |
| Emails actually sent | 2, both on 28 September |
| SEEK packs followed by a SEEK receipt | 2 |
| Employer-site packs followed by any receipt | 0 of 59 |
| Holds waiting on a fact from the owner | 77 |
| SEEK receipts between 9 October and 9 November | 0 |
| Ticks (of 111) that ended on exactly "two new records" | 63 |

**B. Applications that were submitted earlier did not convert.** The receipt list holds 142
applications from February to 20 October (70 in July, 21 in August, 35 in September, 7 in
October), and at least six more are known from other records. 27 rejections are recorded and
no interview. The list cannot say who pressed submit: some are credited to Jeremie, and 15 in
a row on 24 to 26 September arrived about two hours apart through the night.

## 2. Causes, in order of confidence

**High confidence (problem A)**

1. **No step in the loop submitted anything.** SEEK and employer-site applications were
   parked as `READY_JEREMIE_*` for a person who, the owner now says, is no longer involved.
   The runbook asked for records and a one-line count, and told the agent not to ask.
2. **Email sending was blocked by rules the agents wrote for themselves.** A "shared
   canonical journal lease" was required before any send and exists in no code on any branch;
   25 send attempts cite it. Then the only active runner had a draft-only mail tool, then a
   tracker write was a precondition while the tracker was full.
3. **The hand-off failed before the tracker did.** 64 of the 65 packs that expired unsubmitted
   were created while the tracker was still working, and sat there a median of 28 days.

**Medium confidence (problem A)**

4. **The tracker has refused every write since 17 October** (1,791,770 of an allowed
   1,800,000 bytes; the state is one document in one database row, and that row type cannot
   exceed 2 MB, so the limit could not simply be raised). 63 finds since then were saved only
   on one runner's machine.
5. **Many packs were not ready.** 48 of the 121 packs still said "Marc to confirm"; salary and
   notice were unanswered in almost every pack that needed them; `facts.json` had not changed
   in 46 days.
6. **The loop blocked itself.** 94 newer adverts were rejected as duplicates of packs nobody
   had submitted, and the loop did not run on about 23 of the 46 days.

**Medium confidence (problem B)**

7. **Targeting.** 53 to 55 of the 142 applications were plain Site, Project, Civil or Design
   Engineer titles with no entry-level word; 16 went to recruitment agencies; 14 were repeats
   to the same employer. Graduate programs are mostly closed to this profile (half of the
   saved graduate-program adverts require citizenship or permanent residency, and about a
   third carry a graduation window a 2019 degree misses). About 5 of the 142 were drafter
   titles and 2 were technician titles, the work his 2026 Advanced Diploma is for.
8. **The market for this profile is small.** Of 1,301 SEEK adverts read in full, 35% state a
   minimum of one year or more and most of the rest ask for experience in words; only 6.5%
   bar temporary visa holders. On a hand read, about 12 adverts a week nationally are clearly
   attainable (up to about 25 counting marginal ones) and 2 to 5 of them are in Victoria.
9. **A whole entry-level family was thrown away unread.** The title filter excluded the word
   "laboratory"; about a hundred construction materials testing, soil and geotechnical
   technician titles were discarded, many of them trainee or entry level.

**Low confidence (problem B): plausible, but the data cannot test it**

10. **What each application carried.** 195 of 197 drafted letters contained a sentence saying
    what he lacks and all 197 gave the visa end date; the resume was headed "Graduate Civil
    Engineer" for a 2019 degree and its timeline stopped at April 2022. But almost nothing
    drafted by the loop was sent, and the resume used for the July to September applications
    is not in the repo.
11. **Channel mix.** Nearly everything was a cold SEEK application with no follow-up. The only
    human replies on record came from two introductions by a family contact.
12. **Outcomes were barely watched.** Replies were swept from Gmail three times (7, 11 and 17
    October); calls, voicemail and SEEK messages were never checked.

What the data cannot do is separate targeting from documents from the profile itself: only 20
of the 142 applications have a recorded outcome. The plan therefore fixes all three and
measures replies by lane.

## 3. What was changed

See `automation/README.md` section 4 for the table. In short: a queue in the repo that named
runners submit from, with receipts as the only measure; drafter and technician lanes first;
standing answers from the owner in `facts.json`; three resume variants with his current
Australian job listed; shorter applications that do not volunteer limits; no quota of
records; a lock file in place of the lease; and a storage fix for the tracker on `main`.

## 4. What is still unknown

- The live tracker's state, and whether any pack was submitted without leaving a receipt.
- The state of the SEEK account: profile, stored resume, verification, visibility.
- Whether any employer phoned.
- Which lane will convert. "Drafter and technician first" rests on fit to the qualification
  and on what was never tried, not on outcomes: traineeships sometimes exclude degree
  holders, 12d appears in about a quarter of drafting adverts and is not among his tools, and
  the portfolio shows no Civil 3D output yet. Review after about 30 comparable applications.

## 5. Things only the owner can do

- Redraw two or three real drawing sheets with a title block, including one Civil 3D output,
  so drafting applications can attach proof.
- Ask the family contact who produced the only two replies for further introductions, and
  phone small civil contractors, land-development firms and testing laboratories directly.
- Check his phone and SEEK messages for missed contact from employers.
