#!/usr/bin/env bash

# use conda as python interpreter
CONDA_DIR="$(dirname "$(dirname "$(which conda)")")"
ENVS=("py37" "py38" "py39")
PY_EXES=""
for env in "${ENVS[@]}"; do
  exe="${CONDA_DIR}/envs/${env}/bin/python"
  if [[ -z "${PY_EXES}" ]]; then
    PY_EXES="${exe}"
  else
    PY_EXES="${PY_EXES}:${exe}"
  fi
done

set -e

tox --discover "${PY_EXES}"
