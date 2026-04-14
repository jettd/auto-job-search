# Ranking Criteria
# Copy this file to ranking_criteria.md and fill in your values.
# This file is passed verbatim to Claude as scoring context — be specific and honest.

## Dealbreakers
Listings matching any of these are discarded entirely (not scored):
- Pay explicitly listed below $XX/hr with no per diem, mileage, or benefits that could compensate
- Requires [license tier] or higher as a hard requirement (not preferred)
- Requires more than X years experience as a minimum

## Fit Criteria
These drive the fit_score (1–10): how well the candidate matches what the employer wants.

- License tier: [describe candidate's license/certification level] — listings requiring [higher tier] = low fit; [matching tier] roles = high fit
- Experience: [X years, type of work] background
- [Preferred work environment, e.g. commercial/industrial over residential] — weight accordingly
- Listings that explicitly mention [desirable program, e.g. apprenticeship continuation] are a strong fit signal
- [Any other fit signals specific to the trade or candidate]

## Desirability Criteria
These drive the desirability_score (1–10): how attractive this job is to the candidate.

Weights (higher = more important):
1. Pay — floor is $XX/hr. Below floor drops score significantly. [Describe offsets, e.g. per diem, mileage] can offset base rate. No pay listed = apply a mild uncertainty penalty but do not discard.
2. [Second priority — e.g. stability, pay equity, benefits]
3. [Third priority — e.g. local vs. travel, schedule]
4. [Fourth priority — e.g. growth, advancement path]
5. [Fifth priority — e.g. sector preference, union status]

## Current Situation
- Current role: [Job title]
- Current pay: $XX/hr [plus any additional compensation]
- Work type: [Type and conditions of current work]
- What they want to change: [Specific pain points driving the search — be honest, this is what Claude uses to judge desirability]

## Geographic / Availability Notes
- Willing to relocate: [yes/no — if yes, note whether relocation assistance matters]
- Willing to travel: [yes/no — if yes, note what compensation makes travel acceptable]
- Remote: [applicable or not for this trade/role]

## Notes for Claude
[Free-form context that doesn't fit above. The more specific and honest, the better Claude's scoring will be. Good things to include: what the candidate is leaving behind and why, what would make them jump at an offer vs. pass, any nuance around pay or conditions that the structured fields above can't capture.]
