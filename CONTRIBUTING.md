# Contributing to Transist Workflows

External pull requests for public workflow examples, tests, and documentation
are welcome. Start with an issue or discussion for substantial designs. A
submission is reviewed by maintainers; acceptance is not guaranteed.

- Keep each example self-contained and avoid machine-specific paths.
- Document inputs, prerequisites, required capabilities, policy and trust needs,
  and the expected result. Never commit secrets, private keys, customer data,
  operational inputs, or generated run artifacts. Keep `private/` unpublished.
- Add or update deterministic, offline validation where practical. State the
  commands run and any skipped checks in the pull request.
- Keep prompts, helpers, skills and modules contained in their owning example.
  Modules use schema `transist.module.v1`; root plugin pins cover every reachable
  invocation. After publication, workflow and module releases can advance
  independently using SemVer, including prerelease and build metadata. Plugin
  dependencies use exact SemVer versions, not ranges or floating references;
  pin each reachable invocation to the selected plugin release. Schema identifiers
  remain unchanged. Published versioned payloads are immutable: release changed
  bytes under a new version and obtain a new signature for a signed package.
  Preserve previous bundles and homes for recovery. See
  [scripts/README.md](scripts/README.md) for validation. Do not use cross-example
  symlinks or traversal.
- Keep operational data in root managed documents outside the Git workspace.
  Delivery guards still reject stageable legacy `.transist/` and interaction files
  before generation and every all-changes commit. Managed documents need no Git
  exclusion. Do not edit target `.gitignore` or hide required context through
  agent `ignore_paths`; review source/OpenSpec deliverables normally.
- Preserve runtime-bound gate scopes and the complete reviewer ledger. Project
  review context without transport output or duplicated bodies; retain exact
  request IDs, locations and text. A post-gate fetch must merge pending pre-gate
  requests, not replace them. Exceeded bounds must fail rather than truncate.
- CLI agent calls use compact output, invocation-only history and explicit
  UTF-8 prompt/context limits. Apply only fields supported by that action;
  native model calls and Ollama do not accept CLI history settings. Offline
  graph checks do not establish compatibility with installed plugin schemas.
- Match fictional sample inputs to the declared schemas. Document all external
  effects, credential bindings, exact endpoint customization and failure cleanup.
- Run the unit tests, Python formatting/lint checks, runtime source validator,
  and publication gate described in [scripts/README.md](scripts/README.md).
   Automatic CI runs static checks only; execute tests locally as described in
   [validation](docs/validation.md). Never inject credentials into CI.
- Before recreating the repository, copy only the publication gate's explicit
  passing inclusion list into a new directory, initialize Git there, and rerun
  the same checks. Preserve the old checkout as the rollback source until review.
- Changes to runtime or CLI behavior belong in the separate
  [Transist source repository](https://github.com/transist-ai/transist) and
  follow its curated contribution policy.

## License and sign-off

Contributions are submitted under [Apache-2.0](LICENSE) with Developer
Certificate of Origin (DCO) sign-off. You must have the right to submit your
contribution under that license. Add `Signed-off-by:` to each commit using
`git commit -s`. See <https://developercertificate.org/>.
