# Brick topQuadrant SHACL wrapper

## Installation

`brick-tq-shacl` vendors `pytqshacl` via the git submodule at
`brick_tq_shacl/_vendor/pytqshacl`. Installing this project from PyPI pulls in
the vendored bits automatically, so `pip install brick-tq-shacl` works without
any extra steps.

For development, clone with submodules or initialize them afterward:

```shell
git clone --recursive https://github.com/gtfierro/brick-tq-shacl.git
# or, if already cloned:
git submodule update --init --recursive
```

When you need a newer upstream `pytqshacl`, update the submodule and commit the
new pointer:

```shell
git submodule update --remote brick_tq_shacl/_vendor/pytqshacl
```

If you would rather use a locally installed upstream build instead of the
vendored copy, install it before importing this package and it will take
precedence:

```shell
pip install "pytqshacl[cli] @ git+https://github.com/gtfierro/pytqshacl@master"
```

## Contributing

1. Clone the repo **with** submodules (or run `git submodule update --init --recursive`
   after cloning) so the vendored `pytqshacl` sources are available for local
   development and packaging.
2. Run `uv sync` (or `uv sync --extra withjre` if you need the managed JRE) to
   install dependencies.
3. If your change requires updates to `pytqshacl`, run
   `git submodule update --remote brick_tq_shacl/_vendor/pytqshacl`, test, and
   commit the new submodule SHA along with your changes.
4. Before opening a PR, run the smoke scripts (`uv run python brick.py ...`,
   `uv run python s223.py`, etc.) and add any relevant validation output to the
   PR description per the repository guidelines.
