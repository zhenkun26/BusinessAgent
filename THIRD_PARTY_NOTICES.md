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

## Unconfirmed fonts, media and sample data

The presentation's font binaries, screenshots, documentation illustrations/research
material, seed SQL, evaluation corpus and embedded fixtures have not received author or
upstream provenance confirmation. Keep their pending records visible. Do not infer a
license from a font family, filename, synthetic label, screenshot appearance or Git author.
The inventory does not authorize public distribution of unresolved assets.
