# Source-only publication

Publish authored source with all maintained versions and pins at `0.1.0`.
Preserve Apache-2.0 licensing and attribution. Do not distribute publisher-signed
workflow bundles, private inputs, generated homes, credentials or development Git
history. Historical documents are evidence, not current acceptance receipts.

## Prepare and review

1. Run `python3 -B scripts/check_public_snapshot.py --list`.
2. Export the approved inventory to a new absent directory outside the source:

   ```sh
   python3 -B scripts/export_public_snapshot.py --destination "$EXPORT" --init-git
   ```

3. Review every staged path/content/mode and the external inventory digest. The
   exporter creates no commit, tag or remote. Verify zero history and exact parity.
4. Run independent pinned Gitleaks and the approved narrowed [gate](validation.md)
   against the final documented export. Retain commands, exits, identities and logs
   outside the export. Any required check failure blocks publication.
5. Record installed/peer/authoring checks and the repeat Linux matrix as deferred,
   not passed. Preserve earlier failed evidence outside the public inventory.

## Publication checkpoint

The owner approved experimental source-only publication under the narrowed gate
on 2026-11-11; full installed acceptance remains deferred. Record the exact
path/digest, required results, approved public author/committer/DCO identity and
remote operations. Initial commit message:
`Initial public release of Transist Workflows 0.1.0`.

Keep an all-ref private backup and archive. Create a fresh private repository with
one signed-off root commit, require successful static CI, clone and verify parity,
then verify committed contents and modes equal the tested export. Under the explicit
waiver, no repeated full native gate is required. After required checks and parity
pass, make it public and publish the annotated `v0.1.0` source-only release with
experimental limits. Full installed acceptance is not claimed.
Keep rollback evidence until the replacement checkout has been independently
verified. Never force-push private development history into the public repository.
