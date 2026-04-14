#!/usr/bin/env python3
"""
Setup wizard: interviews the user and generates search_criteria.md + ranking_criteria.md
Usage: python setup.py
"""

import subprocess
import sys
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"


def ask(question: str, required: bool = True, default: str = "") -> str:
    hint = f" [{default}]" if default else (" (optional — press Enter to skip)" if not required else "")
    while True:
        answer = input(f"\n{question}{hint}\n> ").strip()
        if not answer and default:
            return default
        if answer or not required:
            return answer
        print("  Required — please enter a value.")


def call_claude(prompt: str) -> str:
    """Send a prompt to Claude via claude --print, return stdout."""
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"\nClaude error:\n{result.stderr}")
        sys.exit(1)
    output = result.stdout.strip()
    # Strip code fences if Claude wrapped the output
    if output.startswith("```"):
        lines = output.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        output = "\n".join(lines[1:end])
    return output


def build_search_prompt(a: dict) -> str:
    return f"""Your response IS the file content. Do not use any tools. Do not describe what you will write. Do not ask for approval. Start your response directly with "# Search Criteria" and output nothing else.

Candidate profile:
- Trade/title: {a['trade']}
- Location: {a['location']}
- Willing to relocate: {a['relocate']}
- Willing to travel for extended projects: {a['travel']}

Fill in the template below based on the candidate profile.
For queries, include 2-4 relevant search terms for their trade.
For locations, use their city/state as the primary location.
Set radius based on willingness to travel/relocate (25-75 miles typical).

# Search Criteria

## Queries
Primary keywords (each runs as a separate Adzuna search):
- "[query 1]"
- "[query 2]"

Exclude terms (pre-filter results that contain these in the title):
- "[irrelevant role title 1]"

## Locations
- City: [city, state]
- Radius: [miles]

## Additional Locations (optional)
# - City: [City, State]
# - Radius: 75 miles

## API Parameters
- Results per query per location: 25
- Sort: date
- Salary floor (annual, optional — leave blank if flexible):

## Notes
# Run frequency is controlled by cron or manual trigger.
# All queries run every cycle. Dedup handles overlap.
"""


def build_rank_prompt(a: dict) -> str:
    return f"""Your response IS the file content. Do not use any tools. Do not describe what you will write. Do not ask for approval. Start your response directly with "# Ranking Criteria" and output nothing else.

Candidate profile:
- Trade/title: {a['trade']}
- License: {a['license']}
- Years experience: {a['years_exp']}
- Work type background: {a['work_type']}
- Current pay: ${a['current_pay']}/hr
- Minimum acceptable pay: ${a['min_pay']}/hr
- Willing to relocate: {a['relocate']}
- Willing to travel: {a['travel']}
- Hard dealbreakers: {a['dealbreakers'] or 'none specified'}
- Wants to change about current situation: {a['current_situation'] or 'not specified'}
- Extra context: {a['extra'] or 'none'}

Fill in the template below. Be specific and practical based on the candidate profile.
Order desirability weights by what matters most to this candidate.
Write "Notes for Claude" as 3-4 direct sentences — no fluff.

# Ranking Criteria

## Dealbreakers
Listings matching any of these are discarded entirely (not scored):
- [dealbreaker based on profile]

## Fit Criteria
These drive the fit_score (1–10): how well the candidate matches what the employer wants.

- License tier: [their license] — listings requiring higher tier = low fit
- Experience: [X] years [work type] background
- [add relevant experience notes]

## Desirability Criteria
These drive the desirability_score (1–10): how attractive this job is to the candidate.

Weights (higher = more important):
1. Pay — floor is $[min_pay]/hr. Below floor drops score significantly. No pay listed = uncertainty penalty.
2. [next most important factor]
3. [next]
4. [next]
5. [next]

## Current Situation
- Current role: [their trade]
- Current pay: ${a['current_pay']}/hr
- Work type: [their work type]
- What they want to change: {a['current_situation'] or 'not specified'}

## Geographic / Availability Notes
- Willing to relocate: {a['relocate']} — boost score if relocation assistance mentioned
- Willing to travel for extended projects: {a['travel']} — note duration if mentioned
- Remote: not applicable for this trade

## Notes for Claude
[3-4 direct sentences of practical judgment context based on the profile.]
"""


def main():
    print("=" * 60)
    print("  Job Search Setup")
    print("  Answer each question. Optional ones can be skipped.")
    print("=" * 60)

    a = {}
    a["trade"]            = ask("What is your trade or job title?")
    a["license"]          = ask("What license or certification do you hold?")
    a["years_exp"]        = ask("How many years of experience do you have?")
    a["work_type"]        = ask("What type of work do you do? (residential / commercial / industrial / mix)")
    a["current_pay"]      = ask("What is your current hourly pay rate? (just the number, e.g. 32)")
    a["min_pay"]          = ask("What is the minimum hourly rate you would accept?")
    a["location"]         = ask("What city and state are you in? (e.g. Lincoln, NE)")
    a["relocate"]         = ask("Are you willing to relocate for the right job?")
    a["travel"]           = ask("Are you willing to travel for extended projects?")
    a["dealbreakers"]     = ask("What would you absolutely NOT accept in a job?", required=False)
    a["current_situation"]= ask("What do you want to change about your current situation?", required=False)
    a["extra"]            = ask("Anything else important to know about what you're looking for?", required=False)

    print("\nGenerating search_criteria.md...")
    search_content = call_claude(build_search_prompt(a))
    search_path = CONFIG_DIR / "search_criteria.md"
    search_path.write_text(search_content, encoding="utf-8")
    print(f"  Written: {search_path}")

    print("Generating ranking_criteria.md...")
    rank_content = call_claude(build_rank_prompt(a))
    rank_path = CONFIG_DIR / "ranking_criteria.md"
    rank_path.write_text(rank_content, encoding="utf-8")
    print(f"  Written: {rank_path}")

    print("\n" + "=" * 60)
    print("  Done. Review your config files before running a search:")
    print(f"  {search_path}")
    print(f"  {rank_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
