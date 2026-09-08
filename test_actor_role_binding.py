import hashlib
from pathlib import Path
import unittest

from bridge import process_coordination, validate_coordination_command


class ActorRoleBindingTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            'repository': 'fixture/repo',
            'trusted_coordination_principals': [
                {'actor': 'alice', 'roles': ['Technical Planner']},
                {'actor': 'bob', 'roles': ['Reviewer']},
            ],
            'trusted_coordination_actors': [],
            'trusted_coordination_roles': [],
            'coordination_authority_ref': 'ADR-007',
        }
        self.command = {
            'schema_version': 1, 'command_id': 'cmd-001', 'action': 'revise',
            'repository': 'fixture/repo', 'wi_path': 'docs/work-items/WI-001-test.md',
            'wi_blob': '2' * 40, 'base_sha': '3' * 40, 'attempt_id': '4' * 32,
            'task_id': '11111111-1111-4111-8111-111111111111', 'checkout': 'unused',
            'work_branch': 'codex/test', 'pr_number': 7, 'expected_pr_head': '3' * 40,
            'feedback_ref': 'https://github.com/fixture/repo/pull/7#pullrequestreview-101',
            'feedback_sha256': '0' * 64, 'feedback': 'bounded feedback', 'issuer_actor': 'alice',
            'active_role': 'Technical Planner', 'authority_ref': 'ADR-007',
            'created_at': '2026-09-08T01:00:00+00:00',
        }

    def test_authorized_pair_succeeds_but_cross_pair_and_forged_role_fail(self):
        self.command['feedback_sha256'] = hashlib.sha256(b'bounded feedback').hexdigest()
        self.assertIs(validate_coordination_command(self.config, 'cmd-001', self.command), self.command)
        for actor, role in [('alice', 'Reviewer'), ('bob', 'Technical Planner'), ('alice', 'Product Owner')]:
            changed = dict(self.command, issuer_actor=actor, active_role=role)
            with self.subTest(actor=actor, role=role), self.assertRaisesRegex(RuntimeError, 'actor-role pair'):
                validate_coordination_command(self.config, 'cmd-001', changed)

    def test_legacy_single_principal_migrates_and_legacy_ambiguous_config_fails(self):
        self.command['feedback_sha256'] = hashlib.sha256(b'bounded feedback').hexdigest()
        legacy = dict(self.config, trusted_coordination_principals=None,
                      trusted_coordination_actors=['alice'],
                      trusted_coordination_roles=['Technical Planner'])
        self.assertIs(validate_coordination_command(legacy, 'cmd-001', self.command), self.command)
        ambiguous = dict(legacy, trusted_coordination_actors=['alice', 'bob'],
                         trusted_coordination_roles=['Technical Planner', 'Reviewer'])
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'):
            validate_coordination_command(ambiguous, 'cmd-001', self.command)

    def test_disabled_coordination_remains_compatible(self):
        with self.assertRaisesRegex(RuntimeError, 'disabled'):
            process_coordination(dict(self.config, coordination_ref=''), Path('.'), None, 'cmd-001')


if __name__ == '__main__':
    unittest.main()
