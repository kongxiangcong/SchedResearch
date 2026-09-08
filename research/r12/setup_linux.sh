#!/usr/bin/env bash
# Build the contract-pinned tt-npe inside the dedicated SchedResearch-R12 WSL distro.
# This script never removes a checkout, install tree, distribution, or build directory.
set -Eeuo pipefail

task_root=/opt/schedresearch-r12
windows_r12=/mnt/d/dsh-proj/SchedResarch/research/r12
artifact_root="$windows_r12/artifacts"
source_origin="$windows_r12/deps/tt-npe"
npe_source="$task_root/tt-npe"
npe_build="$task_root/build/tt-npe"
npe_install="$task_root/install/tt-npe"
npe_venv="$task_root/venv-npe"
expected_commit=341da058f0b65e51d3643fb36f011a0784abedff
run_id=$(date -u +%Y%m%dT%H%M%SZ)
phase_records="$artifact_root/logs/npe_phases_$run_id.jsonl"
mkdir -p "$task_root" "$artifact_root/logs" "$artifact_root/npe"
export DEBIAN_FRONTEND=noninteractive
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUTF8=1

finish() {
    local result_code=$?
    trap - EXIT
    python3 "$windows_r12/write_npe_environment.py" \
        --task-root "$task_root" --artifact-root "$artifact_root" \
        --phase-records "$phase_records" --run-id "$run_id" \
        --exit-code "$result_code" --expected-commit "$expected_commit"
    exit "$result_code"
}
trap finish EXIT

run_phase() {
    local phase=$1
    shift
    local logfile="$artifact_root/logs/npe_${phase}_${run_id}.log"
    local result_code=0
    "$@" 2>&1 | tee "$logfile" || result_code=$?
    python3 - "$phase_records" "$phase" "$logfile" "$result_code" <<'PY'
import json, pathlib, sys
record = {"phase": sys.argv[2], "log": sys.argv[3], "exit_code": int(sys.argv[4])}
with pathlib.Path(sys.argv[1]).open("a", encoding="utf-8") as output:
    output.write(json.dumps(record) + "\n")
PY
    return "$result_code"
}

check_and_clone() {
    local observed
    observed=$(git -c safe.directory="$source_origin" -C "$source_origin" rev-parse HEAD)
    test "$observed" = "$expected_commit"
    if [[ ! -e "$npe_source" ]]; then
        git clone --no-hardlinks "$source_origin" "$npe_source"
    fi
    test -d "$npe_source/.git"
    observed=$(git -C "$npe_source" rev-parse HEAD)
    test "$observed" = "$expected_commit"
    test -z "$(git -C "$npe_source" status --porcelain)"
    printf 'Pinned tt-npe source: %s\n' "$observed"
}

run_phase apt_update apt-get -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 -o Acquire::Retries=2 update
run_phase apt_install apt-get -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 -o Acquire::Retries=2 install -y --no-install-recommends \
    gcc-12 g++-12 cmake ninja-build python3-dev python3-venv \
    git ca-certificates curl libc++-dev libc++abi-dev pkg-config zlib1g-dev
run_phase clone check_and_clone
run_phase venv python3 -m venv "$npe_venv"
run_phase python_install "$npe_venv/bin/python" -m pip install --timeout 20 --retries 2 -r "$windows_r12/requirements-npe.lock.txt"
run_phase python_check "$npe_venv/bin/python" -m pip check
run_phase python_freeze "$npe_venv/bin/python" -m pip freeze --all
run_phase source_archives python3 "$windows_r12/install_npe_sources.py"

run_phase configure cmake -S "$npe_source" -B "$npe_build" -G Ninja \
    -C "$task_root/download_sources/sources.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=/usr/bin/gcc-12 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++-12 \
    -DENABLE_LIBCXX=OFF \
    -DENABLE_CCACHE=OFF \
    -DPython_EXECUTABLE="$npe_venv/bin/python" \
    -DCMAKE_INSTALL_PREFIX="$npe_install"
run_phase build cmake --build "$npe_build" --parallel 4
run_phase install cmake --install "$npe_build"

export PATH="$npe_venv/bin:$npe_install/bin:$PATH"
export PYTHONPATH="$npe_install/lib:$npe_install/bin"
export LD_LIBRARY_PATH="$npe_install/lib"
# Preserve the upstream example input. All generated output goes to this run's folder.
smoke_dir="$task_root/runs/$run_id"
mkdir -p "$smoke_dir"
cd "$smoke_dir"
checks_failed=0
run_phase example_api "$npe_venv/bin/python" "$windows_r12/npe_smoke.py" \
    --source "$npe_source" --install "$npe_install" \
    --output "$artifact_root/npe/example_api_$run_id.json" || checks_failed=1
if run_phase example_cli "$npe_venv/bin/python" "$npe_install/bin/tt_npe.py" \
    -w "$npe_source/tt_npe/workload/example_wl.json"; then
    printf 'Official example CLI exited successfully.\n'
else
    checks_failed=1
    printf 'Official example CLI failed; retaining the error and testing the documented Python API separately.\n'
fi
cd "$npe_source/tt_npe"
run_phase cpp_tests "$npe_build/tt_npe/tt_npe_ut" \
    "--gtest_output=xml:$artifact_root/npe/cpp_tests_$run_id.xml" || checks_failed=1
run_phase python_tests "$npe_venv/bin/python" -m pytest -q \
    "--junitxml=$artifact_root/npe/python_tests_$run_id.xml" \
    -o "cache_dir=$task_root/pytest-cache" || checks_failed=1
run_phase source_status git -C "$npe_source" status --porcelain
test -z "$(git -C "$npe_source" status --porcelain)"
printf 'tt-npe build and official tests completed; these are estimator results, not hardware cycle truth.\n'
exit "$checks_failed"
