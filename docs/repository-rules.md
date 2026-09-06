# Repository rules

Nidavelir treats `main` as a protected integration branch.

## Required rules for `main`

Configure a GitHub repository ruleset targeting the default branch with the following policy:

- require a pull request before merging;
- require at least one approval when collaborators are added;
- dismiss stale approvals when new commits are pushed;
- require conversation resolution before merging;
- require status check `CI / required`;
- require branches to be up to date before merging;
- block force pushes;
- block branch deletion;
- apply the ruleset to administrators as well, unless an explicit emergency bypass actor is intentionally configured.

## Why one required CI gate?

The workflow exposes multiple component jobs (`Core`, `Web`, `Worker`, `Compose`) and one stable aggregate job named `CI / required`.

Branch protection should require only `CI / required`. That job depends on every component gate and fails when any of them fails. Internal CI jobs can therefore evolve without constantly editing repository rules.

## Merge policy

Prefer squash merges for normal feature and maintenance pull requests. Keep PRs scoped to one issue or a tightly-related unit of work.

Direct pushes to `main` are not part of the normal development workflow.
