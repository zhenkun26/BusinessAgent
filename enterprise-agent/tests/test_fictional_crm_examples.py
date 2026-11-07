"""Offline contracts for current, explicitly fictional contact examples."""
import ast
import __future__
from pathlib import Path
import unittest
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def mock_data(name):
    tree = ast.parse((ROOT / 'enterprise-agent/app/tools/crm.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(name)


class FictionalCrmExamplesTests(unittest.TestCase):
    def test_customer_contact_placeholders(self):
        customers = mock_data('_MOCK_CUSTOMERS')
        self.assertEqual(set(customers), {f'C{i:03}' for i in range(1, 9)})
        for cid, customer in customers.items():
            self.assertEqual(customer['customer_id'], cid)
            self.assertEqual(customer['name'], f'虚构示例企业 {cid}')
            self.assertEqual(customer['contact'], f'虚构联系人 {cid}')
            self.assertEqual(customer['phone'], 'NOT-A-PHONE')
            self.assertEqual(customer['email'], f'customer-{cid.lower()}@example.invalid')

    def test_order_customer_relationships(self):
        orders = mock_data('_MOCK_ORDERS')
        expected = ['C001', 'C002', 'C005', 'C003', 'C001', 'C007', 'C004', 'C002']
        self.assertEqual(len(orders), 8)
        for i, cid in enumerate(expected, 1):
            order_id = f'ORD-2026-{i:03}'
            self.assertEqual(orders[order_id]['order_id'], order_id)
            self.assertEqual(orders[order_id]['customer_id'], cid)

    def test_current_demo_references(self):
        page = (ROOT / 'interview/产品介绍网页/index.html').read_text()
        self.assertIn('虚构示例企业 C001', page)
        self.assertIn('虚构联系人 C001', page)
        self.assertIn('customer-c001@example.invalid', page)
        seed = (ROOT / 'enterprise-agent/deploy/demo_seed.sql').read_text()
        self.assertIn('"to":["fictional-demo-manager@company.internal"]', seed)

        # Execute the real classification function without importing runtime providers.
        tree = ast.parse((ROOT / 'enterprise-agent/app/tools/mail.py').read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'has_external_recipient')
        namespace = {'Any': object}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'mail.py', 'exec', flags=__future__.annotations.compiler_flag), namespace)
        config = ModuleType('app.config')
        config.get_settings = lambda: SimpleNamespace(
            mail_tool_provider='mock', tool_provider='mock', tool_reference_profile='')
        with patch.dict(sys.modules, {'app.config': config}):
            classify = namespace['has_external_recipient']
            self.assertFalse(classify({'to': ['fictional-demo-manager@company.internal']}))
            self.assertTrue(classify({'to': ['customer-c001@example.invalid']}))
            self.assertTrue(classify({'to': ['fictional-demo-manager@company.internal'],
                                      'cc': ['customer-c001@example.invalid']}))
            self.assertTrue(classify({'to': ['employee@reference.invalid']}))
