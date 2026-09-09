from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load(path):
    value = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise SystemExit(f'{path} must contain a YAML object')
    return value


workflow = load(ROOT / '.github' / 'workflows' / 'ci.yml')
if not isinstance(workflow.get('jobs'), dict) or not workflow['jobs']:
    raise SystemExit('CI workflow must define jobs')

static_job = workflow['jobs'].get('powershell-and-static')
if not isinstance(static_job, dict):
    raise SystemExit('CI workflow must define the static-check job')
static_steps = static_job.get('steps', [])
checkout = next((step for step in static_steps if step.get('uses', '').startswith('actions/checkout@')), None)
static_check = next((step for step in static_steps if step.get('name') == 'Check whitespace and credential patterns'), None)
if not checkout or checkout.get('with', {}).get('fetch-depth') != 0:
    raise SystemExit('Static checks must fetch the complete history for range validation')
if not static_check or 'ci/check_diff_range.py' not in static_check.get('run', ''):
    raise SystemExit('Static checks must use the deterministic complete-range validator')
for variable in ('CI_EVENT_NAME', 'CI_BEFORE_SHA', 'CI_PR_BASE_SHA', 'CI_HEAD_SHA'):
    if variable not in static_check.get('env', {}):
        raise SystemExit(f'Static checks must provide {variable}')

template = (ROOT / 'templates' / 'ready-dispatch.yml.template').read_text(encoding='utf-8')
replacements = {
    '__BASE_BRANCH__': 'main',
    '__WORK_ITEMS_PATH__': 'docs/work-items',
    '__WORKFLOW_PATH__': '.github/workflows/codex-ready-dispatch.yml',
    '__REPOSITORY__': 'fixture/repo',
    '__REPOSITORY_SLUG__': 'fixture-repo',
    '__RUNNER_LABEL__': 'fixture-dispatch',
    '__INVOKE_PATH__': 'C:/dispatch/invoke-dispatch.ps1',
    '__CONFIG_PATH__': 'C:/dispatch/config.json',
    '__EXPECTED_USER_CHECK__': '# no username check',
    '__ADDITIONAL_PATHS__': '',
}
for marker, replacement in replacements.items():
    template = template.replace(marker, replacement)
rendered = yaml.safe_load(template)
if not isinstance(rendered, dict) or not isinstance(rendered.get('jobs'), dict):
    raise SystemExit('Rendered dispatcher template must define jobs')
print('Workflow and rendered dispatcher template YAML: OK')
