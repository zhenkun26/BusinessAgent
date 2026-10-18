"""C16 source-execution tests; transport/database are injected, not live acceptance."""
from __future__ import annotations
import ast
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from enum import Enum
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
from urllib.parse import urlsplit, parse_qs
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_request_context.py'))
load, module, extract = (BASE[k] for k in ('load', 'module', 'extract'))


class AnalysisTests(BASE['RequestContextTests']):
    def setUp(self):
        super().setUp()
        self.settings = NS(tool_provider='mock', crm_tool_provider='', tool_reference_profile='business-reference-v1',
            tool_reference_run_id='00000000-0000-4000-8000-000000000001',
            tool_reference_principal='ref', crm_api_base='http://reference-crm:8080/api/v1',
            crm_api_token='SYNTHETIC_SERVICE_TOKEN')
        self.identity = NS(username='A', role='salesperson', department='dept_sales', is_active=True)
        self.db_failure = False
        self.requests = []
        self.transform = None
        self.orders = [self.order('O1', 10), self.order('O2', 20)]
        self.customers = [dict(customer_id='C001', name='Synthetic', level='A', version=1)]
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.config': module('app.config', get_settings=lambda: self.settings),
            'sqlalchemy': module('sqlalchemy', text=lambda x:x),
            'pydantic': module('pydantic', BaseModel=object, Field=lambda **kw: None),
            'app.security.redaction': module('app.security.redaction', redact_value=lambda v, **kw:v),
            'app.tools.http_adapter': module('app.tools.http_adapter', call_external_api=self.http),
            'app.core.database': module('app.core.database', get_session_factory=lambda:self.session),
        }))
        tree = ast.parse((ROOT / 'app/security/rbac.py').read_text())
        nodes = [n for n in tree.body if getattr(n, 'name', None) in {
            'AgentRole', 'resolve_active_user', 'can_use_tool'} or
            isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ROLE_TOOLS' for t in n.targets)]
        ns = dict(Enum=Enum, Any=object, User=lambda **kw:NS(**kw), HTTPException=Exception,
                  logger=self.log)
        exec('from __future__ import annotations\n' + '\n'.join(ast.unparse(n) for n in nodes), ns)
        self.roles = ns['AgentRole']
        self.stack.enter_context(patch.dict(sys.modules, {'app.security.rbac':module(
            'app.security.rbac', **{k:ns[k] for k in ('AgentRole','resolve_active_user','can_use_tool')})}))
        ops = load('c16_ops','app/core/tool_operations.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.core.tool_operations':ops}))
        self.ref = load('c16_reference','app/tools/reference.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.tools.reference':self.ref}))
        tree = ast.parse((ROOT/'app/tools/base.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='BaseTool')
        method = next(n for n in cls.body if getattr(n, 'name', None)=='_effective_provider')
        ns = {}
        exec(ast.unparse(method), ns)
        base = type('BaseTool', (), {'provider_override':None, 'provider_config_attr':None,
                                    '_effective_provider':ns['_effective_provider']})
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.tools.base':module('app.tools.base', BaseTool=base,
                ToolCategory=NS(QUERY='query',ACTION='action'), ToolResult=lambda *a,**k:
                NS(**dict(zip(('success','tool_name','output'), a)),**k)),
        }))
        self.crm = load('c16_crm','app/tools/crm.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.tools.crm':self.crm}))
        self.data = load('c16_data','app/tools/analysis_data.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.tools.analysis_data':self.data}))
        self.analysis = load('c16_analysis','app/agents/analysis.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.agents.analysis':self.analysis}))

    def order(self, oid, amount, **kw):
        return dict(order_id=oid, customer_id='C001', amount_minor=amount, currency='CNY',
                    status='completed', version=1, created_at='2026-01-15', **kw)

    @asynccontextmanager
    async def session(self):
        yield self

    async def execute(self, sql, params):
        self.assertIn('WHERE user_id = :uid', sql)
        if self.db_failure: raise RuntimeError('PRIVATE_DB_SECRET')
        return NS(fetchone=lambda:self.identity if params['uid']=='user-a' else None)

    async def http(self, method, url, **kw):
        self.requests.append((method,url,deepcopy(kw)))
        self.assertEqual(method, 'GET')
        self.assertEqual(kw['api_token'],'SYNTHETIC_SERVICE_TOKEN')
        self.assertEqual(kw['extra_headers']['X-Reference-Run-Id'],self.settings.tool_reference_run_id)
        self.assertEqual(kw['max_retries'],2)
        self.assertEqual(kw['timeout_seconds'],5)
        kw['meta'].update(status=200, profile='business-reference-v1')
        path = urlsplit(url).path
        query = parse_qs(urlsplit(url).query)
        if '/analysis/' not in path:
            row=next(o for o in self.orders if o['order_id']==path.rsplit('/',1)[1])
            return True, {'order':deepcopy(row)}, None
        kind = path.rsplit('/',1)[1]
        records = deepcopy(self.orders if kind=='orders' else self.customers)
        start=query.get('start_date',[None])[0]; end=query.get('end_date',[None])[0]
        if kind=='orders' and start: records=[r for r in records if start<=r['created_at']<=end]
        offset=int(query.get('cursor',['c0'])[0][1:])
        data={'schema':'crm-analysis-v1','run_id':self.settings.tool_reference_run_id,
              'snapshot_id':query.get('snapshot_id',['S1'])[0], 'as_of':'2026-10-17T12:00:00Z',
              'range':{'start_date':start,'end_date':end}, 'items':records[offset:offset+100],
              'total':len(records),'next_cursor':'c'+str(offset+100) if offset+100<len(records) else None}
        if self.transform: self.transform(data,kind,offset,kw['meta'])
        return True,data,None

    def reader(self, role='salesperson'):
        self.identity.role=role
        return self.data.AnalysisReader('user-a',self.roles(role),'dept_sales')

    async def run_agent(self, query='统计订单', role='salesperson'):
        self.identity.role=role
        return await self.analysis.AnalysisAgent(self.roles(role),'dept_sales','user-a').run(query)

    async def test_mock_is_explicit_and_never_http(self):
        result=await self.run_agent()
        self.assertTrue(result.success)
        self.assertIn('Mock 内置样例',result.output['answer'])
        self.assertFalse(self.requests)
        self.assertEqual(result.output['data']['totals_by_currency']['CNY']['order_count'],8)

    async def test_global_http_and_override_follow_query_provider(self):
        self.settings.tool_provider='http'
        self.assertEqual((await self.reader().read())['provenance']['provider'],'http')
        self.settings.crm_tool_provider='mock'; self.requests.clear()
        self.assertEqual((await self.reader().read())['provenance']['provider'],'mock')
        self.assertFalse(self.requests)

    async def test_http_changed_records_match_single_query_and_totals(self):
        self.settings.crm_tool_provider='http'
        result=await self.run_agent()
        self.assertEqual(result.output['data']['totals_by_currency']['CNY']['order_amount_minor'],30)
        self.orders[0]['amount_minor']=71
        single=await self.ref.query(self.crm.QueryOrderTool(),{'order_id':'O1'}, {})
        result=await self.run_agent()
        self.assertEqual(single.output['order']['amount_minor'],71)
        self.assertEqual(result.output['data']['totals_by_currency']['CNY']['order_amount_minor'],91)
        self.assertIn('0.91',result.output['answer'])

    async def test_finance_never_reads_customer_directory(self):
        self.settings.crm_tool_provider='http'
        result=await self.run_agent(role='finance')
        self.assertTrue(result.success)
        self.assertFalse(any('/customers' in u for _,u,_ in self.requests))
        self.assertIsNone(result.output['data']['rows'][0]['name'])
        self.settings.crm_tool_provider='mock'
        with patch.object(self.crm,'get_all_customers',side_effect=AssertionError):
            self.assertTrue((await self.run_agent(role='finance')).success)

    async def test_denied_role_never_reads_or_models(self):
        self.settings.crm_tool_provider='http'
        result=await self.run_agent(role='customer_service')
        self.assertEqual(result.error,'ANALYSIS_AUTHORIZATION_DENIED')
        self.assertFalse(self.requests)
        self.primary.assert_not_called()

    async def test_inactive_missing_and_database_failure_fail_closed(self):
        for fault in ('inactive','missing','database'):
            self.identity.is_active=fault!='inactive'; self.db_failure=fault=='database'
            reader=self.reader()
            if fault=='missing':reader.user_id=None
            with self.assertRaises(self.data.AnalysisDataError):await reader.read()
        self.assertFalse(self.requests)

    async def test_stale_role_and_department_denied(self):
        reader=self.reader();self.identity.role='admin'
        with self.assertRaises(self.data.AnalysisDataError):await reader.read()
        self.identity.role='salesperson';self.identity.department='dept_finance'
        with self.assertRaises(self.data.AnalysisDataError):await reader.read()

    async def test_revocation_after_page_prevents_partial_output(self):
        self.settings.crm_tool_provider='http'
        self.transform=lambda *args:setattr(self.identity,'is_active',False)
        result=await self.run_agent()
        self.assertFalse(result.success);self.assertNotIn('data',result.output)

    async def test_two_pages_and_customers_share_snapshot(self):
        self.settings.crm_tool_provider='http'
        self.orders=[self.order('O'+str(i),i) for i in range(101)]
        result=await self.reader().read()
        self.assertEqual(len(result['orders']),101)
        self.assertEqual(len(self.requests),3)
        for _,url,_ in self.requests[1:]:self.assertIn('snapshot_id=S1',url)

    async def test_page_failure_never_falls_back_to_mock(self):
        self.settings.crm_tool_provider='http'
        self.orders=[self.order('O'+str(i),i) for i in range(101)]
        self.transform=lambda d,k,o,m:m.update(status=503) if o else None
        with patch.object(self.crm,'get_all_orders',side_effect=AssertionError):
            result=await self.run_agent()
        self.assertFalse(result.success);self.assertNotIn('data',result.output)

    async def test_changing_snapshot_rejected(self):
        self.settings.crm_tool_provider='http'
        self.orders=[self.order('O'+str(i),i) for i in range(101)]
        self.transform=lambda d,k,o,m:d.update(snapshot_id='S2') if o else None
        with self.assertRaises(self.data.AnalysisDataError):await self.reader().read()

    async def test_duplicate_rows_rejected(self):
        self.settings.crm_tool_provider='http';self.orders.append(deepcopy(self.orders[0]))
        with self.assertRaises(self.data.AnalysisDataError):await self.reader().read()

    async def test_page_totals_cursors_run_schema_and_range_rejected(self):
        self.settings.crm_tool_provider='http'
        for field,value in [('total',True),('total',5001),('total',3),('next_cursor','https://evil'),
                            ('run_id','wrong'),('schema','wrong'),('range',{}),('as_of','no')]:
            with self.subTest(field=field,value=value):
                self.transform=lambda d,k,o,m:d.update({field:value})
                with self.assertRaises(self.data.AnalysisDataError):await self.reader().read()

    async def test_repeated_cursor_rejected(self):
        self.settings.crm_tool_provider='http'
        self.orders=[self.order('O'+str(i),i) for i in range(201)]
        self.transform=lambda d,k,o,m:d.update(next_cursor='c100') if o else None
        with self.assertRaises(self.data.AnalysisDataError):await self.reader().read()

    async def test_bad_order_fields_never_become_zero(self):
        self.settings.crm_tool_provider='http'
        for key,value in [('amount_minor',True),('amount_minor',.1),('amount_minor',-1),
                          ('amount_minor',10**15),('currency','cny'),('status','bad'),
                          ('version',True),('created_at','2026-02-30'),('customer_id','../x')]:
            with self.subTest(key=key):
                self.orders=[self.order('O1',10)];self.orders[0][key]=value
                result=await self.run_agent()
                self.assertFalse(result.success);self.assertNotIn('data',result.output)

    async def test_missing_extra_and_malformed_fields_rejected(self):
        self.settings.crm_tool_provider='http'
        for mutate in (lambda r:r.pop('amount_minor'),lambda r:r.update(secret='x')):
            self.orders=[self.order('O1',10)];mutate(self.orders[0])
            with self.assertRaises(self.data.AnalysisDataError):await self.reader().read()

    async def test_missing_customer_reference_rejected(self):
        self.settings.crm_tool_provider='http';self.customers=[]
        with self.assertRaises(self.data.AnalysisDataError):await self.reader().read()

    async def test_unknown_provider_and_missing_reference_config_do_not_fallback(self):
        for provider,profile in [('other','business-reference-v1'),('http','')]:
            self.settings.crm_tool_provider=provider;self.settings.tool_reference_profile=profile
            self.assertFalse((await self.run_agent()).success)
        self.assertFalse(self.requests)

    async def test_empty_is_explicit_no_replan(self):
        self.settings.crm_tool_provider='http';self.orders=[]
        result=await self.run_agent()
        self.assertTrue(result.success);self.assertEqual(result.output['stage'],'analysis_empty')
        self.assertFalse(result.needs_replan);self.assertIn('没有可分析',result.output['answer'])

    async def test_date_range_is_inclusive_and_provenance_recorded(self):
        self.settings.crm_tool_provider='http'
        result=await self.run_agent('从2026-01-15至2026-01-15统计订单')
        self.assertTrue(result.success)
        self.assertEqual(result.output['data']['observed_range']['start_date'],'2026-01-15')
        self.assertIn('start_date=2026-01-15',self.requests[0][1])

    async def test_bad_or_unsupported_time_does_not_read(self):
        for q in ('本月订单','2026年订单','2026-02-30 至 2026-03-01','2026-01-01',
                  '2026-02-01 至 2026-01-01','今年2026-01-01至2026-02-01'):
            self.assertFalse((await self.run_agent(q)).success)
        self.assertFalse(self.requests)

    async def test_unknown_entities_not_broadened(self):
        self.settings.crm_tool_provider='http'
        for q in ('对比C999和C001','customer:other','客户=C999'):
            self.assertEqual((await self.run_agent(q)).error,'ANALYSIS_ENTITY_UNAVAILABLE')

    async def test_selection_and_exact_minor_money(self):
        self.settings.crm_tool_provider='http'
        self.orders.append({**self.order('O3',99),'customer_id':'C002'})
        self.customers.append(dict(customer_id='C002',name='Other',level='A',version=1))
        result=await self.run_agent('统计C001订单')
        self.assertEqual(result.output['data']['totals_by_currency']['CNY']['order_amount_minor'],30)

    async def test_mixed_currencies_never_summed_together(self):
        self.settings.crm_tool_provider='http';self.orders[1]['currency']='USD'
        result=await self.run_agent()
        self.assertEqual(set(result.output['data']['totals_by_currency']),{'CNY','USD'})

    async def test_revenue_not_approximated(self):
        result=await self.run_agent('累计销售额')
        self.assertEqual(result.error,'ANALYSIS_METRIC_UNSUPPORTED')

    async def test_html_and_markdown_names_are_escaped(self):
        self.settings.crm_tool_provider='http';self.customers[0]['name']='<img src=x>|bad'
        result=await self.run_agent()
        self.assertNotIn('<img',result.output['answer']);self.assertIn('&#124;',result.output['answer'])

    async def test_no_report_or_parser_model_calls(self):
        self.settings.crm_tool_provider='http'
        self.primary.side_effect=AssertionError('LLM must not rewrite values')
        self.assertTrue((await self.run_agent()).success)
        self.primary.assert_not_called()

    async def test_multi_agent_aggregation_preserves_analysis(self):
        analysis=await self.run_agent()
        other=BASE['Result'](agent_name='knowledge',output={'answer':'Other answer'})
        self.aggregator._llm_aggregate=AsyncMock(side_effect=AssertionError)
        result=await self.aggregator.aggregator_node({'user_input':self.user(),
            'agent_results':[analysis,other],'intent':self.intent.ANALYSIS if hasattr(self.intent,'ANALYSIS')
            else self.intent.KNOWLEDGE_QA})
        self.assertIn(analysis.output['answer'],result['final_answer'])
        self.aggregator._llm_aggregate.assert_not_called()

    async def test_executor_forwards_identity_to_analysis(self):
        self.executor.AnalysisAgent=self.analysis.AnalysisAgent
        agent=self.executor._get_agent(self.kind.ANALYSIS,self.user())
        self.assertEqual(agent.user_id,'user-a')

    async def test_network_exception_is_fixed_and_contains_no_payload(self):
        self.settings.crm_tool_provider='http'
        with patch.object(self.ref,'request',AsyncMock(side_effect=RuntimeError('PRIVATE_SECRET'))):
            result=await self.run_agent()
        self.assertEqual(result.error,'ANALYSIS_SOURCE_UNAVAILABLE')
        self.assertNotIn('PRIVATE_SECRET',str(result.output))

    async def test_cancellation_propagates_without_fallback(self):
        self.settings.crm_tool_provider='http'
        with patch.object(self.ref,'request',AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):await self.run_agent()

    async def test_status_selection_and_unsupported_metrics_are_explicit(self):
        self.settings.crm_tool_provider='http';self.orders[1]['status']='cancelled'
        result=await self.run_agent('已完成订单')
        self.assertEqual(result.output['data']['totals_by_currency']['CNY']['order_amount_minor'],10)
        for query in ('前三名客户','行业分布','排除已取消订单','平均金额'):
            self.assertEqual((await self.run_agent(query)).error,'ANALYSIS_METRIC_UNSUPPORTED')

    async def test_executor_uses_original_query_not_model_rewritten_scope(self):
        agent=NS(run=AsyncMock(return_value=BASE['Result']()))
        self.executor._get_agent=Mock(return_value=agent)
        await self.executor.agent_executor_node({'user_input':self.user(message='2026-01-01至2026-02-01'),
            'current_subtask':BASE['Task'](task_type=self.kind.ANALYSIS,task_id='a',description='all orders')})
        agent.run.assert_awaited_once_with('2026-01-01至2026-02-01')


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(AnalysisTests(name) for name in AnalysisTests.__dict__
                              if name.startswith('test_'))


if __name__ == '__main__':
    sys.dont_write_bytecode=True
    def guard(event,args):
        if event=='socket.__new__' and args[1]==1:return
        if event.startswith(('socket.','subprocess.','ctypes.')) or event in {
                'os.remove','os.rmdir','os.rename','os.system','os.mkdir','os.chmod','os.chown',
                'os.truncate','os.utime','os.link','os.symlink','os.exec','os.posix_spawn',
                'os.fork','os.forkpty','os.putenv','os.unsetenv'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event=='open' and (isinstance(args[1],str) and any(c in args[1] for c in 'wax+')
                or isinstance(args[2],int) and args[2]&3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
