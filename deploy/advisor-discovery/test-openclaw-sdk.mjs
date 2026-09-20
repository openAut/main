// Optional contract test against the OpenClaw 2026.9.4 hook module's exports.
// Set OPENCLAW_HOOKS_MODULE to the installed hooks module; no host path is embedded here.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

if(!process.env.OPENCLAW_HOOKS_MODULE) throw new Error('Set OPENCLAW_HOOKS_MODULE for this version-bound optional test');
const {y:resolveHooksConfig,b:applyHookMappings,v:resolveHookSessionKey}=await import(pathToFileURL(process.env.OPENCLAW_HOOKS_MODULE));
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'openaut-hooks-test-'));
const old=process.env.OPENCLAW_CONFIG_PATH;
const prior=Object.fromEntries(['HOME','OPENCLAW_STATE_DIR','XDG_CACHE_HOME'].map(k=>[k,process.env[k]]));
try {
  process.env.OPENCLAW_CONFIG_PATH=path.join(temp,'config.json');
  process.env.HOME=temp;
  process.env.OPENCLAW_STATE_DIR=temp;
  process.env.XDG_CACHE_HOME=path.join(temp,'.cache');
  const transforms=path.join(temp,'hooks','transforms');
  fs.mkdirSync(transforms,{recursive:true});
  fs.writeFileSync(path.join(transforms,'fixture.mjs'),`import {createTransform} from ${JSON.stringify(new URL('./openclaw/alarm-transform.mjs',import.meta.url).href)};
export default createTransform(async id=>id==='ahu-03'?{equipment_id:id,equipment:[{equipment_id:id,alarm_watch:true,alarm_metrics:{fault_flags:'uint16'}}]}:{});`);
  const hooks=JSON.parse(fs.readFileSync(new URL('./hooks.example.json',import.meta.url),'utf8'));
  hooks.token='synthetic-fixture-token';
  for(const mapping of hooks.mappings) mapping.transform.module='fixture.mjs';
  const config=resolveHooksConfig({agents:{defaults:{}},hooks});
  for(const synthetic of [false,true]) {
    const route=synthetic?'equipment-test':'equipment';
    const event={equipment_id:'ahu-03',synthetic,event_id:'fixture-1',changes:[{kind:'process_alarm_change',metric:'fault_flags',source_ts:'2030-01-01T00:00:00Z',previous:0,current:1}]};
    const context={path:route,url:new URL('http://127.0.0.1/'+route),headers:{},payload:{event_json:JSON.stringify(event)}};
    const result=await applyHookMappings(config.mappings,context);
    assert.equal(result.ok,true); assert.equal(result.actions.length,1);
    const action=result.actions[0];
    assert.equal(action.sessionKeySource,'static'); assert.equal(action.agentId,'main');
    assert.equal(action.deliver,false); assert.equal(action.allowUnsafeExternalContent,false);
    assert.equal(resolveHookSessionKey({hooksConfig:config,source:'mapping-static',sessionKey:action.sessionKey}).ok,true);
    assert.equal(resolveHookSessionKey({hooksConfig:config,source:'request',sessionKey:action.sessionKey}).ok,false);
    await assert.rejects(()=>applyHookMappings(config.mappings,{...context,payload:{event_json:JSON.stringify({...event,equipment_id:'outside'})}}));
  }
  // Also exercise the real plugin discovery + tool policy, rather than just a mock register().
  const dist=path.dirname(process.env.OPENCLAW_HOOKS_MODULE);
  const bindings={
    'agent-tools.policy':'agent-tools.policy-BYQnd2Ij.mjs',
    'tool-policy':'tool-policy-DZjipCVm.mjs',
    'tool-policy-pipeline':'tool-policy-pipeline-M7HPpWrp.mjs',
    tools:'tools-CulcXFDi.mjs',
  };
  async function compiled(prefix) {
    return import(pathToFileURL(path.join(dist,bindings[prefix])));
  }
  const {n:resolvePolicy}=await compiled('agent-tools.policy');
  const {collectExplicitAllowlist,collectExplicitDenylist}=await compiled('tool-policy');
  const {n:buildSteps,t:applyPipeline}=await compiled('tool-policy-pipeline');
  const {r:resolveTools}=await compiled('tools');
  const cfg={agents:{defaults:{workspace:temp}},tools:{allow:['openaut_read'],deny:['group:runtime','group:fs','group:automation','group:sessions']},
    plugins:{allow:['openaut-read'],slots:{memory:'none'},load:{paths:[fileURLToPath(new URL('./openclaw',import.meta.url))]},entries:{'openaut-read':{enabled:true}}}};
  const policy=resolvePolicy({config:cfg,agentId:'main',sessionKey:'agent:main:main'});
  const tools=resolveTools({context:{config:cfg,runtimeConfig:cfg,workspaceDir:temp,agentId:'main'},
    toolAllowlist:collectExplicitAllowlist([policy.globalPolicy]),toolDenylist:collectExplicitDenylist([policy.globalPolicy])});
  assert.deepEqual(tools.map(t=>t.name),['openaut_read']);
  const filtered=applyPipeline({tools:[...tools,...['exec','read','write','browser','sessions_spawn','unknown_future_tool'].map(name=>({name}))],
    toolMeta:t=>t.name==='openaut_read'?{pluginId:'openaut-read',optional:true}:undefined,warn:()=>{},steps:buildSteps({...policy})});
  assert.deepEqual(filtered.map(t=>t.name),['openaut_read']);
  console.log('PORTABLE_OPENCLAW_SDK_HOOK_AND_POLICY_TESTS_PASS');
} finally {
  if(old===undefined) delete process.env.OPENCLAW_CONFIG_PATH; else process.env.OPENCLAW_CONFIG_PATH=old;
  for(const [key,value] of Object.entries(prior)) {if(value===undefined) delete process.env[key]; else process.env[key]=value;}
  fs.rmSync(temp,{recursive:true,force:true});
}
