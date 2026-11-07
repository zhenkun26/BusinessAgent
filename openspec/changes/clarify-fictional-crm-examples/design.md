## Plan before implementation
Use 虚构示例企业 C00N and 虚构联系人 C00N, phone NOT-A-PHONE, email customer-c00n@example.invalid. Align the existing CRM task description and two current product-page references. Use fictional-demo-manager@company.internal for the internal seed recipient, explicitly labeled synthetic, preserving the existing mail classification boundary.

## Verification
Offline AST-based tests verify all eight fields and preserved order relationships without loading runtime integrations. Check current page and seed, and compare non-contact CRM data with the Git baseline. No sending, dialing or live acceptance.

## Seed compatibility
Refresh only schema_manifest.json demo_seed SHA for the new SQL bytes; managed migration hashes and versions stay unchanged. Existing demo-v1 markers with the old SHA fail closed on explicit reseeding (no replay or marker rewrite). Ordinary schema checks do not migrate or clear the seed marker. The existing bootstrap regression tests cover this boundary; no database operation is performed.
