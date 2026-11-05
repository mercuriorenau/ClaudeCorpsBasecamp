---
name: benefits-research
description: The step-by-step process for answering any question about government benefit rules (eligibility, income limits, benefit amounts, how to apply, deadlines, tax credits). Use it for every benefits question, together with colorado-programs, dates-and-periods and quote-then-answer.
---

# Benefits research process

A wrong answer can make a family skip a benefit they qualify for, or apply for one they don't. Accuracy matters more than speed. Follow these steps for every question.

## Step 1: Read the question like a rule
Before searching, write down exactly what is being asked:
- the program, and whether it is a Colorado rule or a federal rule
- the period it applies to (a year, a season, a tax year, or "current")
- who it is about (household size, adult, child, pregnant person, single filer)
- the unit (monthly or yearly, gross or net, dollars or % of the poverty level, years of age)

## Step 2: Find the controlling rule
Rules come in layers. Know which layer you are reading:
1. **Law**: a federal statute (U.S. Code) or Colorado statute (C.R.S.), or the Colorado Constitution.
2. **Regulation**: the federal regulations (eCFR) or Colorado's regulations (Code of Colorado Regulations).
3. **Agency guidance**: the agency's own pages, tables, notices and fact sheets.

For numbers that change every year (income limits, benefit amounts, tax credit amounts), the agency's current table or notice usually has the figure. For who qualifies and how a program works, the regulation is the most reliable source. If two layers disagree, the newer, more official one wins. Say so if you find a conflict.

## Step 3: Search official sources only
- Never answer a number, date or rule from memory, even if you think you know it. Search for it every time.
- Use the official sites listed in the colorado-programs skill. Other websites (news, blogs, law firms, benefit-finder sites, other states' agencies) may only help you find the official page. They are never the source.
- Search results show short previews. A preview is never a source. Open the page and read it.

## Step 4: Check that it is Colorado's rule
Many programs are federal but run by the state. Colorado can choose its own options inside the federal rules, so a federal default table may not be the Colorado answer. When the question is about Colorado, find what Colorado actually uses, on a Colorado page or a federal page that lists Colorado specifically.

## Step 5: Check the effective date
Every number has a start date. Follow the dates-and-periods skill. Never use a number without knowing what period it covers.

## Step 6: Quote, then answer
Follow the quote-then-answer skill. No quote, no answer.

## Step 7: Decide whether to abstain
Use the abstention format the task asks for (for example an `abstain` column set to true).
Abstain when:
- you can't find an official source that states the answer
- the question asks about the future (a value, decision or law not announced yet)
- the question needs facts about a specific person or family that you don't have
- official sources conflict and you can't tell which one is current

Abstaining is better than guessing. A guess written as a fact is the worst possible outcome.

## Step 8: Get a second check
Before saving your final answers, send your answered (not abstained) questions to the `verifier` subagent (in batches, for example one batch per program) with the question, your answer and your source URL. If the verifier says MISMATCH or NOT FOUND, research that question again. If you still can't confirm it, change it to an abstention.
