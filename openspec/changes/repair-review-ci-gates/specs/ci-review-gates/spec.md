# CI review gates

## Requirement: Safe record identity
Every CI matrix job supplies a unique record ID accepted by the existing restricted alphabet. Unsafe paths remain rejected.

## Requirement: Evidence-bound secret findings
Source-manifest digests may be classified only after exact recomputation against independently identified Git blobs. Unverified values, wrong paths, altered hashes and real secrets remain findings. Full event history and final tracked-tree coverage remain mandatory.

## Requirement: Honest publication state
Every result identifies its exact commit and actual executed scope. No merge, deployment or release approval follows automatically from a green job.
