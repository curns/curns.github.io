#!/bin/zsh

set -euo pipefail

cd -- "$(dirname -- "$0")"

export BUNDLE_USER_HOME="$PWD/.bundle-home"
export BUNDLE_PATH="vendor/bundle"

bundle check >/dev/null 2>&1 || bundle install
bundle exec jekyll serve --host 127.0.0.1 --port 4000
