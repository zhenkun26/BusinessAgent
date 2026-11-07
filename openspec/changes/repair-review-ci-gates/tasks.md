# Tasks

- [x] Correct matrix record naming and test accepted/rejected values.
- [x] Design and independently review narrowly verified manifest-hash handling.
- [x] Run isolated-candidate full-history and exact-tree scans with negative controls.
- [x] Reconcile inventories and source counts without lowering gates.
- [x] Run focused and complete offline checks and independent review.
- [ ] Record final committed scanning, commit and push to PR #8.
- [ ] Inspect CI for the exact new head; address failures or report blockers.

## Fresh-checkout pytest evidence directory repair (plan before implementation)

CI run 42362838030 reports Python CHILD_FAILED. The ignored eval/results directory
is absent from tracked checkout contents, while the pytest child creates a nested
run directory without creating its parents. Reproduce this missing-parent condition
using retained synthetic fixtures, then create missing parents while preserving
exclusive creation of the UUID run directory. Test both fresh parents and an existing
run-directory collision, retaining all prior bytes. Do not weaken test/receipt gates,
alter application behavior, or publish raw failure output. Diagnostic-summary expansion
is deferred pending evidence that this narrow repair is insufficient.

- [x] Fix retained pytest directory creation for a fresh checkout.
- [x] Verify missing-parent creation and collision rejection with retained fixtures.
- [ ] Reconcile hashes/counts, rerun complete checks and review the next remote CI.

Focused result: the original mkdir operation raises FileNotFoundError when parent
directories are missing. The updated helper creates those parents and still rejects
an existing run directory without changing its evidence. All 40 offline-verification
tests pass under Python 3.13 with zero diagnostic-guard denials; fixtures are retained
under eval/results/ci-fresh-parent-regression-0b9aecfba7e24c029a29d0451dd6f30f.
This focused result does not certify complete-suite or remote CI success.
