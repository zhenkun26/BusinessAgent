## ADDED Requirements

### Requirement: Current CRM examples are explicitly fictional
Current CRM examples SHALL use fictional labels, non-dialable phone placeholders and example.invalid email addresses without changing customer IDs, order relationships or schemas. The internal demo-seed recipient SHALL use an explicitly fictional local part with the existing company.internal classification domain; production mail rules SHALL remain unchanged.

#### Scenario: Read current examples
- **WHEN** a reader inspects the eight mock customers, matching current product-page examples
- **THEN** the contact examples are clearly fictional and non-contactable
- **AND** historical records, UAT fixtures and C17 remain unchanged
