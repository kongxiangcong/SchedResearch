"""Independent read-only audit of saved R7 executions; never calls hardware.

This checks evidence consistency and full saved compute output equality.
It cannot authenticate physical execution, copy output bytes not saved,
counter semantics, strong-static optimality, or a performance gate.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import datetime

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    report_path = ROOT / 'execution_receipt_audit.json'
    if report_path.exists():
        raise SystemExit('refuse to overwrite audit')
    report = {'audited_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'method': 'saved receipt, artifact hash, stage and saved-output consistency',
              'performance_gate_evaluated': False, 'devices_called': 0, 'records': [], 'errors': []}
    total = {'copy': 0, 'compute': 0}
    expected = (ROOT / 'sources/kernel_access/int8_fixture/expected_rowmajor_int32.bin').read_bytes()
    builds = json.loads((ROOT / 'sdk/build_receipt.json').read_text(encoding='utf-8'))
    builds = {item['name']: item for item in builds}
    for receipt_path in sorted((ROOT / 'evidence').glob('*/receipt.json')):
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        command = receipt['command']
        basename = Path(command[0]).name.lower()
        if basename not in ['copy_probe.exe', 'compute_probe.exe']:
            continue
        kind = basename.split('_')[0]
        item = {'receipt': str(receipt_path.relative_to(ROOT)), 'kind': kind,
                'receipt_sha256': sha(receipt_path), 'errors': []}
        errors = item['errors']
        if receipt['timed_out'] or receipt['returncode'] != 0:
            errors.append('timeout or nonzero exit: retained, not discarded')
        if not receipt['artifacts_unchanged']:
            errors.append('artifact drift during process')
        if sha(ROOT/'capture.py') != receipt['capture_sha256']:
            errors.append('capture implementation differs from receipt')
        if sha(ROOT/'experiment_plan.md') != receipt['plan_sha256']:
            errors.append('preregistration differs from receipt')
        before, after = receipt['artifact_sha256_before'], receipt['artifact_sha256_after']
        if before != after:
            errors.append('pre/post hashes differ')
        for name, digest in before.items():
            if sha(name) != digest:
                errors.append('current artifact differs: ' + name)
        for name, digest in receipt['raw_sha256'].items():
            if sha(receipt_path.parent / name) != digest:
                errors.append('raw hash mismatch: ' + name)
        if sha(command[0]) != builds[kind]['artifact_sha256']:
            errors.append('executed executable does not match audited build')
        if sha(builds[kind]['source']) != builds[kind]['source_sha256']:
            errors.append('current source does not match audited build')
        stdout = (receipt_path.parent/'stdout.bin').read_bytes().decode('utf-8', errors='replace')
        stderr = (receipt_path.parent/'stderr.bin').read_bytes().decode('utf-8', errors='replace')
        if re.search(r'\b(?:ERROR|FAILED|FAILURE)\b', stdout+'\n'+stderr, re.IGNORECASE):
            errors.append('error token in raw logs')
        stages = [json.loads(line) for line in stdout.splitlines() if line.startswith('{')]
        item['stage_sequence'] = [stage['stage'] for stage in stages]
        results = [stage for stage in stages if stage['stage'] == 'result']
        prelaunch = [stage for stage in stages if stage['stage'] == 'prelaunch_contract']
        completed = [stage for stage in stages if stage['stage'] == 'completed']
        requested = int(command[3])
        item['requested_repetitions'] = requested
        item['result_count'] = len(results)
        if len(results) != requested or len(completed) != 1 or len(prelaunch) != 1:
            errors.append('stage/repetition count mismatch')
        if sum(stage['stage'] == 'before_launch' for stage in stages) != requested:
            errors.append('before-launch count mismatch')
        item['host_launch_wait2_s'] = []
        item['host_launch_to_output_sync_s'] = []
        item['full_process_s'] = receipt['host_process_elapsed_s']
        for index, result in enumerate(results):
            if result['iteration'] != index or result['state'] != 4 or not result['numeric_pass'] or result['mismatches'] != 0:
                errors.append('result identity/state/numeric mismatch')
            launch = result['host_launch_wait2_s']
            sync = result['sync_from_device_s']
            continuous = result['launch_to_output_sync_s']
            if not all(math.isfinite(v) and v > 0 for v in [launch, sync, continuous]):
                errors.append('nonpositive/nonfinite elapsed')
            if continuous + 1e-9 < launch + sync:
                errors.append('continuous elapsed shorter than component windows')
            item['host_launch_wait2_s'].append(launch)
            item['host_launch_to_output_sync_s'].append(continuous)
            if kind == 'copy':
                if result['compared_words'] != 268435456 or not result['input_unchanged']:
                    errors.append('copy coverage/input mismatch')
                if result['output_sha256'] != prelaunch[0]['input_sha256']:
                    errors.append('copy hashes disagree')
            else:
                if result['compared_int32'] != 2048 or not result['inputs_unchanged_host_mapping']:
                    errors.append('compute coverage/input mismatch')
                output_path = Path(command[4]) / f'output_{index}.bin'
                if not output_path.is_absolute():
                    output_path = Path(receipt['cwd']) / output_path
                if output_path.read_bytes() != expected or sha(output_path) != result['output_sha256']:
                    errors.append('saved compute output not equal full oracle/hash')
            total[kind] += 1
        item['prelaunch_contract'] = prelaunch[0] if prelaunch else None
        report['records'].append(item)
        report['errors'].extend(f'{receipt_path.parent.name}: {error}' for error in errors)
    report['total_saved_results'] = total
    if any(count < 1 or count > 10 for count in total.values()):
        report['errors'].append('expected 1..10 saved results per kernel within preregistered cap')
    report['consistency_pass'] = not report['errors']
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'consistency_pass': report['consistency_pass'], 'total_saved_results': total,
                      'errors': report['errors']}, indent=2))
    raise SystemExit(0 if report['consistency_pass'] else 1)


if __name__ == '__main__':
    main()
