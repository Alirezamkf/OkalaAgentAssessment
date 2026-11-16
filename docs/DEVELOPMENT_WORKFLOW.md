# Okala Development Workflow — Three-Developer Collaboration

**Project:** Okala Examination System
**Team model:** Three developers working in one shared repository
**Task-management system:** GitHub Issues
**Related documents:** `docs/SPEC.md` and `AGENTS.md`

---

## 1. Purpose

This document defines how the three developers coordinate implementation in the shared Okala repository.

The team uses the existing GitHub Issues as its implementation work breakdown. Alireza has defined 198 development tasks. Developers work on individual issues, respecting their dependencies, acceptance criteria, and agreed responsibilities.

This document does not create a parallel task register or replace GitHub Issues.

The purpose of the workflow is to:

- Avoid duplicate implementation.
- Make task ownership visible.
- Respect dependencies.
- Reduce conflicts in shared code and database migrations.
- Keep changes reviewable.
- Integrate work safely.
- Ensure all developers and coding agents follow the same product baseline.

## 2. Shared project references

All developers should use the same committed versions of:

| Reference | Purpose |
|---|---|
| `docs/SPEC.md` | Product scope, functional requirements, architecture, and technical constraints |
| `AGENTS.md` | Mandatory instructions for Codex and other coding agents |
| `docs/DEVELOPMENT_WORKFLOW.md` | Team collaboration and Git workflow |
| GitHub Issues | Individual implementation tasks, dependencies, and acceptance criteria |
| Pull Requests | Review and integration of code changes |

If a GitHub issue appears to conflict with the specification, the team must resolve the conflict before implementing the disputed behavior.

## 3. Task ownership and coordination

### 3.1 Before claiming or starting an issue

A developer should:

1. Read the complete issue description.
2. Read its acceptance criteria.
3. Check linked and prerequisite issues.
4. Inspect whether the required functionality already exists.
5. Check whether another developer is working on the same issue or shared files.
6. Agree task ownership through the team's GitHub process.
7. Confirm that the task is sufficiently clear to begin.

An issue being open does not prove that no implementation exists. Inspect the code and related pull requests first.

### 3.2 Ownership

- Each active issue should have a clearly understood owner.
- Do not independently begin the same task as another developer.
- Do not change another developer's branch or work without coordination.
- If work must be handed over, communicate the current state, branch, changed files, tests, and remaining work.
- Do not assume permanent module ownership unless the team explicitly agrees to it.

### 3.3 Blocked tasks

If a task is blocked:

- Identify the exact missing prerequisite or decision.
- Link the relevant issue or pull request where possible.
- Explain what work is blocked and why.
- Notify the relevant developer/team member.
- Do not implement an unapproved substitute simply to make progress.

## 4. Before implementation

For each issue, the responsible developer should verify:

- [ ] The complete GitHub issue and acceptance criteria have been read.
- [ ] `docs/SPEC.md` has been reviewed for relevant requirements.
- [ ] `AGENTS.md` has been reviewed if a coding agent will be used.
- [ ] Dependencies and related issues have been checked.
- [ ] Existing implementation and tests have been inspected.
- [ ] The current branch and working tree have been checked.
- [ ] Potential shared-file conflicts have been discussed.
- [ ] The task scope is understood.

The developer remains responsible for the code produced by a coding agent and must review the diff and test results.

## 5. Branching and Git workflow

### 5.1 Branch naming

Use a branch associated with the GitHub issue. A practical convention is:

`<developer-or-identifier>/issue-<number>-<short-description>`

Example:

`maedeh/issue-170-attempt-details-service`

The identifier should follow the team's agreed convention. It is not an assignment mechanism.

### 5.2 Base branch

Use the repository's agreed integration/base branch. Inspect the repository and team instructions rather than assuming a `develop` branch exists.

The team should agree which branch is used as the base for new work and pull requests.

### 5.3 Branch safety

- Do not implement unrelated work directly on the integration branch.
- Check `git status` before switching branches, pulling, rebasing, or applying changes.
- Preserve uncommitted changes.
- Do not use destructive commands such as `git reset --hard` or `git clean` to resolve routine problems.
- Do not force-push shared branches.
- Do not delete another developer's branch.
- Keep the feature branch reasonably current with the agreed base branch.
- If branch history or ownership is unclear, coordinate before rewriting it.

### 5.4 Commits and pushes

Follow the team's repository permissions and review policy. Commit messages should describe the change and, where practical, reference the issue number.

Do not commit secrets, local environment files, recordings, real candidate information, generated artifacts that should not be versioned, or unrelated changes.

## 6. Dependencies and parallel work

The 198 issues may depend on one another. Before starting an issue, inspect its dependency relationships and verify that required interfaces or prerequisite behavior are available.

Parallel development is appropriate when tasks have sufficiently clear boundaries and compatible interfaces.

Coordinate before concurrent changes to shared resources, including:

- SQLAlchemy models.
- Alembic migration history.
- Shared Pydantic schemas.
- API contracts.
- Authentication and authorization dependencies.
- Core configuration.
- Shared services.
- Common frontend components.
- Shared types and API clients.

When two tasks require the same shared resource, the developers should agree on the interface and sequencing before both implementations diverge.

Do not assume that separate issue numbers imply independent code changes.

## 7. Database and migration coordination

Database changes can affect multiple tasks and developers. For every schema-related issue:

1. Inspect current models and migration history.
2. Identify related issues that touch the same entities or relationships.
3. Discuss shared model or migration changes with affected developers.
4. Implement schema changes through Alembic migrations.
5. Avoid duplicate or conflicting migration revisions.
6. Test migration upgrade behavior in an appropriate development/test database.
7. Check that application code and migration state remain consistent.
8. Include migration details in the pull request.

Do not manually modify a shared or production database schema. Do not run destructive database commands against an unknown or shared environment.

When multiple developers need migrations at the same time, coordinate migration creation and ordering rather than independently generating conflicting revisions.

## 8. Using Codex and other coding agents

A developer may use Codex or another compatible coding agent to implement an assigned issue.

The agent must follow the repository's `AGENTS.md`.

The normal agent workflow is:

1. Provide the assigned GitHub issue number or full issue content.
2. Require the agent to read `docs/SPEC.md` and `AGENTS.md`.
3. Require repository and dependency inspection before coding.
4. Ask it to implement only the assigned issue.
5. Require relevant tests and verification.
6. Review the complete diff.
7. Confirm that no unrelated files or behavior changed.
8. Understand the implementation before approving or merging it.

The developer—not the coding agent—remains accountable for correctness, security, maintainability, and acceptance criteria.

Agents must not silently redefine requirements, claim unrun tests passed, or perform unauthorized commits, pushes, merges, GitHub changes, or destructive operations.

## 9. Pull request process

A pull request should be associated with its GitHub issue and include:

- A clear title referencing the issue.
- A short summary of the implementation.
- The acceptance criteria addressed.
- Important design or implementation decisions.
- Tests executed and their actual results.
- Migration details, if applicable.
- API/schema changes, if applicable.
- Screenshots or recordings for relevant UI changes, without exposing real candidate data.
- Known limitations or unresolved questions.

The pull request should remain focused on the assigned issue. If additional work is discovered, create or reference the appropriate issue rather than silently expanding the pull request.

## 10. Code review

Reviewers should check:

- Does the change satisfy the issue's acceptance criteria?
- Is it consistent with `docs/SPEC.md`?
- Does it follow existing architecture and conventions?
- Does it introduce duplicate logic or unnecessary abstractions?
- Are authorization and candidate-data boundaries respected?
- Are answer keys and restricted data protected?
- Are recording files and references private?
- Are migrations safe and consistent?
- Are tests meaningful and sufficient for the change?
- Does the diff contain unrelated or generated files?
- Are failures and limitations reported honestly?

Reviewers should request changes when important acceptance criteria, security requirements, or data-integrity guarantees are not met.

## 11. Integration and conflict resolution

When updating a feature branch or resolving a conflict:

1. Check the working tree and preserve local changes.
2. Identify the conflicting files and commits.
3. Understand both implementations before choosing a resolution.
4. Contact the other developer if the conflict affects their work or a shared contract.
5. Resolve the conflict without blindly choosing one side.
6. Review the resulting diff.
7. Run relevant tests again.
8. Update the pull request with the resolution.

Never overwrite another developer's work simply to make a merge succeed.

If a conflict reveals incompatible API, model, or business-rule assumptions, resolve the design with the team before proceeding.

## 12. Task completion

An issue should be considered ready for closure when:

- Its acceptance criteria are satisfied.
- The implementation is within scope.
- Relevant tests have been run and results reported.
- Required migrations and documentation are included.
- Security and authorization have been considered.
- The pull request has passed the team's review process.
- The change has been integrated according to repository policy.
- Known limitations and unresolved questions are documented.
- The GitHub issue is updated according to the team's process.

A successful application startup alone does not establish that a task is complete.

## 13. Specification and architecture changes

A developer or agent must not silently change product requirements or architectural principles.

For a proposed change:

1. Identify the existing requirement or decision.
2. Explain the proposed change and why it is needed.
3. Identify affected modules, data, APIs, and other GitHub issues.
4. Discuss the change with all affected developers and the appropriate project decision-maker.
5. Obtain agreement before treating it as approved.
6. Update `docs/SPEC.md` through a reviewed documentation change.
7. Review affected issues and implementation.
8. Communicate the decision to the team.

If a task cannot be implemented without resolving an open decision, raise the question before choosing a permanent behavior.

## 14. Communication

Developers should communicate promptly about:

- Starting or taking ownership of an issue.
- Blocked dependencies.
- Shared model, schema, or API changes.
- Breaking changes.
- Migration creation and ordering.
- Pull requests requiring review.
- Conflicts with the specification.
- Important test failures.
- Handoffs or changes in task ownership.

Keep issue and pull-request discussions sufficiently clear that another developer can understand the current state without reconstructing private conversations.

## 15. Shared Definition of Done

For each issue, confirm:

- The issue's acceptance criteria are met.
- The implementation follows the specification and repository conventions.
- Appropriate tests have been added or updated.
- Relevant tests have actually been run.
- Database migrations are included and tested when needed.
- Security, authorization, and privacy implications have been considered.
- No unrelated changes are included.
- Documentation is updated where applicable.
- Review is complete.
- Known limitations and deviations are recorded.
- GitHub issue and pull-request status reflect the actual state of the work.

---

## 16. Guiding principle

The three developers share one product specification, one repository, and one GitHub-based implementation work breakdown.

Work should be independently owned where practical, coordinated where shared resources are involved, reviewed before integration, and always consistent with the approved Okala requirements.
