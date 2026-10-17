"""C12 actual-source orchestration tests. Doubles are not PostgreSQL/HTTP acceptance."""
from __future__ import annotations

import asyncio
import ast
from contextlib import ExitStack, asynccontextmanager, contextmanager, nullcontext
from copy import deepcopy
from enum import Enum
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]


def module(name, **attrs):
    value = ModuleType(name)
    value.__dict__.update(attrs)
    return value


def load(name, path):
    value = module(name)
    value.__file__ = str(ROOT / path)
    sys.modules[name] = value
    exec(compile((ROOT / path).read_bytes(), value.__file__, 'exec'), value.__dict__)
    return value


class Role(str, Enum):
    MANAGER = 'manager'
    FINANCE = 'finance'


class Database:
    """SQL orchestration double: no claims about PostgreSQL isolation or syntax."""
    def __init__(self):
        self.executions = {}
        self.operations = {}
        self.commits = 0
        self.fail = False
        self.sql = []

    @asynccontextmanager
    async def session(self):
        yield self

    async def commit(self):
        self.commits += 1
        if self.fail:
            raise RuntimeError('synthetic database failure')

    async def execute(self, sql, args):
        if self.fail:
            raise RuntimeError('synthetic failure')
        self.sql.append((sql, deepcopy(args)))
        row = None
        if 'INSERT INTO tool_executions' in sql:
            self.executions.setdefault(args['scope'], dict(execution_id=args['eid'], scope_key=args['scope'],
                plan_hash=args['hash'], owner_id=args['owner'], session_id=args['sid'], calls=json.loads(args['calls'])))
        elif 'SELECT * FROM tool_executions' in sql:
            row = self.executions.get(args['scope'])
        elif 'INSERT INTO tool_operations' in sql:
            self.operations.setdefault(args['oid'], dict(operation_id=args['oid'], execution_id=args['eid'],
                slot=args['slot'], intent=json.loads(args['intent']), state='prepared', request=None, receipt=None))
        elif 'JOIN tool_executions' in sql:
            operation = self.operations.get(args['oid'])
            if operation:
                execution = next(x for x in self.executions.values() if x['execution_id']==operation['execution_id'])
                row = {**execution, **operation}
        elif "SET request =" in sql:
            operation = self.operations[args['oid']]
            if operation['state']=='prepared' and operation['request'] is None:
                operation['request'] = json.loads(args['request'])
        elif "SET state = 'dispatched'" in sql:
            operation = self.operations[args['oid']]
            if operation['state']=='prepared' and operation['request'] is not None:
                operation['state']='dispatched'
                row = {'operation_id':args['oid']}
        elif 'SET state = :state' in sql:
            operation = self.operations[args['oid']]
            if operation['state'] in ('dispatched','unknown'):
                operation.update(state=args['state'], receipt=json.loads(args['receipt']))
                row = {'operation_id':args['oid']}
        else:
            raise AssertionError(sql)
        result = NS(returns_rows=True)
        result.mappings = lambda: NS(first=lambda: deepcopy(row))
        return result


class SafetyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.db=Database()
        self.settings=NS(tool_provider='http', tool_reference_profile='business-reference-v1',
            tool_reference_run_id=str(uuid.uuid4()), tool_reference_principal='synthetic-principal',
            crm_api_base='http://reference-crm:8080/api/v1', crm_api_token='synthetic-crm',
            ticket_api_base='http://reference-ticket:8080/api/v1', ticket_api_token='synthetic-ticket',
            mail_api_base='http://reference-mail:8080/api/v1', mail_api_token='synthetic-mail',
            external_timeout_seconds=5, external_max_retries=2)
        self.user=NS(user_id='test-user',role='manager')
        self.resolve=AsyncMock(side_effect=lambda *a,**kw:self.user)
        self.audit=NS(log_tool_call=AsyncMock(),log_violation=AsyncMock())
        self.stack.enter_context(patch.dict(sys.modules, {
            'app':module('app'), 'app.core':module('app.core'), 'app.tools':module('app.tools'),
            'app.config':module('app.config', get_settings=lambda:self.settings),
            'app.core.database':module('app.core.database',get_session_factory=lambda:self.db.session),
            'sqlalchemy':module('sqlalchemy',text=lambda x:x),
            'loguru':module('loguru',logger=Mock()),
            'app.security.rbac':module('app.security.rbac',AgentRole=Role,resolve_active_user=self.resolve,
                can_use_tool=lambda role,name:role==Role.MANAGER),
            'app.observability.audit':module('app.observability.audit',get_audit_logger=lambda:self.audit),
            'app.observability.tracing':module('app.observability.tracing',
                record_span_attributes=Mock(), record_span_event=Mock(), record_exception=Mock(),
                traced_span=lambda *a,**kw:nullcontext()),
            'httpx':module('httpx', HTTPError=type('HTTPError',(Exception,),{})),
        }))
        self.redaction=load('app.security.redaction','app/security/redaction.py')
        self.ops=load('app.core.tool_operations','app/core/tool_operations.py')
        self.transport=load('app.tools.http_adapter','app/tools/http_adapter.py')
        self.ref=load('app.tools.reference','app/tools/reference.py')
        sys.modules['app.tools'].reference=self.ref
        self.base=load('app.tools.base','app/tools/base.py')
        self.gateway=load('app.tools.operation_gateway','app/tools/operation_gateway.py')
        self.saga=load('app.tools.saga','app/tools/saga.py')
        base=self.base
        class Tool(base.BaseTool):
            name='create_ticket'
            category=base.ToolCategory.ACTION
            async def _execute(self, params, context):
                return base.ToolResult(True,self.name,{'mock':True})
        self.tool=Tool()
        self.base.register_tool(self.tool)
        self.context=dict(user_id='test-user',role='manager',session_id='session',request_id=str(uuid.uuid4()),execution_slot='task-1')
        self.calls=[]
        self.real_request=self.ref.request
        self.ref.request=AsyncMock(side_effect=self.respond)
        self.mode='valid'
        self.send_count=0
        self.response_count=0

    async def prepare(self, name='create_ticket', params=None, context=None):
        self.tool.name=name
        self.tool.requires_approval=name=='send_email_external'
        self.base.register_tool(self.tool)
        plan=NS(tool=name,params=params if params is not None else {'title':'test'},operation_id=None)
        ctx=context if context is not None else self.context
        await self.gateway.prepare_calls([plan],ctx)
        ctx['operation_id']=plan.operation_id
        return plan

    def receipt(self, oid):
        row=self.db.operations[oid]
        frozen=row['request']; name=row['intent']['tool']
        after=2 if name=='update_ticket' else 1
        rid='T1' if name=='update_ticket' else 'R1'
        op=dict(operation_id=oid,run_id=self.settings.tool_reference_run_id,
            service=row['intent']['target']['service'],request_hash=self.ops.fingerprint(frozen),
            state='committed',resource_id=rid,after_version=after,created_at='2026-10-17T00:00:00Z',
            completed_at='2026-10-17T00:00:01Z',compensates_operation_id=None,
            effect='updated' if name=='update_ticket' else 'created')
        if name.startswith('send_email'):
            op['effect']='captured'
            return dict(message_id=rid,receipt_state='captured',recipients=len(set(frozen['body']['to']+frozen['body']['cc'])),operation=op)
        kind,key=('task','task_id') if name=='create_crm_task' else ('ticket','ticket_id')
        if name=='update_ticket':op['before']={'ticket_id':rid,'version':1}
        obj={key:rid,'version':after,'status':'open',**frozen['body']}
        if 'comment' in obj:
            obj['comments']=[{'comment_id':'C1','text':obj.pop('comment')}]
        return {kind:obj,'operation':op}

    async def respond(self, target, method, path, **kw):
        self.calls.append((method,path,deepcopy(kw)))
        if method=='GET' and path.startswith('/tickets/'):
            return True,{'ticket':{'ticket_id':'T1','version':1}},None,{'status':200}
        if method=='GET':
            oid=path.rsplit('/',1)[1]
            if self.mode in ('unknown','invalid','lost-store'):
                return False,None,'EXTERNAL_HTTP_404',{'status':404}
            data=self.receipt(oid)
            return True,{'operation':data['operation'],'result':data},None,{'status':200}
        self.send_count+=1
        oid=kw['operation_id']
        self.assertEqual(self.db.operations[oid]['state'],'dispatched')
        self.assertIsNotNone(self.db.operations[oid]['request'])
        if self.mode=='lost-store':
            self.db.fail=True
        if self.mode in ('loss','unknown'):
            return False,None,'EXTERNAL_TRANSPORT_UNCERTAIN',{}
        if self.mode=='invalid':
            return True,{},None,{'status':201}
        return True,self.receipt(oid),None,{'status':200 if method=='PATCH' else 201}

    async def test_persisted_distinct_ids_for_identical_action_slots(self):
        plans=[NS(tool='create_ticket',params={'title':'test'},operation_id=None) for _ in range(2)]
        await self.gateway.prepare_calls(plans,self.context)
        self.assertNotEqual(plans[0].operation_id,plans[1].operation_id)
        self.assertEqual(len(self.db.operations),2)

    async def test_restart_scope_reuses_ids(self):
        first=await self.prepare()
        second=await self.prepare(context=dict(self.context,operation_id=None))
        self.assertEqual(first.operation_id,second.operation_id)

    async def test_different_request_or_task_creates_distinct_identity(self):
        one=await self.prepare()
        for change in ({'request_id':str(uuid.uuid4())},{'execution_slot':'task-2'}):
            other=await self.prepare(context={**self.context,**change})
            self.assertNotEqual(one.operation_id,other.operation_id)

    async def test_changed_plan_denied_without_rekey(self):
        await self.prepare()
        with self.assertRaisesRegex(self.ops.OperationError,'PLAN_CONFLICT'):
            await self.prepare(params={'title':'changed'})
        self.assertEqual(len(self.db.operations),1)

    async def test_missing_scope_or_mixed_identity_denied(self):
        for key in ('user_id','session_id','request_id','execution_slot'):
            with self.assertRaises(self.ops.OperationError):
                await self.prepare(context={**self.context,key:''})
        with self.assertRaises(self.ops.OperationError):
            await self.gateway.prepare_calls([NS(tool='create_ticket',operation_id=str(uuid.uuid4())),
                NS(tool='create_ticket',operation_id=None)],self.context)

    async def test_secret_content_not_persisted(self):
        with self.assertRaisesRegex(self.ops.OperationError,'CREDENTIAL'):
            await self.prepare(params={'title':'Authorization: Bearer synthetic-secret'})
        self.assertFalse(self.db.operations)

    async def test_store_failure_prevents_dispatch(self):
        await self.prepare();self.db.fail=True
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertFalse(result.success);self.assertEqual(self.send_count,0)

    async def test_valid_receipt_committed_then_replay_is_read_only(self):
        await self.prepare()
        first=await self.tool.invoke({'title':'test'},self.context)
        again=await self.tool.invoke({'title':'test'},self.context)
        self.assertTrue(first.success and again.success)
        self.assertEqual(self.send_count,1)
        self.assertEqual(first.side_effects['operation_id'],again.side_effects['operation_id'])

    async def test_parallel_same_identity_sends_once(self):
        await self.prepare()
        results=await asyncio.gather(*(self.tool.invoke({'title':'test'},self.context) for _ in range(8)))
        self.assertTrue(all(result.success for result in results));self.assertEqual(self.send_count,1)

    async def test_response_loss_queries_original_receipt(self):
        await self.prepare();self.mode='loss'
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertTrue(result.success);self.assertEqual(self.send_count,1)
        self.assertEqual(self.calls[-1][0],'GET')

    async def test_unknown_and_reentry_never_send_again(self):
        await self.prepare();self.mode='unknown'
        for _ in range(2):
            result=await self.tool.invoke({'title':'test'},self.context)
            self.assertFalse(result.success)
            self.assertEqual(result.side_effects['outcome'],'unknown')
        self.assertEqual(self.send_count,1)

    async def test_crash_after_claim_before_send_does_not_reclaim(self):
        await self.prepare()
        store=self.ops.OperationStore();oid=self.context['operation_id']
        await store.freeze(oid,self.ref.wire('create_ticket',{'title':'test'},'test-user'))
        await store.claim(oid);self.mode='unknown'
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertFalse(result.success);self.assertEqual(self.send_count,0)

    async def test_receipt_commit_failure_is_not_success(self):
        await self.prepare();self.mode='lost-store'
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertFalse(result.success);self.assertEqual(self.send_count,1)
        self.db.fail=False;self.mode='loss'
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertTrue(result.success);self.assertEqual(self.send_count,1)

    async def test_invalid_2xx_is_unknown(self):
        await self.prepare();self.mode='invalid'
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertFalse(result.success);self.assertEqual(self.send_count,1)

    async def test_receipt_identity_hash_version_and_effect_matrix(self):
        await self.prepare();await self.tool.invoke({'title':'test'},self.context)
        row=await self.ops.OperationStore().load(self.context['operation_id'])
        for key,value in {'operation_id':str(uuid.uuid4()),'run_id':str(uuid.uuid4()),'service':'crm',
                          'request_hash':'bad','state':'pending','resource_id':'other','after_version':True,
                          'created_at':'bad','completed_at':None,'effect':'recalled',
                          'compensates_operation_id':str(uuid.uuid4())}.items():
            data=deepcopy(row['receipt']);data['operation'][key]=value
            with self.subTest(key=key),self.assertRaises(self.ops.OperationError):self.ref.receipt(data,row)

    async def test_current_role_revocation_and_skip_flag_deny(self):
        await self.prepare();self.user.role='finance'
        result=await self.tool.invoke({'title':'test'},self.context,skip_rbac=True)
        self.assertFalse(result.success);self.assertEqual(self.send_count,0)

    async def test_context_flags_do_not_authorize_external_mail(self):
        params={'to':['customer@reference.invalid'],'subject':'test','body':'test'}
        await self.prepare('send_email_external',params)
        result=await self.tool.invoke(params,{**self.context,'approval_id':'A1','approved':True},skip_rbac=True)
        self.assertFalse(result.success);self.assertEqual(self.send_count,0)

    async def test_approved_external_capture_counts_cc_and_scope_resets(self):
        params={'to':['customer@reference.invalid'],'cc':['manager@reference.invalid'],'subject':'test','body':'test'}
        await self.prepare('send_email_external',params);self.context['approval_id']='A1'
        with self.ops.approved_calls('test-user','A1',self.context['execution_calls']):
            result=await self.tool.invoke(params,self.context)
        self.assertTrue(result.success);self.assertEqual(result.output['recipients'],2)
        again=await self.tool.invoke(params,self.context)
        self.assertFalse(again.success);self.assertEqual(self.send_count,1)

    async def test_changed_target_or_params_or_owner_denied(self):
        await self.prepare()
        for ctx,params in [({**self.context,'user_id':'other'},{'title':'test'}),
                           (self.context,{'title':'other'}),({**self.context,'session_id':'other'},{'title':'test'})]:
            self.assertFalse((await self.tool.invoke(params,ctx)).success)
        self.settings.tool_reference_run_id=str(uuid.uuid4())
        self.assertFalse((await self.tool.invoke({'title':'test'},self.context)).success)
        self.assertEqual(self.send_count,0)

    async def test_provider_switch_is_not_mock_fallback(self):
        await self.prepare();self.settings.tool_provider='mock'
        self.assertFalse((await self.tool.invoke({'title':'test'},self.context)).success)

    async def test_unproven_profile_denies_before_io(self):
        self.settings.tool_reference_profile=''
        with self.assertRaises(self.ops.OperationError):await self.prepare()
        self.assertEqual(self.send_count,0)

    async def test_update_reads_version_and_freezes_precondition(self):
        params={'ticket_id':'T1','comment':'test'}
        await self.prepare('update_ticket',params)
        result=await self.tool.invoke(params,self.context)
        self.assertTrue(result.success)
        self.assertEqual(self.calls[1][2]['if_match'],'"1"')
        self.assertEqual(self.calls[1][2]['body'],{'comment':'test'})

    async def test_mail_targets_and_attachments_fail_closed(self):
        for params in ({'to':['real@example.com']},{'to':['customer@reference.invalid']},
                       {'to':['employee@reference.invalid'],'cc':['real@example.com']},
                       {'to':['employee@reference.invalid'],'attachments':['/etc/passwd']}):
            with self.assertRaises(self.ops.OperationError):
                self.ref.wire('send_email_internal',{'subject':'test','body':'test',**params},'test-user')

    async def test_path_injection_rejected(self):
        for value in ('../x','a/b','%2F','a?x=1','a#b',''):
            with self.assertRaises(self.ops.OperationError):self.ref.resource_id(value)

    async def test_saga_unknown_stops_downstream_and_compensation(self):
        await self.prepare();self.mode='unknown'
        coordinator=self.saga.SagaCoordinator(self.context)
        coordinator.add_step('one','create_ticket',{'title':'test'},operation_id=self.context['operation_id'])
        coordinator.add_step('two','create_ticket',{'title':'later'},operation_id=str(uuid.uuid4()))
        coordinator._compensate=AsyncMock()
        result=await coordinator.execute()
        self.assertFalse(result.success or result.compensated)
        coordinator._compensate.assert_not_awaited();self.assertEqual(self.send_count,1)

    async def test_missing_compensation_evidence_is_failure(self):
        step=self.saga.SagaStep('one','create_ticket',{},result=self.base.ToolResult(True,'create_ticket',{}))
        result=await self.saga.SagaCoordinator(self.context)._compensate([step])
        self.assertTrue(result);self.assertEqual(step.status,self.saga.SagaStepStatus.COMPENSATION_FAILED)

    def source_function(self, path, name, owner=None, **namespace):
        tree=ast.parse((ROOT/path).read_text())
        if owner:tree=next(n for n in tree.body if getattr(n,'name',None)==owner)
        node=next(n for n in tree.body if getattr(n,'name',None)==name)
        node.decorator_list=[]
        ns={'Any':object,**namespace}
        exec(compile('from __future__ import annotations\n'+ast.unparse(node),path,'exec'),ns)
        return ns[name]

    async def test_actual_single_and_saga_entry_preserve_operation_ids(self):
        plan=await self.prepare()
        single=self.source_function('app/agents/execution.py','_invoke_single',
            get_tool=self.base.get_tool,ToolResult=self.base.ToolResult)
        result=await single(plan,self.context)
        self.assertTrue(result.success)
        saga=self.source_function('app/agents/execution.py','_invoke_saga',
            get_tool=self.base.get_tool,SagaCoordinator=self.saga.SagaCoordinator)
        result=await saga([plan],self.context)
        self.assertTrue(result.success);self.assertEqual(self.send_count,1)
        self.assertNotIn('step_id',self.context)

    async def test_actual_approval_creation_freezes_ids_without_credentials(self):
        plan=NS(tool='send_email_external',params={'to':['customer@reference.invalid'],
            'subject':'test','body':'test'},operation_id=None)
        self.tool.name=plan.tool;self.base.register_tool(self.tool)
        create=self.source_function('app/agents/execution.py','_create_approval_request',
            'ExecutionAgent',uuid=uuid,json=json,get_tool=self.base.get_tool,
            redact_text=self.redaction.redact_text,redact_value=self.redaction.redact_value,
            logger=Mock(),get_audit_logger=lambda:NS(log=AsyncMock()))
        writes=[]
        @asynccontextmanager
        async def approval_session():
            async def execute(sql,args):writes.append((sql,args))
            yield NS(execute=execute,commit=AsyncMock())
        original_prepare=self.gateway.prepare_calls
        async def prepare(*args,**kwargs):
            with patch.object(sys.modules['app.core.database'],'get_session_factory',
                              return_value=self.db.session):
                await original_prepare(*args,**kwargs)
        owner=NS(_build_approval_summary=lambda *a:'test')
        with patch.object(self.gateway,'prepare_calls',side_effect=prepare),patch.object(
                sys.modules['app.core.database'],'get_session_factory',return_value=approval_session):
            await create(owner,[plan],{**self.context,'jwt_token':'transient'},'test')
        payload=json.loads(writes[-1][1]['payload'])
        self.assertEqual(payload['tool_calls'][0]['operation_id'],plan.operation_id)
        self.assertNotIn('transient',json.dumps(writes))

    async def test_all_http_compensators_require_durable_evidence(self):
        for path,owner in [('crm','CreateCrmTaskTool'),('ticket','CreateTicketTool'),
                           ('ticket','UpdateTicketTool'),('mail','SendEmailInternalTool'),
                           ('mail','SendEmailExternalTool')]:
            compensate=self.source_function(f'app/tools/{path}.py','compensate',owner,
                ToolResult=self.base.ToolResult)
            result=await compensate(NS(name=owner,_effective_provider=lambda:'http'),{})
            self.assertFalse(result.success)
            self.assertEqual(result.error,'DURABLE_COMPENSATION_REQUIRED')
        self.ref.request.assert_not_awaited()

    async def test_read_projection_and_integer_money_mapping(self):
        self.tool.name='query_customer';self.tool.category=self.base.ToolCategory.QUERY
        self.ref.request=AsyncMock(return_value=(True,{'customer':{'customer_id':'C1',
            'version':1,'name':'test'}},None,{'status':200}))
        result=await self.ref.query(self.tool,{'customer_id':'C1','fields':['name']},self.context)
        self.assertTrue(result.success)
        self.assertEqual(self.ref.request.await_args.args[2],'/customers/C1?fields=name')
        self.tool.name='query_order'
        self.ref.request.return_value=(True,{'order':{'order_id':'O1','customer_id':'C1',
            'version':1,'amount_minor':1234,'currency':'CNY','status':'completed','items':[]}},None,{'status':200})
        result=await self.ref.query(self.tool,{'order_id':'O1','include_items':True},self.context)
        self.assertTrue(result.success);self.assertEqual(result.output['order']['amount'],12.34)

    async def test_read_rejects_projection_leak_and_wrong_id(self):
        self.tool.name='query_customer'
        for data in ({'customer_id':'C1','version':1,'email':'synthetic@reference.invalid'},
                     {'customer_id':'other','version':1,'name':'test'},
                     {'customer_id':'C1','name':'test'}):
            self.ref.request=AsyncMock(return_value=(True,{'customer':data},None,{'status':200}))
            self.assertFalse((await self.ref.query(self.tool,{'customer_id':'C1','fields':['name']},self.context)).success)

    async def test_crm_defaults_and_null_update_are_frozen(self):
        params={'customer_id':'C1','title':'test'}
        await self.prepare('create_crm_task',params)
        result=await self.tool.invoke(params,self.context)
        self.assertTrue(result.success)
        body=self.db.operations[self.context['operation_id']]['request']['body']
        self.assertEqual(body['assignee'],'test-user');self.assertIsNone(body['due_date'])
        self.assertEqual(self.ref.wire('update_ticket',{'ticket_id':'T1','assignee':None},'test-user')['body'],
                         {'assignee':None})

    async def test_missing_fields_and_extra_fields_cannot_be_receipts(self):
        await self.prepare();await self.tool.invoke({'title':'test'},self.context)
        row=await self.ops.OperationStore().load(self.context['operation_id'])
        for edit in ('missing_title','extra_field','missing_operation','empty'):
            data=deepcopy(row['receipt'])
            if edit=='missing_title':data['ticket'].pop('title')
            if edit=='extra_field':data['extra']='not-contract'
            if edit=='missing_operation':data.pop('operation')
            if edit=='empty':data={}
            with self.subTest(edit=edit),self.assertRaises(self.ops.OperationError):self.ref.receipt(data,row)

    async def test_committed_operation_evidence_reaches_audit(self):
        await self.prepare();result=await self.tool.invoke({'title':'test'},self.context)
        record=self.audit.log_tool_call.await_args.kwargs
        self.assertEqual(record['payload']['side_effects']['operation_id'],self.context['operation_id'])
        self.assertEqual(record['payload']['side_effects']['operation'],result.side_effects['operation'])

    def install_transport(self, responses):
        calls=[]; httpx=sys.modules['httpx']
        class Response:
            def __init__(self,status,body,headers=None):
                self.status_code=status;self.body=body
                self.headers=headers or {'X-Reference-Profile':'business-reference-v1'}
            async def aiter_bytes(self):
                for chunk in self.body:yield chunk
        @asynccontextmanager
        async def client(**kwargs):
            self.assertFalse(kwargs['follow_redirects'])
            @asynccontextmanager
            async def stream(method,url,**options):
                calls.append((method,deepcopy(options)))
                status,body=responses.pop(0)
                if status=='timeout':
                    await asyncio.sleep(1)
                if status=='error':raise httpx.HTTPError()
                yield Response(status,body)
            yield NS(stream=stream)
        httpx.AsyncClient=client
        return calls

    async def test_pending_reconciliation_budget_expires_without_resend(self):
        await self.prepare();self.mode='unknown'
        oid=self.context['operation_id']
        original=self.respond
        async def pending(target,method,path,**kwargs):
            if method=='GET':
                row=self.db.operations[oid]
                return True,{'operation':{'operation_id':oid,'run_id':self.settings.tool_reference_run_id,
                    'request_hash':self.ops.fingerprint(row['request']),'state':'pending'},'result':None},None,{'status':200}
            return await original(target,method,path,**kwargs)
        self.ref.request.side_effect=pending
        timeout=asyncio.timeout
        def short_budget(seconds):
            self.assertEqual(seconds,30)
            return timeout(.005)
        with patch.object(self.gateway.asyncio,'timeout',side_effect=short_budget):
            result=await self.tool.invoke({'title':'test'},self.context)
        self.assertFalse(result.success);self.assertEqual(self.send_count,1)
        self.assertEqual(self.db.operations[oid]['state'],'unknown')

    async def test_cancellation_keeps_claim_and_cannot_resend(self):
        await self.prepare();oid=self.context['operation_id']
        async def cancelled(*args,**kwargs):
            raise asyncio.CancelledError
        self.ref.request.side_effect=cancelled
        with self.assertRaises(asyncio.CancelledError):
            await self.tool.invoke({'title':'test'},self.context)
        self.assertEqual(self.db.operations[oid]['state'],'dispatched')
        self.mode='unknown';self.ref.request.side_effect=self.respond
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertFalse(result.success);self.assertEqual(self.send_count,0)

    async def test_gateway_reference_and_transport_share_original_identity(self):
        await self.prepare();oid=self.context['operation_id']
        await self.ops.OperationStore().freeze(oid,self.ref.wire('create_ticket',{'title':'test'},'test-user'))
        calls=self.install_transport([(201,[json.dumps(self.receipt(oid)).encode()])])
        self.ref.request=self.real_request
        result=await self.tool.invoke({'title':'test'},self.context)
        self.assertTrue(result.success);self.assertEqual(len(calls),1)
        headers=calls[0][1]['headers']
        self.assertEqual(headers['Idempotency-Key'],'ba-ref-v1:'+oid)
        self.assertEqual(headers['X-Reference-Run-Id'],self.settings.tool_reference_run_id)
        self.assertEqual(headers['Authorization'],'Bearer synthetic-ticket')
        self.assertNotEqual(headers['X-Request-Id'],oid)
        self.assertNotIn('synthetic-ticket',json.dumps(self.db.operations))

    async def test_transport_mutations_do_not_retry_even_with_key(self):
        for status in (503,429,401,403,409,422,428,501,'error'):
            calls=self.install_transport([(status,[b'{}'])])
            result=await self.transport.call_external_api('POST','https://synthetic.invalid',
                extra_headers={'Idempotency-Key':'same'},max_retries=9)
            self.assertFalse(result[0]);self.assertEqual(len(calls),1)

    async def test_transport_read_retries_and_attempt_ids_differ(self):
        calls=self.install_transport([(503,[]),(429,[]),(200,[b'{"ok":true}'])])
        with patch.object(self.transport.asyncio,'sleep',new=AsyncMock()):
            result=await self.transport.call_external_api('GET','https://synthetic.invalid')
        self.assertTrue(result[0]);self.assertEqual(len(calls),3)
        self.assertEqual(len({call[1]['headers']['X-Request-Id'] for call in calls}),3)

    async def test_transport_total_deadline(self):
        calls=self.install_transport([('timeout',[])])
        result=await self.transport.call_external_api('POST','https://synthetic.invalid',timeout_seconds=.001)
        self.assertFalse(result[0]);self.assertEqual(len(calls),1)

    async def test_transport_invalid_status_json_size_and_numbers(self):
        for status,body in ((302,[b'{}']),(204,[]),(200,[b'text']),(200,[b'[]']),
                            (200,[b'{"x":1,"x":2}']),(200,[b'{"x":NaN}']),
                            (200,[b'{"x":1.1}']),(200,[b'x'*65537])):
            calls=self.install_transport([(status,body)])
            result=await self.transport.call_external_api('POST','https://synthetic.invalid')
            self.assertFalse(result[0]);self.assertEqual(len(calls),1)


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    def guard(event, args):
        if event == 'socket.__new__' and args[1] == 1:return
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
