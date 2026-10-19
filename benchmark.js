(() => {
  'use strict';
  const engines = [{id:'deepseek',name:'DeepSeek'},{id:'metaso',name:'秘塔搜索'},{id:'bocha',name:'Bocha'},{id:'tavily',name:'Tavily'},{id:'exa',name:'Exa'}];
  const questions = ['Python 官方文档中，asyncio.TaskGroup 与 gather 的异常处理有什么区别？','Visual Studio Code 官方下载是否收费，其源码使用什么许可证？','SQLite 官方说明，什么情况下适合使用 SQLite，什么情况下应选择客户端服务器数据库？','Attention Is All You Need 原论文中，base 模型在 WMT 2014 英德翻译上的 BLEU 分数是多少？','世界卫生组织建议成年人每周进行多少分钟中等强度有氧运动？','中华人民共和国个人信息保护法第十三条规定了哪些处理个人信息的情形？'];
  const $ = id => document.getElementById(id);
  const state = {token:null,available:[],run:null,running:false,sort:null,direction:1,detail:null};
  let cancelCurrent = null;
  let toastTimer;
  const create = (tag,text,className) => { const node=document.createElement(tag); if(text!==undefined)node.textContent=text; if(className)node.className=className; return node; };
  const option = (value,label) => { const node=create('option',label); node.value=value; return node; };
  function notify(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{$('toast').hidden=true;},4000);}
  function clearFields(){document.querySelectorAll('[data-key]').forEach(input=>{input.value='';});}
  function error(message){$('config-error').textContent=message;$('config-error').hidden=!message;}
  function formValues(){return {providers:engines.filter(e=>$('choose-'+e.id).checked).map(e=>e.id),questions:$('config-questions').value.split(/\r?\n/).map(q=>q.trim()).filter(Boolean),top_k:Number($('config-topk').value),language:$('config-language').value,domain:$('config-domain').value};}
  function estimate(){const c=formValues();$('request-estimate').textContent=`${c.questions.length} 道题 × ${c.providers.length} 个引擎 = ${c.questions.length*c.providers.length} 次 API 请求，可能产生厂商费用。`;engines.forEach(e=>{$('key-'+e.id).disabled=!$('choose-'+e.id).checked||state.running;});}
  async function connect(){
    if(state.running)return;
    state.token=null;state.available=[];$('start-run').disabled=true;$('connection-status').textContent='正在连接本地执行服务…';
    try{
      if(!['localhost','127.0.0.1','[::1]'].includes(location.hostname)||!['http:','https:'].includes(location.protocol))throw new Error('local');
      const response=await fetch('/api/health',{cache:'no-store',credentials:'omit',redirect:'error'});const health=await response.json();
      if(!response.ok||health.ok!==true||typeof health.csrf_token!=='string'||!Array.isArray(health.providers))throw new Error('health');
      state.token=health.csrf_token;state.available=health.providers.filter(id=>engines.some(e=>e.id===id));$('connection-status').textContent=`本机服务已连接 · ${state.available.length} 个引擎`;$('start-run').disabled=!state.available.length;
    }catch{$('connection-status').textContent='无法连接。请启动本地 benchmark_server.py，再通过本机网址打开此页。';}
  }
  function matchesRun(){return state.run&&($('filter-language').value==='all'||$('filter-language').value===state.run.config.language)&&($('filter-domain').value==='all'||$('filter-domain').value===state.run.config.domain);}
  const percentile=(values,p)=>values.length?[...values].sort((a,b)=>a-b)[Math.max(0,Math.ceil(p*values.length)-1)]:null;
  function metrics(engine){
    const records=matchesRun()?state.run.records.filter(r=>r.provider===engine.id):[];
    const success=records.filter(r=>r.status==='success');const results=success.flatMap(r=>r.results);
    const relevanceComplete=results.length>0&&results.every(r=>r.review.relevance!==null);
    const pollutionComplete=results.length>0&&results.every(r=>r.review.pollution!=='unknown');
    const coverageComplete=success.length>0&&success.every(r=>r.coverage.value!==null&&r.coverage.basis.trim());
    const times=records.filter(r=>r.status!=='cancelled'&&Number.isFinite(r.elapsed_ms)).map(r=>r.elapsed_ms);
    return {...engine,records,attempts:records.length,success:success.length,failed:records.filter(r=>r.status==='failed').length,cancelled:records.filter(r=>r.status==='cancelled').length,empty:success.filter(r=>!r.results.length).length,returned:results.length,
      bodyRate:results.length?100*results.filter(r=>r.content.trim()).length/results.length:null,
      quality:relevanceComplete?100*results.filter(r=>r.review.relevance>=2).length/results.length:null,
      pollution:pollutionComplete?100*results.filter(r=>r.review.pollution!=='none').length/results.length:null,
      coverage:coverageComplete?success.reduce((sum,r)=>sum+r.coverage.value,0)/success.length:null,
      latency:percentile(times,.5),p95:percentile(times,.95),relevanceReviewed:results.filter(r=>r.review.relevance!==null).length,pollutionReviewed:results.filter(r=>r.review.pollution!=='unknown').length,coverageReviewed:success.filter(r=>r.coverage.value!==null&&r.coverage.basis.trim()).length};
  }
  const percent=value=>value===null?'待标注':value.toFixed(1)+'%';
  const time=value=>value===null?'—':(value/1000).toFixed(2)+'s';
  function renderSummary(){
    const rows=engines.map(metrics);
    if(state.sort)rows.sort((a,b)=>a[state.sort]===null?(b[state.sort]===null?0:1):b[state.sort]===null?-1:(a[state.sort]-b[state.sort])*state.direction);
    $('engine-body').replaceChildren();$('trust-rows').replaceChildren();
    rows.forEach(row=>{
      const tr=create('tr');const nameCell=create('td');const name=create('span',row.name,'engine');const observedMode=row.records.find(r=>r.provider_mode);name.append(create('small',observedMode?observedMode.provider_mode:'等待实际模式'));nameCell.append(name);tr.append(nameCell);
      [`${row.attempts} / ${row.success} / ${row.failed} / ${row.empty}`,percent(row.quality),percent(row.coverage),percent(row.pollution),`${time(row.latency)} / ${time(row.p95)}`,`${row.returned} / ${row.bodyRate===null?'—':row.bodyRate.toFixed(1)+'%'}`,'未核算'].forEach(value=>tr.append(create('td',value)));
      const cell=create('td');const button=create('button','查看 ↗');button.type='button';button.setAttribute('aria-label',`查看 ${row.name} 详情`);button.addEventListener('click',()=>{state.detail=row.id;renderDetail();$('detail-title').focus();});cell.append(button);tr.append(cell);$('engine-body').append(tr);
      const trust=create('div',undefined,'trust-item');trust.append(create('h3',row.name),create('p',`污染曝光 ${percent(row.pollution)}`),create('p',`证据覆盖 ${percent(row.coverage)}`),create('p',`污染已标 ${row.pollutionReviewed}/${row.returned} · 覆盖 ${row.coverageReviewed}/${row.success}`,'muted small'));$('trust-rows').append(trust);
    });
    $('dataset-label').textContent=!state.run?'尚无实测数据':!matchesRun()?'当前筛选无数据':`${state.run.config.questions.length} 题 · Top ${state.run.config.top_k} · ${state.run.status==='running'?'运行中':state.run.status==='cancelled'?'已取消（部分结果）':'已完成'}`;
    document.querySelectorAll('th[data-col]').forEach(th=>th.setAttribute('aria-sort',th.dataset.col===state.sort?(state.direction===1?'ascending':'descending'):'none'));
    if(state.detail)renderDetail();
  }
  function renderDetail(){
    const row=metrics(engines.find(e=>e.id===state.detail));$('engine-detail').hidden=false;$('detail-title').textContent=row.name+' · 本轮统计';$('detail-grid').replaceChildren();
    [['请求',`${row.attempts} 次尝试，${row.cancelled} 次中止`],['相关性标注',`${row.relevanceReviewed} / ${row.returned} 条`],['污染标注',`${row.pollutionReviewed} / ${row.returned} 条`],['覆盖标注',`${row.coverageReviewed} / ${row.success} 题`]].forEach(([label,value])=>{const group=create('div');group.append(create('dt',label),create('dd',value));$('detail-grid').append(group);});
    $('detail-description').textContent='延迟为已结束且有耗时的请求（包括失败，排除取消）的最近秩分位数。可用文本率为返回结果中 content 非空的占比；各家原生摘要与正文长度、语义不同，不能当作统一全文。质量指标仅描述已返回结果；失败、空结果、取消与未尝试需结合执行统计判断。费用未按厂商账单核算。';
  }
  function safeURL(value){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;}catch{return null;}}
  function renderEvidence(side){
    const host=$(side+'-evidence');host.replaceChildren();host.className='';
    if(!state.run){host.append(create('p','尚无搜索结果','empty'));return;}
    const provider=$(side+'-engine').value;const questionIndex=Number($('case-select').value);const record=state.run.records.find(r=>r.provider===provider&&r.question_index===questionIndex);
    if(!record){host.append(create('p',state.running?'尚未请求此问题。':'本题尚未尝试。','empty'));return;}
    host.append(create('p',`${record.started_at} · ${record.status} · ${time(record.elapsed_ms)} · Top ${state.run.config.top_k}`,'source-meta'));
    if(record.status==='pending')host.append(create('p','正在等待厂商返回…','empty'));
    else if(record.status!=='success')host.append(create('p',record.error?.message||'请求已中止，已发送的请求仍可能计费。','error'));
    else{
      const coverage=create('div',undefined,'coverage');const row=create('label',undefined,'coverage-row');row.append(create('span','证据覆盖（0–100%）','small'));
      const input=create('input');input.type='number';input.min='0';input.max=record.results.length?'100':'0';input.readOnly=!record.results.length;input.step='1';input.value=record.coverage.value===null?'':record.coverage.value;input.setAttribute('aria-label','本题证据覆盖百分比');
      input.addEventListener('input',()=>{const value=Number(input.value);record.coverage.value=input.value!==''&&Number.isFinite(value)&&value>=0&&value<=100?value:null;renderSummary();});row.append(input);
      const basis=create('textarea');basis.placeholder='核验依据：正确事实、参考来源与仍缺失的证据';basis.maxLength=5000;basis.value=record.coverage.basis;basis.setAttribute('aria-label','证据覆盖核验依据');basis.addEventListener('input',()=>{record.coverage.basis=basis.value;renderSummary();});coverage.append(row,basis);host.append(coverage);
      if(!record.results.length)host.append(create('p','API 请求成功，但未返回结果。空结果不记为零污染或满分。','warning small'));
      record.results.forEach(result=>{
        const card=create('article',undefined,'result-card');card.append(create('div',`RESULT ${result.rank} · ${result.site_name||'未提供站点'}${result.published_at?' · '+result.published_at:''}`,'source-meta'),create('h4',result.title||'无标题'));
        const url=safeURL(result.url);if(url){const link=create('a',result.url,'source-url');link.href=url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}else card.append(create('span',result.url||'未提供 URL','source-url muted'));
        card.append(create('p',result.snippet||'未提供摘要'));
        if(result.content){const details=create('details');details.append(create('summary',result.content_kind==='body'?'查看返回正文':result.content_kind==='summary'?'查看返回摘要':'查看原生返回文本'),create('p',result.content));card.append(details);}
        const annotation=create('div',undefined,'annotation');const relevanceLabel=create('label','相关性');const relevance=create('select');relevance.setAttribute('aria-label',`结果 ${result.rank} 相关性`);
        [['','待标注'],['0','0 · 不相关'],['1','1 · 主题相关'],['2','2 · 部分回答'],['3','3 · 直接回答']].forEach(([value,label])=>relevance.append(option(value,label)));relevance.value=result.review.relevance===null?'':String(result.review.relevance);relevance.addEventListener('change',()=>{result.review.relevance=relevance.value===''?null:Number(relevance.value);renderSummary();});relevanceLabel.append(relevance);
        const pollutionLabel=create('label','污染判定');const pollution=create('select');pollution.setAttribute('aria-label',`结果 ${result.rank} 污染判定`);[['unknown','未判定'],['none','无污染'],['seo','SEO 作弊'],['geo','GEO 操纵'],['low_quality','低质内容']].forEach(([value,label])=>pollution.append(option(value,label)));pollution.value=result.review.pollution;pollution.addEventListener('change',()=>{result.review.pollution=pollution.value;renderSummary();});pollutionLabel.append(pollution);annotation.append(relevanceLabel,pollutionLabel);card.append(annotation);host.append(card);
      });
    }
    const raw=create('details');raw.append(create('summary','原始响应与执行参数'));raw.append(create('pre',JSON.stringify({provider:record.provider,query:record.query,top_k:state.run.config.top_k,mode:record.mode,provider_mode:record.provider_mode,params:record.params,started_at:record.started_at,ended_at:record.ended_at,bridge_http_status:record.bridge_http_status,provider_http_status:record.http_status??'未提供',usage:record.usage,raw:record.raw,error:record.error},null,2)));host.append(raw);
  }
  function renderCases(){['left','right'].forEach(renderEvidence);}
  function setupCases(){
    const select=$('case-select');select.replaceChildren();state.run.config.questions.forEach((q,i)=>select.append(option(String(i),`${i+1}. ${q}`)));select.disabled=false;
    ['left','right'].forEach((side,i)=>{const select=$(side+'-engine');select.replaceChildren();state.run.config.providers.forEach(id=>select.append(option(id,engines.find(e=>e.id===id).name)));select.value=state.run.config.providers[Math.min(i,state.run.config.providers.length-1)];});
  }
  function exportRecord(record){return {provider:record.provider,question_index:record.question_index,query:record.query,status:record.status,started_at:record.started_at,ended_at:record.ended_at,elapsed_ms:record.elapsed_ms,mode:record.mode,provider_mode:record.provider_mode,params:record.params,http_status:record.http_status,bridge_http_status:record.bridge_http_status,error:record.error&&{code:record.error.code,message:record.error.message},results:record.results.map(r=>({rank:r.rank,title:r.title,url:r.url,snippet:r.snippet,content:r.content,content_kind:r.content_kind,published_at:r.published_at,site_name:r.site_name,review:{relevance:r.review.relevance,pollution:r.review.pollution}})),coverage:{value:record.coverage.value,basis:record.coverage.basis},usage:record.usage,cost:null,raw:record.raw};}
  function exportSnapshot(caseOnly){
    if(!state.run)return;const c=state.run.config;const records=state.run.records.filter(r=>!caseOnly||r.question_index===Number($('case-select').value));
    const payload={schema_version:'1.0',is_simulated:false,generated_at:new Date().toISOString(),run:{id:state.run.id,status:state.run.status,started_at:state.run.started_at,ended_at:state.run.ended_at,config:{providers:[...c.providers],questions:[...c.questions],top_k:c.top_k,language:c.language,domain:c.domain,track:'search',mode:'provider_default',auto_retry:false}},metric_definitions:{relevance:'Returned results with manual grade >= 2 / all returned results; pending until all returned results graded.',pollution:'Returned results manually labelled seo/geo/low_quality / all returned results; pending until all judged.',coverage:'Mean manual per-question coverage with written verification basis; pending until all successful requests reviewed. Successful empty responses have fixed zero coverage.',latency:'Nearest-rank p50/p95 elapsed milliseconds over completed requests with timing, including failures and excluding cancellations.',available_text:'Nonempty content / returned results. Provider-native summaries and bodies are not equivalent full text.',costs:'Not calculated. No provider invoice reconciliation.',limitations:'Non-blind manual review. No nDCG, web recall, or statistical significance. Missing results are not clean results.'},records:records.map(exportRecord)};
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const link=create('a');link.href=url;link.download=`searchbench-${state.run.id}${caseOnly?'-question-'+(Number($('case-select').value)+1):''}.json`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('已导出真实结果、参数与人工标注。');
  }
  async function startRun(event){
    event.preventDefault();if(state.running)return;error('');const config=formValues();
    if(!state.token){error('请先连接本地执行服务。');return;}
    if(!config.providers.length){error('请至少选择一个引擎。');return;}
    if(config.providers.some(id=>!state.available.includes(id))){error('所选引擎当前不可用，请重新连接或取消选择。');return;}
    if(!config.questions.length||config.questions.length>20||config.questions.some(q=>[...q].length>128)){error('请填写 1–20 道题，每题不超过 128 字符。');return;}
    if(state.run&&!$('replace-confirm').checked){error('请先确认清除当前结果与标注。');return;}
    if(config.providers.some(id=>!$('key-'+id).value.trim())){error('请为每个选中引擎填写本轮 API Key。');return;}
    const keys=new Map(config.providers.map(id=>[id,$('key-'+id).value.trim()]));clearFields();
    const controller=new AbortController();const cleanupKeys=()=>{keys.clear();clearFields();};cancelCurrent=()=>{controller.abort();cleanupKeys();};
    // Scrub echoes before any provider-controlled text reaches state, DOM or export.
    function scrub(value){
      if(typeof value==='string'){let safe=value;keys.forEach(key=>{if(key)safe=safe.split(key).join('[REDACTED]');});return safe;}
      if(Array.isArray(value))return value.map(scrub);
      if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,item])=>[scrub(key),scrub(item)]));
      return value;
    }
    state.running=true;state.run={id:new Date().toISOString().replace(/[:.]/g,'-'),started_at:new Date().toISOString(),ended_at:null,status:'running',config,records:[]};
    $('run-fields').disabled=true;$('start-run').disabled=true;$('cancel-run').hidden=false;$('cancel-run').disabled=false;$('reconnect').disabled=true;$('replace-warning').hidden=true;$('replace-confirm').checked=false;$('export-data').disabled=false;$('export-case').disabled=false;$('run-progress').max=config.questions.length*config.providers.length;$('run-progress').value=0;setupCases();renderSummary();renderCases();let completed=0;
    async function search(provider,query,questionIndex){
      if(controller.signal.aborted)return;const started=performance.now();const record={provider,query,question_index:questionIndex,status:'pending',started_at:new Date().toISOString(),ended_at:null,elapsed_ms:null,mode:'default',provider_mode:null,params:null,http_status:null,bridge_http_status:null,results:[],error:null,usage:null,raw:null,coverage:{value:null,basis:''}};state.run.records.push(record);
      try{
        const response=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json','X-Benchmark-Token':state.token},credentials:'omit',cache:'no-store',redirect:'error',signal:controller.signal,body:JSON.stringify({provider,key:keys.get(provider),query,top_k:config.top_k})});
        const data=scrub(await response.json());
        if(!response.ok||data.ok!==true){record.status='failed';record.error={code:typeof data.error?.code==='string'?data.error.code:'request_failed',message:typeof data.error?.message==='string'?data.error.message:'请求失败，请检查 Key、额度或服务连接。'};}
        else if(!Array.isArray(data.results)){record.status='failed';record.error={code:'invalid_response',message:'执行服务返回格式异常。'};}
        else{record.status='success';record.mode=typeof data.mode==='string'?data.mode:'default';record.provider_mode=typeof data.provider_mode==='string'?data.provider_mode:null;record.params=data.params??null;record.results=data.results.slice(0,config.top_k).map((r,i)=>({rank:i+1,...Object.fromEntries(['title','url','snippet','content','content_kind','published_at','site_name'].map(field=>[field,typeof r[field]==='string'?r[field]:''])),review:{relevance:null,pollution:'unknown'}}));record.raw=data.raw??null;record.usage=data.usage??null;if(!record.results.length)record.coverage={value:0,basis:'厂商请求成功但未返回搜索结果，本题没有可用证据，覆盖率固定为 0。'};}
        record.bridge_http_status=response.status;record.http_status=Number.isInteger(data.http_status)?data.http_status:null;record.elapsed_ms=Number.isFinite(data.elapsed_ms)?data.elapsed_ms:performance.now()-started;
      }catch{record.status=controller.signal.aborted?'cancelled':'failed';record.error={code:controller.signal.aborted?'cancelled':'network_error',message:controller.signal.aborted?'本轮已取消。已发送请求仍可能计费。':'网络或执行服务错误，未自动重试。'};record.elapsed_ms=performance.now()-started;}
      finally{record.ended_at=new Date().toISOString();completed+=1;$('run-progress').value=completed;$('run-status').textContent=`已结束 ${completed} / ${$('run-progress').max} 次请求 · 第 ${questionIndex+1} 题`;renderSummary();renderCases();}
    }
    try{for(let i=0;i<config.questions.length&&!controller.signal.aborted;i+=1){$('run-status').textContent=`第 ${i+1} / ${config.questions.length} 题 · 并行请求 ${config.providers.length} 个引擎`;await Promise.all(config.providers.map(provider=>search(provider,config.questions[i],i)));}}
    finally{cleanupKeys();cancelCurrent=null;state.running=false;state.run.status=controller.signal.aborted?'cancelled':'completed';state.run.ended_at=new Date().toISOString();$('run-fields').disabled=false;$('start-run').disabled=!state.token;$('cancel-run').hidden=true;$('reconnect').disabled=false;$('replace-warning').hidden=false;$('run-status').textContent=`${controller.signal.aborted?'已取消':'测评完成'} · 已结束 ${completed} / ${config.questions.length*config.providers.length} 次请求 · Key 已从输入框与本轮引用中清除。${controller.signal.aborted?' 已发送的请求仍可能计费。':''}`;estimate();renderSummary();renderCases();}
  }
  engines.forEach(engine=>{
    const field=create('div',undefined,'provider-field');const label=create('label');const check=create('input');check.type='checkbox';check.id='choose-'+engine.id;check.checked=true;label.append(check,create('span',engine.name));
    const key=create('input');key.type='password';key.id='key-'+engine.id;key.dataset.key=engine.id;key.autocomplete='off';key.spellcheck=false;key.setAttribute('autocapitalize','off');key.setAttribute('data-lpignore','true');key.setAttribute('data-1p-ignore','');key.placeholder='本轮 API Key';key.setAttribute('aria-label',engine.name+' 本轮 API Key');check.addEventListener('change',()=>{if(!check.checked)key.value='';estimate();});field.append(label,key);if(engine.id==='metaso')field.append(create('p','响应适配待实测；结构异常不会计为空结果。','note small'));$('config-engines').append(field);
  });
  $('config-questions').value=questions.join('\n');['config-questions','config-topk'].forEach(id=>$(id).addEventListener('input',estimate));['filter-language','filter-domain'].forEach(id=>$(id).addEventListener('change',renderSummary));
  ['left','right'].forEach((side,index)=>{engines.forEach(engine=>$(side+'-engine').append(option(engine.id,engine.name)));$(side+'-engine').value=engines[index].id;$(side+'-engine').addEventListener('change',()=>renderEvidence(side));});
  $('case-select').addEventListener('change',renderCases);$('config-form').addEventListener('submit',startRun);$('cancel-run').addEventListener('click',()=>{if(cancelCurrent){cancelCurrent();$('run-status').textContent='正在取消。已发送的请求仍可能计费。';$('cancel-run').disabled=true;}});
  $('new-run').addEventListener('click',()=>{$('experiment-config').scrollIntoView({behavior:'smooth'});$('config-title').focus({preventScroll:true});});$('close-detail').addEventListener('click',()=>{state.detail=null;$('engine-detail').hidden=true;});$('reconnect').addEventListener('click',connect);$('export-data').addEventListener('click',()=>exportSnapshot(false));$('export-case').addEventListener('click',()=>exportSnapshot(true));
  document.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{const key=button.dataset.sort;state.direction=state.sort===key?-state.direction:['pollution','latency'].includes(key)?1:-1;state.sort=key;renderSummary();}));
  window.addEventListener('pagehide',()=>{if(cancelCurrent)cancelCurrent();clearFields();});estimate();renderSummary();renderCases();connect();
})();
