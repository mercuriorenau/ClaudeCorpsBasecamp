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
- If WebFetch is blocked (403 Forbidden, an empty page, or an error), open the same page in the Chrome browser and read it there. Many official Colorado and federal sites block WebFetch but work fine in the browser. Only treat a page as unavailable after both have failed.
- WebFetch gives you a summary of the page, not its exact words. When you need a verbatim quote, read the page text in the browser.

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

But don't abstain when you have the proof. If you opened an official page, copied words that answer the question, and checked the period, answer it. Abstaining on a question an official source answers is also a failure: it leaves a family without information they need.

## Step 8: Get a second check
This step is pre-approved. Always do it, without asking anyone.

Before saving your final answers, send your answered (not abstained) questions to the `verifier` subagent (in batches, for example one batch per program) with the question, your answer, your source URL and your supporting quote. Then, for each result:
- `MATCH`: keep the answer.
- `MISMATCH`: research that question again. Answer only if you find and quote an official source that settles it; otherwise abstain.
- `NOT FOUND`: the verifier read the page and couldn't find support. Re-read the page yourself. If your quote really is on it and answers the question for the right period, keep the answer at `medium` confidence at most. If not, research again or abstain.
- `UNABLE TO CHECK`: the verifier couldn't open the page. That is a tool problem, not evidence against you. Keep the answer if your supporting quote was copied from that page when you opened it, and set confidence to `medium` at most.
