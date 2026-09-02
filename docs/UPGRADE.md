# Upgrade policy

Resolve an official Apache Superset release tag to its exact Git commit and multi-platform image digest. Verify the linux/amd64 manifest, package version, and embedded source label before updating the runtime lock and build manifest together.

Build and scan the derived image in CI. Promote only the same protected source and digest through test, staging, production, and main.
