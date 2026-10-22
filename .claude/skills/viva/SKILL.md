---
name: viva
description: Understanding gate at the end of each milestone. Ilia must pass before the milestone closes.
disable-model-invocation: true
argument-hint: "M<n> [grade]"
arguments: [milestone, mode]
---
Milestone: $milestone. Mode: $mode (empty means write questions).

If mode is empty:
1. Ask the interviewer agent for 5 questions on milestone $milestone.
2. Write them to viva/$milestone.md under "## Round 1", each followed by an empty
   "Answer:" line.
3. Tell Ilia the file is ready, then end the turn. Do not answer, hint, or discuss the
   questions. Ilia answers in the file himself, without AI help.

If mode is "grade":
1. Pass the questions and Ilia's answers from viva/$milestone.md to the interviewer agent
   and ask it to grade them.
2. Append the grades under each answer.
3. For each fail: explain the concept in plain words, with the relevant file and line,
   then add one new question on the same concept under "## Round N+1" and end the turn.
4. When every question in the latest round passes, write "All passed" at the end of the
   file and tell Ilia he can mark $milestone closed in SPEC.md. Do not mark it yourself.
