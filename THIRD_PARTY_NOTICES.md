# Third-party notices and unresolved provenance

This is a source-distribution index, not a replacement license or a redistribution
clearance. The project's [MIT license](LICENSE) does not relicense third-party
components, fonts, media or datasets. The [F2-09 inventory and review procedure](docs/50-engineering/license-provenance.md)
records exact inputs, evidence limits and unresolved rights.

## Browser components already retained in source

| Component | Declared version/license | Preserved upstream text |
| --- | --- | --- |
| Vue | 3.5.44 / MIT | [LICENSE](enterprise-agent/app/static/vendor/vue-3.5.44/LICENSE) |
| Marked | 18.1.1 / MIT | [LICENSE](enterprise-agent/app/static/vendor/marked-18.1.1/LICENSE) |
| DOMPurify | 3.4.17 / Apache-2.0 OR MPL-2.0 | [Apache text](enterprise-agent/app/static/vendor/dompurify-3.4.17/LICENSE), [MPL text](enterprise-agent/app/static/vendor/dompurify-3.4.17/LICENSE-MPL) |

Preserve these files and copyright/license headers with the corresponding distributions.
The exact upstream tarball URLs, integrity values and local file hashes are recorded in
the [vendor manifest](enterprise-agent/app/static/vendor/manifest.json). DOMPurify's
vendored bundle additionally contains a regenerator-runtime MIT attribution to Facebook;
that embedded notice is preserved. Its complete bundled-component license-text review
remains pending. No dual-license election or complete notice audit is asserted here.

## Python, OS, optional profiles and externally supplied services

The [machine-readable inventory](enterprise-agent/deploy/license-inventory.json) records
all 98 pinned production Python distributions, including publisher-declared license
expressions/classifiers and exact-release metadata sources. These declarations are not
a verified Linux wheel or native-library bill of materials. Preserve installed upstream
license/NOTICE files and review the actual final distribution before redistribution.
In particular, review LGPL declarations for psycopg/psycopg-pool, MPL declarations
including certifi/orjson/tqdm, dual licenses, and native components bundled in wheels.
This index does not determine compliance obligations or license compatibility.

Development/evaluation/ML/IdP requirements, Docker/service images and CI tools are
recorded separately as declarations. Unresolved closures, OS copyright files, bundled
libraries, model weights and provider terms do not inherit the production inventory's
coverage. The remote model profile does not distribute model weights.

## Verified upstream notice additions — 2026-11-07

This is a scoped evidence and notice update, not a blanket rights decision. The controlled
457 source statuses and their verifier are unchanged.

- **Twelve generated tooling files:** their instruction bodies match the official
  OpenSpec 1.7.0 package under its actual Codex/Kimi renderer rules. The npm archive's
  published integrity was verified without executing package code. Retain
  [the complete upstream MIT text](third_party/licenses/openspec/OpenSpec-1.7.0-MIT.txt)
  and its Copyright 2024 OpenSpec Contributors attribution.
  [Exact local/package/template mappings](third_party/licenses/openspec/provenance.json)
  distinguish this source match from project-wide authorship or distribution acceptance.
- **89 presentation font files:** six JetBrains Mono and 83 Noto Serif SC files match
  byte-for-byte the official Google Fonts distribution URLs recorded in the
  [verified source map](third_party/licenses/fonts/verified-source-map.json).
  Their [original copyright notices](third_party/licenses/fonts/NOTICE.md) and full
  [JetBrains OFL](third_party/licenses/fonts/JetBrainsMono-OFL.txt) /
  [Noto Serif OFL](third_party/licenses/fonts/NotoSerifSC-OFL.txt) are retained.
  Copy those notices with the font files in any separate website/export; repository
  retention alone does not prove an export contains them.
- **128 other fonts:** [conditional OFL applicability, version and comparison evidence](third_party/licenses/fonts/unresolved-source-map.json)
  remains separate. Full OFL texts and original notices are now retained for these groups.
  OFL permits modifications/subsetting under its conditions; byte differences are not
  a redistribution prohibition. Historical acquisition chains remain incompletely
  reconstructed, particularly Manrope 4.504. No exact Manrope release verification or
  blanket clearance is claimed. No source is replaced or relicensed.

The OFL conditions include notice retention, restrictions on selling fonts alone and
reserved names for modified fonts, and continued OFL licensing of font derivatives.
The upstream full texts control. These font licenses do not relicense application code
or documents created using the fonts.

## Unconfirmed fonts, media and sample data

The remaining font lineage questions, screenshots, documentation illustrations/research
material, seed SQL, evaluation corpus and embedded fixtures still need scoped author or
upstream provenance evidence. The additions above do not clear those records. Keep their
pending records visible. Do not infer a
license from a font family, filename, synthetic label, screenshot appearance or Git author.
The inventory does not authorize public distribution of unresolved assets.
