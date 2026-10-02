# Preserved failed same-protocol comparison

This directory retains the first two complete 24-operator executions after relation-action separation but before observation normalization. The runs contained identical scientific keys and verdicts, but 27 `observations_json` fields for the parallel relation varied because they recorded which payload won a schedule-sensitive shared-state race. Those values were not part of the clause predicate and were therefore inappropriate as frozen scientific evidence.

The final protocol retains the failure, replaces exact race-winner payloads with schedule-invariant clause observations, adds a regression test, and regenerates both complete matrices. Rows here are never pooled with final evidence.
