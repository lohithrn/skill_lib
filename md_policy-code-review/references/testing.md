# Tests and the human review documents

Answers: *what shape does a test take here, what may be faked, and what documentation must exist
alongside?*

Rules **19** (tests teach public usage), **20** (the two human review documents), plus the
**Testing Expectations** operational rules. The premise: a test for a public library is an executable
usage example first and a regression net second.

---

### 19. Tests must teach public usage

Tests for public library wrappers should read like executable usage examples.

Prefer one focused test file per public scenario or provider combination.

Each such test class should:

- Use `setUp` to create temporary folders and external-test guards.
- Use `tearDown` to clean temporary folders.
- Keep the first line of each actual test method as object creation.
- Provide a dedicated method that creates the configuration object.
- Call the public methods that agents or callers are expected to use.
- Avoid generic import-only tests unless package import itself is the feature.
- Put reusable fake backends, metadata helpers, and setup helpers in `tests/utility`.
- Keep fake dependencies visibly injected through the public dependency-injection path.
- Use an isolated workspace-root folder such as `.generated-test-artifacts` for generated test
  artifacts.
- Never let test setup or teardown delete the real library artifact output root, such as `.generated`,
  because developers may use that folder for expensive generated artifacts.
- Assert category namespacing when artifacts are written by category.
- Treat category as a required namespace passed separately from input/output roots.
- Do not bake category into test input/output root paths.

Integration tests that call paid or credentialed services should be real but guarded in setup by
explicit environment variables or dependency checks.

**Two of those bullets are hard, not stylistic.** Teardown must never delete the real artifact output
root — a developer can lose hours of expensive generated artifacts to one test run. And category is a
*separate* argument, never baked into a root path, because a test that bakes it cannot detect the
namespacing bug it exists to catch.

**Consequence of faking through anything but the public DI path:** the test proves an internal seam
works and says nothing about whether a caller can wire the fake at all.

---

### 20. Human review documents

For reusable library repositories, maintain project-specific human review documents outside the
`documentation/skills` folder. Skills must stay generic; do not place library-specific class names,
package names, diagrams, or test instructions inside a generic coding skill.

Recommended project documentation files:

- `documentation/human_test_methods.md`: teaches humans how to evaluate the test strategy, generated
  artifacts, provider guards, and manual verification steps.
- `documentation/human_read_code.md`: teaches humans how to read that specific codebase, including
  important entry points, interfaces, package structure, and low-level design.

The code-reading file should:

- Stay as one file.
- Stay under **250 lines**.
- Include a visual class/interface/package diagram when the codebase has meaningful layers.
- Focus on the most important reading path and contracts.
- Avoid exhaustive details that humans cannot hold in working memory.

Update these documents when public constructors, interfaces, artifact paths, namespace behavior, or
test strategy changes.

**Note the 250-line cap applies to this document too** — the same number as the source-file cap in
`references/laws.md`, for the same reason: past it, nobody reads to the end.

---

## Testing expectations

Prefer tests that prove public behavior through real constructors and public methods.

Use fake implementations only at meaningful boundaries such as external clients, paid services,
network calls, file stores, or slow ML providers.

**Do not mock the class under test. Mock or fake its dependencies.** Mocking the subject means the
test asserts against the mock's configuration, so it passes whatever the subject does.

Keep both:

- Fast unit/scenario tests that run by default.
- Guarded integration tests for paid, credentialed, or heavyweight providers.

The rest of the day-to-day rules — error types, logging, async boundaries, type annotations, import
order, commit hygiene — are in `references/operational-rules.md`.
