"""Actual lifecycle function tests with pure doubles; no external acceptance claim."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

SOURCE = Path(__file__).resolve().parents[1] / 'app/core/approval_lifecycle.py'

def functions(**extra):
    tree = ast.parse(SOURCE.read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                 and n.name in {'expire', 'settle', 'observe'}]
    scope = dict(Any=object, UNCLAIMED={'pending','approved_pending_reauth'},
        OUTCOMES={'executed','execution_unknown','execution_failed','compensated','compensation_failed'},
        OperationError=RuntimeError, text=lambda x:x,
        deadline=NS(verified=lambda row:True, payload=lambda row:row.prefill_payload),
        event=AsyncMock(), load_locked=AsyncMock())
    scope.update(extra)
    exec(compile(tree,str(SOURCE),'exec'),scope)
    return scope

class HumanHoldTests(IsolatedAsyncioTestCase):
    async def test_legacy_never_auto_expires(self):
        scope=functions(deadline=NS(verified=lambda row:False))
        for status in ('pending','approved_pending_reauth'):
            db=NS(execute=AsyncMock())
            self.assertFalse(await scope['expire'](db,NS(status=status)))
            db.execute.assert_not_awaited()

    async def test_later_success_never_releases_hold(self):
        scope=functions()
        for status in ('execution_unknown','execution_failed','compensation_failed','compensated'):
            db=NS(execute=AsyncMock())
            self.assertEqual(await scope['settle'](db,NS(status=status),'executed'),status)
            db.execute.assert_not_awaited()

    async def test_racing_hold_is_not_overwritten(self):
        scope=functions(load_locked=AsyncMock(return_value=NS(status='execution_unknown')))
        db=NS(execute=AsyncMock(return_value=NS(fetchone=lambda:None)))
        row=NS(status='executing',approval_id='a',execution_claim='c',requester_id='u')
        self.assertEqual(await scope['settle'](db,row,'executed'),'execution_unknown')
        self.assertIn("AND status = 'executing'",db.execute.call_args.args[0])
        self.assertIn('execution_deadline <= clock_timestamp()', db.execute.call_args.args[0])
        scope['event'].assert_not_awaited()

    async def observation(self, rows, calls):
        db=NS(execute=AsyncMock(return_value=NS(mappings=lambda:NS(all=lambda:rows))))
        row=NS(execution_id='e',prefill_payload={'tool_calls':calls})
        return await functions()['observe'](db,row,finished=True)

    def record(self, oid):
        call={'operation_id':oid,'tool':'send_email_internal','params':{},'target':{'provider':'mock'}}
        return dict(operation_id=oid,execution_id='e',intent=call,state='committed',receipt={'success':True}),call

    async def test_all_steps_need_receipts(self):
        r1,c1=self.record('1');r2,c2=self.record('2')
        self.assertEqual(await self.observation([r1],[c1,c2]),'execution_unknown')
        self.assertEqual(await self.observation([r1,r2],[c1,c2]),'executed')

    async def test_foreign_or_changed_receipts_rejected(self):
        r,c=self.record('1')
        r['execution_id']='foreign'
        self.assertEqual(await self.observation([r],[c]),'execution_unknown')
        r,c=self.record('1');r['intent']={**c,'params':{'changed':True}}
        self.assertEqual(await self.observation([r],[c]),'execution_unknown')

    async def test_duplicate_and_empty_plan_not_success(self):
        r,c=self.record('1')
        self.assertEqual(await self.observation([r,r],[c,c]),'execution_unknown')
        self.assertEqual(await self.observation([],[]),'execution_unknown')

    async def test_mock_failure_receipt_not_success(self):
        r,c=self.record('1');r['receipt']={'success':False}
        self.assertEqual(await self.observation([r],[c]),'execution_unknown')

    async def test_invalid_contract_not_observed_as_success(self):
        db=NS(execute=AsyncMock())
        scope=functions(deadline=NS(verified=lambda row:False))
        self.assertEqual(await scope['observe'](db,NS(execution_id='e')),'execution_unknown')
        db.execute.assert_not_awaited()

if __name__ == '__main__':
    import unittest
    unittest.main()
