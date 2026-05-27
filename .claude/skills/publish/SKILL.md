---
name: publish
description: Generate a publication draft for a specific platform from the HRRP research findings.
argument-hint: "[platform: linkedin-article | medium | ssrn | linkedin-post | fed-register | all]"
context: fork
agent: publisher
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Generate a publication draft for the platform specified in: $ARGUMENTS

Steps:
1. Read `HRRP_Analysis_v_1.docx` and `consolidated_findings.md` to ground the draft in the canonical research findings. Do not invent statistics.
2. Identify the requested platform from $ARGUMENTS. Accept: `linkedin-article`, `medium`, `ssrn`, `linkedin-post`, `fed-register`, or `all`.
3. Produce a PUBLICATION DRAFT block (or one per platform if `all`) with platform name, target and actual word counts, the full draft text, and the revision checklist.
4. Respect each platform's formatting conventions: lead, length, tone, audience, CTAs, citations, keywords.
5. Use author identity strings exactly: Jay Callery, GitHub jcal-2, LinkedIn www.linkedin.com/in/jay-callery-73820165/.
6. No em dashes anywhere. Use "correlates with" and "suggests" language only. Match hospital-list naming to platform context (intervention priority tiers for academic and regulatory, sales tiers for commercial).
7. When generating `all`, produce platforms in order: SSRN Abstract, LinkedIn Post, LinkedIn Article, Medium, Federal Register Comment.
