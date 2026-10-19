"""C22 retained synthetic fixtures and injected Docker; no application or real infrastructure."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import unittest
from unittest.mock import Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('recovery', ROOT/'scripts/recovery.py')
assert SPEC and SPEC.loader
recovery = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(recovery)
a = recovery.archive
FIXTURES = ROOT/'eval/results'/('c22-tests-'+uuid.uuid4().hex)


def inventory():
    roles = [('postgres','postgres_data','/var/lib/postgresql/data'),
             ('redis','redis_data','/data'), ('etcd','etcd_data','/etcd'),
             ('minio','minio_data','/minio_data'), ('milvus-standalone','milvus_data','/var/lib/milvus'),
             ('api','audit_state','/data/observability'), ('worker','audit_state','/data/observability')]
    return {'project':'c22-source','external_writers':[], 'containers':[
        {'id':format(i+1,'064x'), 'image':'sha256:'+'a'*64, 'service':service,
         'running':True,'paused':False,'restarting':False,'exit_code':0,
         'mounts':[{'name':'c22-source_'+volume,'type':'volume','target':target,'writable':True}]}
        for i,(service,volume,target) in enumerate(roles)],
        'volumes':[{'name':'c22-source_'+v,'project':'c22-source','logical':v,
                    'driver':'local','options':False} for v in sorted(recovery.CORE)]}


class FakeDocker:
    def __init__(self, source, root):
        self.source = copy.deepcopy(source); self.calls=[]; self.root=root
        self.volumes=set(v['name'] for v in source['volumes']); self.volume_owners={}; self.fail_stop=None; self.fail_start=None
    def inventory(self, project):
        if project == self.source['project']:return copy.deepcopy(self.source)
        return {'project':project,'containers':[],'volumes':[],'external_writers':[]}
    def run(self,*args,**kwargs):
        self.calls.append(args)
        if args[:2]==('image','inspect'):return 'sha256:'+'a'*64
        if args[:2]==('volume','ls'):return '\n'.join(sorted(self.volumes))
        if args[:2]==('ps','-aq'):return ''
        if args[:2]==('volume','inspect'):
            if '--format' in args and 'businessagent.recovery.run' in args[3]:return self.volume_owners.get(args[-1],'')
            return args[2]
        if args[:2]==('volume','create'):
            self.volumes.add(args[-1]); (self.root/args[-1]).mkdir()
            self.volume_owners[args[-1]]=next(a.split('=',1)[1] for a in args if a.startswith('businessagent.recovery.run='))
            return args[-1]
        if args[0]=='stop':
            cid=args[-1]
            for c in self.source['containers']:
                if c['id']==cid:c['running']=False
            if cid==self.fail_stop:raise RuntimeError('INJECTED_STOP_ACK_LOSS')
            return cid
        if args[0]=='start':
            cid=args[-1]
            if cid==self.fail_start:raise RuntimeError('INJECTED_START_FAILURE')
            for c in self.source['containers']:
                if c['id']==cid:c['running']=True
            return cid
        if args[0]=='inspect':
            for c in self.source['containers']:
                if c['id']==args[-1]:return json.dumps({'Running':c['running'],'ExitCode':c['exit_code']})
            return json.dumps({'Running':False,'ExitCode':0})
        if args[0]=='create':return 'helper'
        raise AssertionError(args)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root=FIXTURES/uuid.uuid4().hex;self.root.mkdir(parents=True)
        self.source=inventory(); self.plan=recovery.plan(self.source,'fixture/app@sha256:'+'b'*64,'c'*40)
        self.docker=FakeDocker(self.source,self.root)
        self.bundle=self.root/'bundle'
        for volume in self.plan['volumes']:
            path=self.root/volume;path.mkdir();(path/'record').write_bytes(b'synthetic persistent content')
        self.patch=patch.object(recovery,'helper',self.copy_helper);self.patch.start();self.addCleanup(self.patch.stop)
        self.owners=patch.object(a.os,'chown');self.owners.start();self.addCleanup(self.owners.stop)
    def copy_helper(self,docker,value,operation,volume,bundle,*,target=None):
        if operation=='pack':a.pack(self.root/volume,bundle,volume)
        else:
            meta=recovery.load(bundle/(volume+'.json'))
            a.restore(bundle/(volume+'.tar'),meta['members'],self.root/target)
    def capture(self):return recovery.backup(self.docker,self.plan,self.bundle)
    def test_complete_core_inventory(self):self.assertEqual(len(self.plan['volumes']),6)
    def test_optional_named_state_is_not_silently_omitted(self):
        item={'name':'c22-source_reference_crm','project':'c22-source','logical':'reference_crm','driver':'local','options':False}
        self.source['volumes'].append(item)
        self.source['containers'][0]['mounts'].append({'type':'volume','name':item['name'],'target':'/extra','writable':True})
        self.assertIn(item['name'],recovery.validate_source(self.source))
    def test_missing_core_state_refused(self):
        self.source['containers'].pop()
        with self.assertRaises(ValueError):recovery.validate_source(self.source)
    def test_wrong_service_mount_refused(self):
        self.source['containers'][0]['mounts'][0]['target']='/wrong'
        with self.assertRaises(ValueError):recovery.validate_source(self.source)
    def test_writable_bind_refused(self):
        self.source['containers'][0]['mounts'][0]['type']='bind'
        with self.assertRaises(ValueError):recovery.validate_source(self.source)
    def test_anonymous_or_foreign_volume_refused(self):
        self.source['containers'][0]['mounts'][0]['name']='foreign'
        with self.assertRaises(ValueError):recovery.validate_source(self.source)
    def test_external_writer_refused_even_when_not_running(self):
        self.source['external_writers']=['outside']
        with self.assertRaises(ValueError):recovery.validate_source(self.source)
    def test_network_volume_options_refused(self):
        self.source['volumes'][0]['options']=True
        with self.assertRaises(ValueError):recovery.validate_source(self.source)
    def test_paused_or_restarting_source_refused(self):
        for key in ('paused','restarting'):
            source=copy.deepcopy(self.source);source['containers'][0][key]=True
            with self.assertRaises(ValueError):recovery.validate_source(source)
    def test_mutable_helper_image_refused(self):
        with self.assertRaises(ValueError):recovery.plan(self.source,'fixture:latest','c'*40)
    def test_reviewed_hash_and_exact_isolation_required(self):
        recovery.validate_plan(self.plan,recovery.identity(self.plan),'c22-source')
        for approved,project in [('bad','c22-source'),(recovery.identity(self.plan),'wrong')]:
            with self.assertRaises(ValueError):recovery.validate_plan(self.plan,approved,project)
    def test_schema_drift_refused(self):
        value=copy.deepcopy(self.plan);value['schema_sha256']='0'*64
        with self.assertRaises(ValueError):recovery.validate_plan(value,recovery.identity(value),'c22-source')
    def test_inventory_drift_prevents_stops(self):
        self.docker.source['containers'][0]['image']='sha256:'+'d'*64
        with self.assertRaises(ValueError):self.capture()
        self.assertFalse(any(c[0]=='stop' for c in self.docker.calls));self.assertFalse(self.bundle.exists())
    def test_existing_bundle_is_preserved(self):
        self.bundle.mkdir();(self.bundle/'keep').write_text('keep')
        with self.assertRaises(ValueError):self.capture()
        self.assertEqual((self.bundle/'keep').read_text(),'keep');self.assertFalse(self.docker.calls)
    def test_capture_verifies_bytes_and_resumes_all_sources(self):
        result=self.capture();self.assertTrue(result['snapshot_complete'])
        self.assertEqual(result['source_resume_failed'],[])
        self.assertTrue(all(c['running'] for c in self.docker.source['containers']))
        value,report=recovery.verify_bundle(self.bundle);self.assertEqual(value,self.plan)
        self.assertEqual(report['runtime_acceptance'],'BLOCKED')
    def test_stopped_source_is_not_started(self):
        self.source['containers'][0]['running']=False
        self.plan=recovery.plan(self.source,'fixture/app@sha256:'+'b'*64,'c'*40)
        self.docker=FakeDocker(self.source,self.root);self.capture()
        self.assertNotIn(('start',self.source['containers'][0]['id']),self.docker.calls)
    def test_partial_stop_ack_failure_attempts_every_original_restart(self):
        self.docker.fail_stop=self.source['containers'][-1]['id']
        with self.assertRaises(RuntimeError):self.capture()
        self.assertEqual(sum(c[0]=='start' for c in self.docker.calls),7)
        self.assertFalse(recovery.load(self.bundle/'result.json')['snapshot_complete'])
    def test_archive_failure_retains_partial_and_resumes(self):
        def fail(*args,**kwargs):raise RuntimeError('INJECTED_COPY_FAILURE')
        with patch.object(recovery,'helper',fail),self.assertRaises(RuntimeError):self.capture()
        self.assertTrue((self.bundle/'plan.json').exists())
        self.assertTrue(all(c['running'] for c in self.docker.source['containers']))
    def test_resume_failure_does_not_skip_remaining_sources(self):
        self.docker.fail_start=self.source['containers'][0]['id']
        with self.assertRaises(RuntimeError):self.capture()
        report=recovery.load(self.bundle/'result.json')
        self.assertEqual(report['source_resume_failed'],[self.docker.fail_start])
        self.assertEqual(sum(c[0]=='start' for c in self.docker.calls),7)
    def test_interruption_still_attempts_source_resumption(self):
        with patch.object(recovery,'helper',side_effect=KeyboardInterrupt),self.assertRaises(RuntimeError):self.capture()
        self.assertEqual(sum(c[0]=='start' for c in self.docker.calls),7)
    def test_unclean_shutdown_is_not_a_complete_snapshot(self):
        self.docker.source['containers'][0]['exit_code']=1
        self.plan['source']['containers'][0]['exit_code']=1
        with self.assertRaises(RuntimeError):self.capture()
        self.assertFalse(recovery.load(self.bundle/'result.json')['snapshot_complete'])
    def test_restarted_writer_during_copy_invalidates_snapshot(self):
        def raced(*args,**kwargs):
            self.copy_helper(*args,**kwargs);self.docker.source['containers'][0]['running']=True
        with patch.object(recovery,'helper',raced),self.assertRaises(RuntimeError):self.capture()
        self.assertFalse(recovery.load(self.bundle/'result.json')['snapshot_complete'])
    def test_complete_bundle_hash_tampering_refused(self):
        self.capture();path=self.bundle/(self.plan['volumes'][0]+'.tar')
        with path.open('ab') as stream:stream.write(b'tampered')
        with self.assertRaises(ValueError):recovery.verify_bundle(self.bundle)
    def test_missing_volume_receipt_refused(self):
        self.capture();report=recovery.load(self.bundle/'result.json');report['files'].pop(next(iter(report['files'])))
        with patch.object(recovery,'load',side_effect=lambda p,*args: report if p.name=='result.json' else json.loads(p.read_text())):
            with self.assertRaises(ValueError):recovery.verify_bundle(self.bundle)
    def test_restore_refuses_same_or_nonisolated_project(self):
        self.capture()
        for target in ['c22-source','production']:
            with self.assertRaises(ValueError):recovery.restore_plan(self.bundle,target)
    def test_restore_only_creates_new_volumes_and_does_not_start_apps(self):
        self.capture();self.docker.calls=[]
        proposed=recovery.restore_plan(self.bundle,'c22-restore-test')
        recovery.restore_bundle(self.docker,proposed,self.bundle,self.root/'restore-receipt')
        for old,new in proposed['volumes'].items():
            self.assertEqual(a.scan(self.root/old),a.scan(self.root/new))
        self.assertFalse(any(c[0]=='start' for c in self.docker.calls))
        report=recovery.load(self.root/'restore-receipt/restore-result.json')
        self.assertTrue(report['byte_restore_complete']);self.assertFalse(report['application_started'])
    def test_existing_restore_volume_refused_before_creation(self):
        self.capture();proposed=recovery.restore_plan(self.bundle,'c22-restore-test')
        self.docker.volumes.add(next(iter(proposed['volumes'].values())));self.docker.calls=[]
        with self.assertRaises(ValueError):recovery.restore_bundle(self.docker,proposed,self.bundle,self.root/'receipt')
        self.assertFalse(any(c[:2]==('volume','create') for c in self.docker.calls))
    def test_target_mapping_tamper_refused(self):
        self.capture();proposed=recovery.restore_plan(self.bundle,'c22-restore-test')
        proposed['volumes'][self.plan['volumes'][0]]='production_data'
        with self.assertRaises(ValueError):recovery.restore_bundle(self.docker,proposed,self.bundle,self.root/'receipt')
    def test_restore_failure_retains_new_volumes_and_failure_receipt(self):
        self.capture();proposed=recovery.restore_plan(self.bundle,'c22-restore-test')
        with patch.object(recovery,'helper',side_effect=RuntimeError),self.assertRaises(RuntimeError):
            recovery.restore_bundle(self.docker,proposed,self.bundle,self.root/'receipt')
        self.assertFalse(recovery.load(self.root/'receipt/restore-result.json')['byte_restore_complete'])
        self.assertTrue(set(proposed['volumes'].values())&self.docker.volumes)
    def test_archive_restore_refuses_nonempty_directory(self):
        self.capture();v=self.plan['volumes'][0];rows=recovery.load(self.bundle/(v+'.json'))['members']
        with self.assertRaises(ValueError):a.restore(self.bundle/(v+'.tar'),rows,self.root/v)
    def test_parent_traversal_and_absolute_names_refused(self):
        for name in ['../escape','/etc/passwd','a/../../x','a\\b','a//b','./x']:
            with self.assertRaises(ValueError):a.member_name(name)
    def test_link_and_special_archive_members_refused(self):
        for kind in [tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.FIFOTYPE,tarfile.CHRTYPE]:
            data=io.BytesIO()
            with tarfile.open(fileobj=data,mode='w:') as stream:
                root=tarfile.TarInfo('.');root.type=tarfile.DIRTYPE;stream.addfile(root)
                member=tarfile.TarInfo('link');member.type=kind;member.linkname='../escape';stream.addfile(member)
            data.seek(0)
            with tarfile.open(fileobj=data,mode='r:') as stream,self.assertRaises(ValueError):
                a.verify_stream(stream,[{'name':'.','directory':True,'uid':0,'gid':0,'mode':420,'size':0,'sha256':None}, {'name':'link'}])
    def test_duplicate_member_manifest_refused(self):
        with self.assertRaises(ValueError):a.verify_stream([], [{'name':'.','directory':True}]*2)
    def test_source_and_tar_bytes_remain_after_repeated_restore_refusal(self):
        self.capture();before={p.name:a.file_hash(p) for p in self.bundle.iterdir()}
        with self.assertRaises(ValueError):recovery.backup(self.docker,self.plan,self.bundle)
        self.assertEqual(before,{p.name:a.file_hash(p) for p in self.bundle.iterdir()})
    def test_helper_recipe_has_no_network_auto_remove_or_pull(self):
        self.patch.stop()
        recovery.helper(self.docker,self.plan,'pack',self.plan['volumes'][0],self.root)
        command=next(c for c in self.docker.calls if c[0]=='create')
        self.assertIn('none',command);self.assertIn('--read-only',command)
        self.assertIn('--pull=never',command)
        self.assertTrue(any('volume-nocopy' in arg for arg in command))
        self.assertNotIn('--rm',command);self.assertNotIn('pull',command)
        self.assertTrue(any('dst=/source,readonly' in arg for arg in command))
    def test_main_requires_execute_and_reviewed_digest(self):
        path=self.root/'plan.json';a.write_json(path,self.plan)
        with patch.object(sys,'argv',['recovery','backup','--plan',str(path),'--output',str(self.bundle)]),patch.object(recovery,'Docker') as docker:
            self.assertEqual(recovery.main(),1);docker.assert_not_called()
    def test_rollback_requires_equal_schema_and_immutable_image(self):
        candidate={'image':self.plan['helper_image'],'commit':'c'*40,
                   'schema_sha256':self.plan['schema_sha256']}
        report=recovery.rollback_plan(candidate)
        self.assertFalse(report['execution_allowed']);self.assertFalse(report['semantic_compatibility_verified'])
        for key,value in [('image','fixture:latest'),('schema_sha256','0'*64)]:
            with self.assertRaises(ValueError):recovery.rollback_plan({**candidate,key:value})
    def test_window_thresholds_are_observations_not_acceptance(self):
        times={'snapshot_started_at':'2026-10-18T00:00:00Z','snapshot_finished_at':'2026-10-18T00:01:00Z',
               'incident_at':'2026-10-18T01:00:00Z','service_verified_at':'2026-10-18T01:30:00Z'}
        report=recovery.assess_window(times)
        self.assertEqual(report['rto_observed_seconds'],1800)
        self.assertEqual(report['rpo_upper_bound_seconds'],3600)
        self.assertEqual(report['status'],'OBSERVED');self.assertEqual(report['runtime_acceptance'],'BLOCKED')
    def test_window_excess_is_fail_and_time_order_is_strict(self):
        times={'snapshot_started_at':'2026-10-16T00:00:00Z','snapshot_finished_at':'2026-10-16T00:01:00Z',
               'incident_at':'2026-10-18T01:00:00Z','service_verified_at':'2026-10-18T03:00:00Z'}
        self.assertEqual(recovery.assess_window(times)['status'],'FAIL')
        source=self.root/'times.json';a.write_json(source,times)
        with patch.object(sys,'argv',['recovery','assess-window','--inventory',str(source),
                                     '--output',str(self.root/'window.json')]):
            self.assertEqual(recovery.main(),1)
        for replacement in ['2026-10-18T00:00:00Z','2026-10-18T03:00:00']:
            with self.assertRaises(ValueError):recovery.assess_window({**times,'service_verified_at':replacement})
    def test_helper_timeout_attempts_stop_and_never_reports_success(self):
        self.patch.stop();base=self.docker.run
        def fail(*args,**kwargs):
            if args[:2]==('start','-a'):raise RuntimeError('INJECTED_TIMEOUT')
            return base(*args,**kwargs)
        with patch.object(self.docker,'run',fail),self.assertRaises(RuntimeError):
            recovery.helper(self.docker,self.plan,'pack',self.plan['volumes'][0],self.root)
        self.assertTrue(any(c[0]=='stop' for c in self.docker.calls))

    def test_actual_inventory_omits_environment_and_bind_source(self):
        rows=[]
        for c in self.source['containers']:
            rows.append({**c,'project':'c22-source','recovery_helper':None,'mounts':[
                {'Type':m['type'],'Name':m['name'],'Destination':m['target'],'RW':m['writable'],
                 'Source':'/private/not-exported'} for m in c['mounts']]})
        rows.append({'id':'f'*64,'project':'other','running':False,'paused':False,
                     'restarting':False,'recovery_helper':'c22','mounts':[
                         {'Name':self.plan['volumes'][0],'RW':True}]})
        docker=recovery.Docker()
        def command(*args,**kwargs):
            if args[:2]==('ps','-aq'):return '\n'.join(r['id'] for r in rows)
            if args[:2]==('volume','ls'):return '\n'.join(v['name'] for v in self.source['volumes'])
            if args[0]=='inspect':return json.dumps(next(r for r in rows if r['id']==args[-1]))
            if args[:2]==('volume','inspect'):return json.dumps(next(v for v in self.source['volumes'] if v['name']==args[-1]))
            raise AssertionError(args)
        with patch.object(docker,'run',command):
            actual=docker.inventory('c22-source')
            self.assertEqual(recovery.validate_source(actual),self.plan['volumes'])
            self.assertNotIn('/private',json.dumps(actual))
            rows[-1]['running']=True
            with self.assertRaises(ValueError):recovery.validate_source(docker.inventory('c22-source'))
        self.assertNotIn('.Config.Env',recovery.INSPECT)
        source=copy.deepcopy(self.source)
        source['volumes'].append({'name':'c22-source_orphan','project':'c22-source',
                                  'logical':'orphan','driver':'local','options':False})
        with self.assertRaises(ValueError):recovery.validate_source(source)
    def test_volume_precreation_race_is_refused_before_restore_writes(self):
        self.capture();proposed=recovery.restore_plan(self.bundle,'c22-restore-race');base=self.docker.run
        def race(*args,**kwargs):
            result=base(*args,**kwargs)
            if args[:2]==('volume','create'):self.docker.volume_owners[args[-1]]='foreign-owner'
            return result
        with patch.object(self.docker,'run',race),patch.object(recovery,'helper') as helper:
            with self.assertRaises(ValueError):recovery.restore_bundle(self.docker,proposed,self.bundle,self.root/'receipt')
            helper.assert_not_called()
    def test_restore_refuses_attached_container_before_data_write(self):
        self.capture();proposed=recovery.restore_plan(self.bundle,'c22-restore-attached');base=self.docker.run
        def attached(*args,**kwargs):
            return 'outside' if args[:2]==('ps','-aq') else base(*args,**kwargs)
        with patch.object(self.docker,'run',attached),patch.object(recovery,'helper') as helper:
            with self.assertRaises(ValueError):recovery.restore_bundle(self.docker,proposed,self.bundle,self.root/'receipt')
            helper.assert_not_called()

    def test_sigterm_is_cooperative_and_prior_handler_restored(self):
        previous=object()
        with patch.object(recovery.signal,'signal',return_value=previous) as install:
            with self.assertRaises(InterruptedError):
                with recovery.termination_guard():install.call_args.args[1](15,None)
            self.assertIs(install.call_args.args[1],previous)
    def test_repeated_interrupt_during_resume_does_not_skip_other_containers(self):
        base=self.docker.run
        def interrupted(*args,**kwargs):
            if args==('start',self.source['containers'][0]['id']):raise KeyboardInterrupt
            return base(*args,**kwargs)
        with patch.object(self.docker,'run',interrupted):
            failed=recovery.resume(self.docker,self.plan)
        self.assertEqual(failed,[self.source['containers'][0]['id']])
        self.assertEqual(sum(c[0]=='start' for c in self.docker.calls),6)

    def test_no_automatic_deletion_in_controller_or_helper(self):
        for name in ['recovery.py','recovery_archive.py']:
            text=(ROOT/'scripts'/name).read_text()
            for forbidden in ['unlink(', 'rmtree(', 'os.remove(', '--rm', 'DROP SCHEMA', 'extractall(']:
                self.assertNotIn(forbidden,text)
        self.assertIn('COPY scripts/recovery_archive.py ./deploy/recovery_archive.py',(ROOT/'Dockerfile.prod').read_text())


if __name__=='__main__':
    sys.dont_write_bytecode=True
    def guard(event,args):
        if event.startswith(('socket.','subprocess.')) or event in {'os.remove','os.rmdir','os.rename','os.system','os.symlink','os.link'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event in {'os.mkdir','os.chmod','os.chown'}:
            path=Path(args[0]).absolute()
            if path != FIXTURES and FIXTURES not in path.parents:raise RuntimeError('OFFLINE_PATH_DENIED')
        if event=='open' and not isinstance(args[0],int):
            writing=(isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or (isinstance(args[2],int) and args[2]&3)
            if writing and FIXTURES not in Path(args[0]).absolute().parents:raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
