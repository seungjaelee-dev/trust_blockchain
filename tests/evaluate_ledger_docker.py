"""Local Docker integration verification; no uploaded Solidity is executed."""
import argparse, json, subprocess, sys, time
from pathlib import Path
from jsonschema import Draft202012Validator
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tests'))
from test_ledger_operations import EXPECTED, DIRECTORY
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image', default='trust404-track1:ledger-review')
parser.add_argument('--output', default='ledger-integration')
parser.add_argument('--reporting-baseline', type=Path)
args = parser.parse_args()
out = root / 'results' / args.output
inputs = out / 'inputs'
inputs.mkdir(parents=True, exist_ok=True)
expected = {}
for prefix, folder, labels in [
    ('public_', root/'reference/public', {'P1_StandardToken.sol':'BENIGN', 'P2_HiddenMint.sol':'MALICIOUS','P3_Honeypot.sol':'MALICIOUS','P4_CappedMint.sol':'BENIGN','P5_DelegatecallBackdoor.sol':'MALICIOUS'}),
    ('expanded_', root/'tests/fixtures/variants/expanded', {n:v['verdict'] for n,v in json.loads((root/'tests/fixtures/variants/expanded/expected.json').read_text()).items()}),
    ('ledger_', DIRECTORY, EXPECTED)]:
    for name, verdict in labels.items():
        (inputs/(prefix+name)).write_bytes((folder/name).read_bytes())
        expected[prefix+name] = verdict
(inputs/'broken.sol').write_text('pragma solidity ^0.8.20; contract Broken { this is invalid }')
expected['broken.sol']='UNCERTAIN'
start=time.monotonic()
cmd=['docker','run','--rm','--network','none','--cpus','2','--memory','4g','--memory-swap','4g','--mount',f'type=bind,source={inputs},target=/input,readonly',args.image]
run=subprocess.run(cmd,capture_output=True,text=True,timeout=590)
(out/'output.json').write_text(run.stdout)
(out/'stderr.log').write_text(run.stderr)
assert run.returncode == 0, run.stderr
actual=json.loads(run.stdout)
Draft202012Validator(json.loads((root/'reference/schema.json').read_text(encoding='utf-8-sig'))).validate(actual)
assert len(actual)==len(expected)
assert {x['file'] for x in actual} == set(expected)
for x in actual:
    assert x['verdict']==expected[x['file']], x
    for e in x['evidence']:
        assert 1<=e['line']<=len((inputs/x['file']).read_text().splitlines()), x
assert 'PermissionError' not in run.stderr
summary={'image':args.image,'elapsed_seconds':round(time.monotonic()-start,3),'input_count':len(expected),'matched':len(actual),'network':'none','cpus':2,'memory':'4g','schema':'passed','invalid_source':'UNCERTAIN','missing':0,'permission_error':False}
if args.reporting_baseline:
    from test_reporting import ReportingTests
    checker = ReportingTests()
    for item in actual:
        checker.assert_links(item)
    before = json.loads(args.reporting_baseline.read_text(encoding='utf-8'))
    assert {x['file']:x['verdict'] for x in actual} == {x['file']:x['verdict'] for x in before}
    summary.update(verdicts_unchanged=True, reason_evidence_links='passed', duplicate_evidence=0)
(out/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))

