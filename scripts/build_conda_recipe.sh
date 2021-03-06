#!/bin/bash -ex
# Usage:
#
#    $ ./scripts/build_conda_recipe.sh v1.2.3
#    $ ./scripts/build_conda_recipe.sh v1.2.3 --python 3.4
#
if [[ $1 != v* ]]; then
    echo "Argument does not start with 'v'"
    exit 1
fi
./scripts/check_clean_repo_on_master.sh

echo ${1#v}>__conda_version__.txt
cleanup() {
    rm __conda_version__.txt
    exit
}
trap cleanup INT TERM EXIT

if [[ -d build/ ]]; then
    rm -r build/
fi
conda build ${@:2} ./conda-recipe/
