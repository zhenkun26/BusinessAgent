# Enforce the dependency audit result

The unit test workflow pipes the dependency scanner through tee. With the
runner's default shell the step receives the output writer's exit status.
A scan may therefore fail without blocking the subsequent image build.

Make the scanner the last command and retain its report as a workflow artifact.
This restores the existing security-operations specification.

A fresh scan of the production requirements returned 23 advisory rows across
five packages, including a duplicate certifi advisory. Update the affected
requirements and the matching development dependency floors. Preserve the
existing exemption policy.
