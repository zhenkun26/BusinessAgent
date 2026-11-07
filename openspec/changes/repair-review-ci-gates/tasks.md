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

## Dependency advisory remediation (plan before implementation)

Run 42363479117 passed both Python versions and Gitleaks controls but pip-audit
reported msgpack 1.2.1 (CVE-2026-114613) and setuptools 83.0.0
(GHSA-xmj3-9gf7-h52w). Upgrade only these existing dependencies to the reviewed
fixed versions 1.2.3 and 84.1.0 using official PyPI metadata and binary-wheel
digests. Reconcile the production pins, hash lock, build metadata and publisher
inventory/declarations without changing package scope, rights status or exemptions.
Create a new retained isolated Python environment; preserve every existing
environment and fixture. Validate package selection, dependency compatibility and
offline integrity before parent-owned full checks, independent review and CI.

- [x] Update the two fixed versions and their exact official metadata/wheel bindings.
- [x] Verify isolated runtime selection and relevant build/inventory checks.
- [ ] Reconcile current sources and complete full, security and remote CI checks.


Dependency repair evidence is retained in
enterprise-agent/eval/results/ci-dependency-repair-20261107. Exact PyPI response
bytes, URLs and SHA256 digests bind the two release records; downloaded Linux
cp313/msgpack and local macOS/universal wheels match official digests. This new
capture does not claim to reproduce historical metadata digests after mutable
publisher/advisory metadata changed. Build inputs verify all 98 packages; license
inventory integrity passes with all 457 source rights still pending. A new retained
Python 3.13 environment excludes both old distribution roots, resolves each new
distribution exactly once, imports from the new wheel directories, and satisfies
all active production dependency requirements. Msgpack roundtrip passes.
The first metadata-update command used system Python 3.9 and stopped on missing
tomllib; the existing isolated Python 3.13 completed inventory reconciliation.
An initial build-check invocation omitted its required root argument; the corrected
read-only invocation passed. Neither attempt deleted files or changed gates.
Full-suite and remote audit/image validation remain parent-owned next steps.

## Debian image advisory remediation (plan before implementation)

Run 42364507658 passed both Python jobs, dependency audit, image build and installed
inventory/identity checks. Trivy found four HIGH Debian records: apt/libapt-pkg6.0
CVE-2026-109518 and openssl/libssl3 CVE-2026-84782. Verify official advisory and
fixed-version availability in a newer immutable signed Debian snapshot. Prefer
retaining the existing Python base digest and Python package scope while explicitly
installing only the affected fixed system versions. Preserve signed APT verification,
hash-bound inputs and vulnerability gates; no new exemption. Retain official metadata
and validate the build/license bindings locally without running APT or Docker.
Actual installation, dependency imports and image scanning remain remote CI evidence.

- [x] Verify official snapshot evidence and exact fixed package availability.
- [x] Update the minimal reproducible recipe/snapshot and integrity bindings.
- [ ] Complete local integrity review, full checks and remote image verification.


Retained evidence: enterprise-agent/eval/results/ci-debian-repair-20261107.
Official Debian tracker pages identify both fixed source versions. The frozen
20261107T000000Z Release hashes bind the amd64 Packages.xz byte hashes/sizes, and
the security index binds all four downloaded .deb byte hashes/sizes. Both indexes
and all archives are retained; nothing was installed locally. GPG was unavailable
locally, so this is a digest-chain check, not a claimed local signature verification.
APT's existing Signed-By/keyring checks remain enabled for the actual remote build.

The recipe installs apt/libapt-pkg6.0 2.6.2 and openssl/libssl3 3.0.22-1~deb12u2,
then requires four matching dpkg-query results before continuing. The immutable
Python base digest and all 98 Python package records remain unchanged. Existing
unversioned runtime-library requests still resolve against the new frozen snapshot;
their actual versions and any dependency changes must be compared in the resulting
CI inventory. This is not a claim that only four final OS package versions change.
Build-input verification and license integrity pass locally (98 packages, 457 pending
source rights). Full suite, signed APT installation, actual image/import checks and
Trivy remain parent-owned remote verification; no exemption or trust relaxation.
