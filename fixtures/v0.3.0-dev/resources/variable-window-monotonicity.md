# Variable-window monotonicity premise

This fixture is public, deterministic input for the Nana `v0.3.0-dev`
runtime slice. It is intentionally narrower than the later algorithm study.

For an array whose values are all non-negative, extending a window to the
right cannot decrease its sum. Removing the leftmost value cannot increase
the sum. A variable-length sliding window can rely on these two monotone
changes when it searches for a shortest window whose sum reaches a positive
target.

If negative values are admitted, those two monotone changes no longer hold.
The dev slice records that boundary and runs one already locked test. It does
not search for a counterexample, implement the replacement algorithm, run a
benchmark, or form a final Decision.
