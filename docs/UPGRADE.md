# Upgrade policy

Resolve an official Apache Superset release tag to its exact Git commit and multi-platform image digest. Verify the linux/amd64 manifest, package version, and embedded source label before updating the runtime lock and build manifest together.

Build and scan the derived image in CI. Promote only the same protected source and digest through test, staging, production, and main.

Before any later installation, verify the keyless signature, SLSA provenance,
and SBOM for the immutable release identity. Pull only that digest, then run
`scripts/verify_release_identity.sh IMAGE@sha256:DIGEST PROTECTED_SOURCE_SHA`.
The readback must prove the OCI source label, protected revision label,
repository digest, and non-root user all agree. A tag or a syntactically valid
but differently labeled digest is not an eligible upgrade.
