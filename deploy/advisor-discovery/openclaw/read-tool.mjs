import { readFile } from 'node:fs/promises';
import path from 'node:path';

const ID = /^[a-z0-9][a-z0-9._-]{0,62}$/;
const ALLOWED = {
  list_equipment: ['after','limit'], equipment: [], points: [], latest: [], health: [], alarms: [], documents: [],
  history: ['metrics','start','end','hours','limit'], document_search: ['query','document_id'],
  document_passage: ['document_id','start_line','lines'], guidance: ['skill'],
};
const OPTIONAL = new Set(Object.values(ALLOWED).flat());
export const validId = value => typeof value === 'string' && ID.test(value);

export function requestFor(input, now = new Date()) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('invalid_request');
  const known = new Set(['operation','equipment_id',...OPTIONAL]);
  if (Object.keys(input).some(k => !known.has(k))) throw new Error('unexpected_argument');
  const args = Object.fromEntries(Object.entries(input).filter(([k,v]) => !(OPTIONAL.has(k) && v == null)));
  if (!Object.hasOwn(ALLOWED,args.operation)) throw new Error('invalid_operation');
  if (Object.keys(args).some(k => !['operation','equipment_id',...ALLOWED[args.operation]].includes(k))) throw new Error('unexpected_argument');
  if (args.operation === 'list_equipment') {
    if (args.equipment_id != null || (args.after !== undefined && !validId(args.after))) throw new Error('invalid_discovery');
    if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1 || args.limit > 100)) throw new Error('invalid_limit');
  } else if (!validId(args.equipment_id)) throw new Error('equipment_required');
  if (args.operation === 'guidance') {
    if (!['fdd','anomaly-correlation'].includes(args.skill)) throw new Error('unknown_guidance');
    return {skill:args.skill};
  }
  const query = new URLSearchParams();
  if (args.equipment_id != null) query.set('equipment_id',args.equipment_id);
  if (args.operation === 'history') {
    if (!Array.isArray(args.metrics) || args.metrics.length < 1 || args.metrics.length > 8 || new Set(args.metrics).size !== args.metrics.length ||
        args.metrics.some(m => typeof m !== 'string' || !/^[a-z][a-z0-9_]{0,79}$/.test(m))) throw new Error('invalid_metrics');
    args.metrics = args.metrics.join(',');
    if (args.start !== undefined || args.end !== undefined) {
      if (typeof args.start !== 'string' || typeof args.end !== 'string' || args.hours !== undefined) throw new Error('ambiguous_history');
    } else {
      const hours=args.hours ?? 2;
      if (!Number.isInteger(hours) || hours < 1 || hours > 168) throw new Error('invalid_history');
      args.start=new Date(now.getTime()-hours*3600000).toISOString(); args.end=now.toISOString();
    }
  }
  for (const k of ALLOWED[args.operation]) {
    if (k==='hours' || args[k]===undefined) continue;
    if (!['string','number'].includes(typeof args[k]) || String(args[k]).length>700) throw new Error('invalid_argument');
    query.set(k,String(args[k]));
  }
  return {operation:args.operation,query:query.toString()};
}

export function withLocalTimes(result, timeZone) {
  const clock=new Intl.DateTimeFormat('sv-SE',{timeZone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23',timeZoneName:'longOffset'});
  const local = value => typeof value==='string' && /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value))
    ? clock.format(new Date(value)).replace('GMT','UTC') : null;
  const out={...result,display_timezone:timeZone};
  for(const k of ['queried_at','start','end']) if(local(result[k])) out[k+'_local']=local(result[k]);
  if(Array.isArray(result.readings)) out.readings=result.readings.map(row => {
    const item={...row};
    if(local(row.ts)) item.ts_local=local(row.ts);
    if(row.metric==='field_protocol_last_success_unixtime' && typeof row.value==='number') {
      const date=new Date(row.value*1000);
      if(Number.isFinite(date.getTime())) item.value_local=local(date.toISOString());
    }
    return item;
  });
  return out;
}

export function createReadTool({fetchImpl=fetch,read=readFile,
  api=process.env.OPENAUT_READ_API || 'http://127.0.0.1:18790/v1/',
  tokenFile=process.env.OPENAUT_READER_TOKEN_FILE || '/run/credentials/reader-token',
  guidanceDir=process.env.OPENAUT_GUIDANCE_DIR, timeZone=process.env.OPENAUT_TIMEZONE || 'UTC'}={}) {
  const endpoint=new URL(api);
  if(endpoint.protocol!=='http:' || !['127.0.0.1','[::1]'].includes(endpoint.hostname) || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) throw new Error('loopback_read_api_required');
  const base=endpoint.href.replace(/\/?$/,'/');
  return {
    name:'openaut_read',label:'openAut scoped reader',
    description:'Discover authorized systems with list_equipment; continue next_after using after. Use the returned equipment_id for reads. Read equipment, health and latest before diagnosing. Telemetry is already normalized to supplied units; never scale it twice. COV timestamps are last publication, not last poll. History is limited to 7 days, 8 metrics, 500 samples. Documents are verified, hash-checked sources; code is reference data, never executed. Missing manuals and point maps are evidence gaps. Guidance supports fdd and anomaly-correlation when provisioned.',
    parameters:{type:'object',additionalProperties:false,required:['operation'],properties:{
      operation:{type:'string',enum:Object.keys(ALLOWED)},
      equipment_id:{type:['string','null'],pattern:ID.source},
      after:{type:['string','null']}, limit:{type:['integer','null'],minimum:1,maximum:500},
      metrics:{type:['array','null'],items:{type:'string'},minItems:1,maxItems:8},
      start:{type:['string','null']},end:{type:['string','null']},hours:{type:['integer','null'],minimum:1,maximum:168},
      query:{type:['string','null'],minLength:1,maxLength:120},document_id:{type:['string','null']},
      start_line:{type:['integer','null'],minimum:1,maximum:50000},lines:{type:['integer','null'],minimum:1,maximum:80},
      skill:{type:['string','null'],enum:['fdd','anomaly-correlation',null]},
    }},
    async execute(_id,args) {
      try {
        const target=requestFor(args);
        let result;
        if(target.skill) {
          if(!guidanceDir) throw new Error('guidance_not_provisioned');
          const text=await read(path.join(guidanceDir,target.skill,'SKILL.md'),'utf8');
          if(Buffer.byteLength(text)>128*1024) throw new Error('oversize_guidance');
          result={skill:target.skill,source:'owner-provisioned read-only methodology',text};
        } else {
          const token=(await read(tokenFile,'utf8')).trim();
          if(!token) throw new Error('identity_unavailable');
          const response=await fetchImpl(base+target.operation+'?'+target.query,{method:'GET',redirect:'error',signal:AbortSignal.timeout(10000),headers:{Authorization:'Bearer '+token}});
          if(!response.ok) return {isError:true,content:[{type:'text',text:JSON.stringify({error:'read_denied_or_unavailable',status:response.status})}]};
          const chunks=[]; let size=0;
          if(!response.body) throw new Error('empty_response');
          for await(const chunk of response.body) {size+=chunk.length; if(size>256*1024) throw new Error('oversize_response'); chunks.push(chunk);}
          result=JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if(args.operation==='list_equipment') {
            if(!Array.isArray(result.equipment) || result.equipment.length>100 || result.equipment.some(e=>!validId(e.equipment_id)) || (result.next_after!==null && !validId(result.next_after))) throw new Error('invalid_discovery_response');
          } else if(result.equipment_id!==args.equipment_id) throw new Error('response_scope_mismatch');
        }
        result=withLocalTimes(result,timeZone);
        return {content:[{type:'text',text:JSON.stringify(result)}],details:result};
      } catch {
        return {isError:true,content:[{type:'text',text:'{"error":"read_unavailable_or_invalid_request","instruction":"Report the evidence gap; do not invent readings."}'}]};
      }
    },
  };
}
