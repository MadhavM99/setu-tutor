# Telugu speakers learning Hindi (L1 = Telugu, L2 = Hindi)

Same format as `../l1-hi_l2-te/rules.json`: `rules.json` (about 10 rules to start), `tests_v0.jsonl`.
Planted mistakes are Telugu-speaker mistakes in Hindi, e.g. gender on the verb/adjective, क्या omitted, है dropped,
ने dropped or misused, मुझे used for possession. Every rule starts as `draft_unverified` and needs a native Hindi check.
Nothing else in the code changes: the checker, leak filter and state read the rules from this folder.
