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
