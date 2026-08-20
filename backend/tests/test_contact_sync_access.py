from __future__ import annotations

import ast
from pathlib import Path
import unittest


class ContactSyncAccessTests(unittest.TestCase):
    def test_contact_sync_access_checks_receive_database_session(self) -> None:
        source = Path(__file__).parents[1] / "app" / "api" / "esi.py"
        module = ast.parse(source.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        for name in ("preview_contact_sync", "apply_contact_sync"):
            calls = [
                node
                for node in ast.walk(functions[name])
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "require_token_access"
            ]
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(len(call.args) == 3 for call in calls))
            self.assertTrue(all(isinstance(call.args[2], ast.Name) and call.args[2].id == "db" for call in calls))

    def test_contact_apply_only_queues_the_worker(self) -> None:
        source = Path(__file__).parents[1] / "app" / "api" / "esi.py"
        module = ast.parse(source.read_text(encoding="utf-8"))
        apply_function = next(
            node
            for node in module.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "apply_contact_sync"
        )

        direct_contact_fetches = [
            node
            for node in ast.walk(apply_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "fetch_character_contacts"
        ]
        queued_tasks = [
            node
            for node in ast.walk(apply_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "schedule_contact_sync_task"
        ]

        self.assertEqual(direct_contact_fetches, [])
        self.assertEqual(len(queued_tasks), 1)


if __name__ == "__main__":
    unittest.main()
