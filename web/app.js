// Live Agent integration layered on the visual prototype.
(() => {
  const form=document.querySelector('#plannerForm'), query=document.querySelector('#query');
  const result=document.querySelector('#journey'), hint=document.querySelector('#demoHint');
  const dest=document.querySelector('#destination'), traveler=document.querySelector('#traveler'), days=document.querySelector('#duration');
  let destTouched=false, travelerTouched=false, daysTouched=false;
  dest.addEventListener('change',()=>destTouched=true);
  traveler.addEventListener('change',()=>travelerTouched=true);
  days.addEventListener('change',()=>daysTouched=true);
  const status=document.createElement('p'); status.className='demo-label'; status.id='liveStatus';
  status.textContent='正在检查本地服务…'; hint.replaceWith(status);
  const settings=document.createElement('button'); settings.type='button';settings.textContent='运行模式与模型设置';
  settings.style.cssText='display:block;margin:10px 0 0 auto;border:0;border-bottom:1px solid #506447;background:none;color:#293b30;cursor:pointer';status.after(settings);
  const note=document.createElement('div');note.style.cssText='display:none;max-width:660px;margin:12px 0 0 auto;padding:20px;background:#fffaf0;border:1px solid #c9c8b9;line-height:1.7';settings.after(note);
  note.innerHTML='<form id="modelSettings" autocomplete="off"><label>运行模式 <select name="mode"><option value="offline">离线规则（默认）</option><option value="model">模型辅助</option></select></label><br><label>Base URL <input name="base_url" type="url" placeholder="https://api.example.com/v1" style="width:100%;padding:9px;margin:5px 0 12px"></label><br><label>Model Name <input name="model" type="text" placeholder="模型名称" style="width:100%;padding:9px;margin:5px 0 12px"></label><br><label>API Key <input name="api_key" type="password" placeholder="留空则保留已保存密钥" autocomplete="new-password" style="width:100%;padding:9px;margin:5px 0 12px"></label><br><label><input name="clear_key" type="checkbox"> 清除已保存的密钥</label><p id="keyState">密钥状态：正在读取</p><button type="submit" style="padding:10px 18px;background:#293b30;color:white;border:0;cursor:pointer">保存到本机 .env</button><p id="settingsFeedback" role="status"></p></form><p style="font-size:12px">密钥不会在页面回显；此设置只写入本机项目目录。模型请求失败时 Agent 会回退离线规则，结果区会显示实际情况。</p>';
  settings.onclick=()=>note.style.display=note.style.display==='none'?'block':'none';
  const sf=note.querySelector('#modelSettings'), feedback=note.querySelector('#settingsFeedback'), keyState=note.querySelector('#keyState');let csrf='';
  const modeLabel=v=>status.textContent=v.mode==='model'?'运行模式：模型辅助（失败时回退规则）':'运行模式：离线规则，开箱即用';
  async function refreshSettings(){try{const r=await fetch('/api/settings');if(!r.ok)throw Error('无法读取设置');const v=await r.json();csrf=v.csrf_token;sf.elements.mode.value=v.mode;sf.elements.base_url.value=v.base_url||'';sf.elements.model.value=v.model||'';sf.elements.api_key.value='';keyState.textContent=v.has_key?'密钥状态：已配置（不会回显）':'密钥状态：未配置';modeLabel(v)}catch(e){status.textContent='本地服务未启动';feedback.textContent=e.message}}
  refreshSettings();
  sf.addEventListener('submit',async e=>{e.preventDefault();feedback.textContent='正在保存…';const payload={mode:sf.elements.mode.value,base_url:sf.elements.base_url.value,model:sf.elements.model.value,api_key:sf.elements.api_key.value,clear_key:sf.elements.clear_key.checked};try{const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)});const v=await r.json();if(!r.ok)throw Error(v.error||'保存失败');sf.elements.api_key.value='';sf.elements.clear_key.checked=false;keyState.textContent=v.has_key?'密钥状态：已配置（不会回显）':'密钥状态：未配置';modeLabel(v);feedback.textContent='已保存到本机 .env，下一次规划立即生效。'}catch(e){feedback.textContent=e.message}});
  const noResult=document.querySelector('#noResult'), button=form.querySelector('.submit');
  const el=(tag,cls,value)=>{const e=document.createElement(tag);e.className=cls||'';e.textContent=value||'';return e};
  function message(title,body){result.classList.remove('visible');noResult.replaceChildren(el('strong','',title),el('span','',body));noResult.classList.add('visible');noResult.scrollIntoView({behavior:'smooth'})}
  function requestText(){let s=query.value.trim();if(!s)return '';
    if(destTouched&&dest.value&&!s.includes(dest.value))s+='；目的地'+dest.value;
    if(travelerTouched&&traveler.value==='老人同行'&&!s.includes('老人'))s+='；带老人';
    if(travelerTouched&&traveler.value==='亲子同行'&&!/亲子|孩子|一家三口/.test(s))s+='；亲子同行';
    if(travelerTouched&&traveler.value==='情侣同行'&&!s.includes('情侣'))s+='；情侣同行';
    if(daysTouched&&days.value==='两日'&&!/两天|两日/.test(s))s+='；玩两天';return s}
  function render(data){const p=data.plan||{};if(!p.found){message(p.need_clarification?'请补充需求':'暂未找到路线',p.clarify_message||p.message||p.summary||'请调整输入');return}
    noResult.classList.remove('visible');result.classList.add('visible');
    document.querySelector('#resultTitle').textContent=`${p.scenic} · ${p.duration} 日`;
    const llm=data.llm||{};const modelUsed=(llm.successful_responses||0)>0;
    document.querySelector('#resultSub').textContent=`${p.visitor_type} · ${modelUsed?'模型参与':data.provider==='offline-rules'?'离线规则':'模型未成功，规则回退'} · ${data.tool_call_count} 次图谱工具调用`;
    document.querySelector('.route-top h3').textContent=`${p.scenic}行程`;
    const timeline=result.querySelector('.timeline');timeline.replaceChildren();let n=0;
    for(const day of p.days||[])for(const sec of day.sections||[]){const part=el('div','period');part.append(el('div','period-title',`第${day.day}天 ／ ${sec.period}`));const list=el('div','step-list');for(const step of sec.steps||[]){n++;const row=el('div','step');row.append(el('span','step-no',String(step.order||n).padStart(2,'0')),el('span','step-name',step.spot||step.label),el('span','step-state',step.period_status||''));list.append(row)}part.append(list);timeline.append(part)}
    result.querySelector('.route-count').textContent=`${n} 步`;
    let summary=result.querySelector('#liveSummary');if(!summary){summary=el('p','');summary.id='liveSummary';summary.style.cssText='white-space:pre-wrap;line-height:1.8;margin:24px 0';timeline.after(summary)}summary.textContent=p.summary||'';
    result.querySelector('.route-note').textContent=p.period_note||'路线来自项目图谱；当前通行未核验。';
    const trace=result.querySelector('.trace-list');trace.replaceChildren();for(const [i,t] of (data.traces||[]).entries()){const row=el('li','trace-item');const body=el('div');body.append(el('h4','',({thought:'思考',action:'工具调用',observation:'观察',final:'最终建议',note:'回退说明'})[t.type]||t.type),el('p','',t.type==='action'?`${t.tool} ${JSON.stringify(t.args)}`:t.content));row.append(el('span','trace-icon',String(i+1).padStart(2,'0')),body);trace.append(row)}
    const list=result.querySelector('.evidence-list');list.replaceChildren();for(const id of (p.evidence_ids||[]).slice(0,12)){const b=el('button','evidence-id',id);b.type='button';list.append(b)}result.querySelector('.evidence-title span').textContent=`${(p.evidence_ids||[]).length} 条证据`;
    result.querySelector('.caveat span').textContent='当前开放、票价和通行情况未核验。'+(p.warnings||[]).join('；');result.scrollIntoView({behavior:'smooth'})}
  form.addEventListener('submit',async event=>{event.preventDefault();event.stopImmediatePropagation();const text=requestText();if(!text){message('请补充需求','输入目的地或同行人群');return}button.disabled=true;button.classList.add('loading');try{const response=await fetch('/api/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:text})});const data=await response.json();if(!response.ok)throw Error(data.error||'服务异常');render(data)}catch(error){message('规划暂不可用',error.message)}finally{button.disabled=false;button.classList.remove('loading')}},true);
  document.querySelector('.graph-notice').textContent='搜索覆盖实验六完整图谱的 471 个节点与 629 条关系；画布按查询展示局部连接，规划表单会实时调用本地 Agent。';
  document.querySelector('.footer span:last-child').textContent='本地 Web 交互入口 · 当前开放与通行情况未核验';
})();
