/* AutoRSE descriptive cost and task-profile views. No prices or scores are imputed. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{root.AutoRSEInsightsCore=api;if(typeof document!=='undefined')api.mount(root);}
})(typeof globalThis==='object'?globalThis:this,function(){
  'use strict';
  const numeric=value=>typeof value==='number'&&Number.isFinite(value);
  const cost=value=>numeric(value)&&value>=0;
  const colors=['#3155d8','#0c8975','#8551b7','#bd623c','#bd477b','#467da5','#60738d'];
  const shapes=['circle','diamond','square','triangle','cross','hexagon','triangle-down'];
  function costRows(data,cohort='paper',scope='TIGER',board=null){
    const sourceCohort=data?.cohort||data?.metadata?.cohort||'paper';
    const compatible=sourceCohort===cohort;
    const records=compatible&&Array.isArray(data?.scopes?.[scope]?.rows)?data.scopes[scope].rows:[];
    const originals=Array.isArray(board?.rows)?board.rows:records;
    const byId=new Map(records.filter(row=>row&&typeof row.id==='string').map(row=>[row.id,row]));
    return originals.map(original=>{
      const found=byId.get(original.id),valid=!!found&&cost(found.cost_usd)&&numeric(found.score)&&
        (scope!=='overall'||found.covered_tasks===6);
      const expected=scope==='overall'?(original.trial_counts||[]).reduce((sum,n)=>sum+(Number.isInteger(n)&&n>0?n:0),0):
        original.trial_counts?.[(board?.task_order||board?.tasks?.map(task=>task.name)||[]).indexOf(scope)]||0;
      return {...(found||{}),id:original.id,model:original.model,harness:original.harness,
        cost_usd:valid?found.cost_usd:null,score:valid?found.score:null,
        score_sd:valid&&numeric(found.score_sd)&&found.score_sd>=0?found.score_sd:null,
        cost_sd:valid&&numeric(found.cost_sd)&&found.cost_sd>=0?found.cost_sd:null,
        recorded_runs:found?.recorded_runs||0,total_runs:found?.total_runs||expected,
        status:valid?found.status||'complete':'unavailable',available:valid};
    });
  }
  function dominatedBy(row,selected){
    return !!row&&!!selected&&cost(row.cost_usd)&&cost(selected.cost_usd)&&numeric(row.score)&&numeric(selected.score)&&
      row.cost_usd>=selected.cost_usd&&row.score<=selected.score&&
      (row.cost_usd>selected.cost_usd||row.score<selected.score);
  }
  function paretoFrontier(rows){
    const known=rows.filter(row=>row.available!==false&&cost(row.cost_usd)&&numeric(row.score));
    return known.filter(row=>!known.some(other=>dominatedBy(row,other))).sort((a,b)=>a.cost_usd-b.cost_usd||b.score-a.score||String(a.id).localeCompare(String(b.id)));
  }
  function costRanking(rows){
    const ranked=rows.filter(row=>row.available!==false&&cost(row.cost_usd)).map(row=>({...row})).sort((a,b)=>a.cost_usd-b.cost_usd||String(a.id).localeCompare(String(b.id)));
    let previous,rank;
    ranked.forEach((row,index)=>{if(index===0||row.cost_usd!==previous)rank=index+1;previous=row.cost_usd;row.rank=rank;});
    return {ranked,missing:rows.filter(row=>row.available===false||!cost(row.cost_usd)).map(row=>({...row}))};
  }
  function normalizationReferences(board){
    const tasks=board?.tasks||[],rows=board?.rows||[];
    return tasks.map((_,i)=>{const values=rows.map(row=>row.scores?.[i]).filter(value=>numeric(value)&&value>=0);return values.length?Math.max(...values):null;});
  }
  function profileData(board,selectedIds){
    const references=normalizationReferences(board),selected=new Set(selectedIds||[]);
    return {tasks:(board?.tasks||[]).map((task,i)=>({name:task.name,metric:task.metric,reference:references[i]})),
      series:(board?.rows||[]).filter(row=>selected.has(row.id)).map(row=>({id:row.id,model:row.model,harness:row.harness,
        values:references.map((reference,i)=>numeric(reference)&&reference>0&&numeric(row.scores?.[i])?row.scores[i]/reference*100:null),
        raw:references.map((_,i)=>numeric(row.scores?.[i])?row.scores[i]:null),
        sd:references.map((_,i)=>numeric(row.sd?.[i])?row.sd[i]:null),trials:references.map((_,i)=>row.trial_counts?.[i]??null)}))};
  }
  function formatCost(value){
    if(!cost(value))return 'N/A';
    if(value===0)return '$0.000';
    if(value<.001)return '$'+value.toPrecision(3);
    return '$'+value.toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:3});
  }
  function mount(root){
    const host=document.getElementById('insights-panel');if(!host)return;
    const NS='http://www.w3.org/2000/svg',$=id=>document.getElementById(id);
    const html=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
    const svg=(tag,attributes={},text)=>{const node=document.createElementNS(NS,tag);for(const [key,value]of Object.entries(attributes))node.setAttribute(key,String(value));if(text!==undefined)node.textContent=text;return node;};
    host.innerHTML='<div class="insights"><div class="insights-header"><div><h2>Performance, in perspective.</h2><p>Explore logged API cost and compare six-task strengths within the selected results cohort.</p></div><label class="insights-scope" for="insights-scope">Cost scope <select id="insights-scope"><option value="TIGER">TIGER</option><option value="HSTU">HSTU</option><option value="IntSR">IntSR</option><option value="OneTrans">OneTrans</option><option value="RankMixer">RankMixer</option><option value="WuKong">WuKong</option><option value="overall">All six tasks</option></select></label></div><div class="insights-grid"><section class="insight-card" aria-labelledby="quality-title"><h3 id="quality-title">Quality vs. cost · TIGER</h3><p class="chart-note" id="quality-note"></p><div id="quality-coverage" class="chart-coverage"></div><div id="quality-chart" class="chart-region"></div><div id="quality-legend" class="scatter-legend"></div><p id="quality-selection" class="chart-selection" aria-live="polite"></p></section><section class="insight-card" aria-labelledby="cost-title"><h3 id="cost-title">Cost, ranked · TIGER</h3><p class="chart-note">Mean recorded API cost per research run (USD), cheapest first. Hover or focus for coverage and paired results.</p><div id="cost-chart" class="chart-region"></div></section><section class="insight-card profile-card" aria-labelledby="profile-title"><div class="profile-heading"><div><h3 id="profile-title">Six-task profile</h3><p class="chart-note">Compare 2–3 configurations. Each axis is scaled to the best reported mean in this cohort (100); hover or focus for the original score.</p></div></div><div id="profile-content"></div></section></div><div class="insights-footer"><p>Logged API estimates; GPU and hosting costs excluded. The frontier describes observed means, not statistical significance.</p><a href="insights-data.json" download>Chart data JSON ↗</a><a href="paper-run-resources.csv" download>Run-level CSV ↗</a></div><p id="insights-data-status" class="insights-data-status"></p></div>';
    let state=root.AutoRSELeaderboardState||null,data=null,scope='TIGER',selectedPoint=null,profileSelection=[],activeCohort=null,lastChartWidth=0,resizeQueued=false;
    const initialParams=new URLSearchParams(location.search);
    let activeTab=initialParams.get('tab')==='insights'||location.hash==='#insights'?'insights':'table';
    function resize(){root.dispatchEvent(new Event('resize'));}
    function tab(value,writeUrl=true){
      activeTab=value;
      $('table-panel').hidden=value!=='table';host.hidden=value!=='insights';
      const toggle=document.querySelector('.view-toggle');if(toggle)toggle.hidden=value!=='table';
      for(const name of ['table','insights']){const button=$(name+'-tab');button.setAttribute('aria-selected',String(value===name));button.tabIndex=value===name?0:-1;}
      if(writeUrl){const url=new URL(location.href);if(value==='insights')url.searchParams.set('tab','insights');else url.searchParams.delete('tab');if(url.hash==='#insights')url.hash='';history.replaceState(null,'',url.pathname+url.search+url.hash);}
      if(value==='insights'&&state){renderCosts();profile();}
      resize();
    }
    for(const name of ['table','insights']){
      $(name+'-tab').addEventListener('click',()=>tab(name));
      $(name+'-tab').addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'table':event.key==='End'?'insights':name==='table'?'insights':'table';tab(next);$(next+'-tab').focus();}});
    }
    root.addEventListener('popstate',()=>tab(new URLSearchParams(location.search).get('tab')==='insights'||location.hash==='#insights'?'insights':'table',false));
    $('insights-scope').addEventListener('change',event=>{scope=event.target.value;selectedPoint=null;renderCosts();});
    function styleFor(id){const ids=(state?.boards?.[state.cohort]?.rows||[]).map(row=>row.id).sort(),index=Math.max(0,ids.indexOf(id));return {color:colors[index%colors.length],shape:shapes[index%shapes.length],dash:['','7 4','2 4','8 3 2 3','4 3','10 4','2 2 8 2'][index%7]};}
    function marker(parent,cx,cy,size,style,extra={}){
      const attrs={fill:style.color,stroke:style.color,'stroke-width':1.3,...extra};let point;
      if(style.shape==='square')point=svg('rect',{x:cx-size,y:cy-size,width:size*2,height:size*2,rx:1,...attrs});
      else if(style.shape==='diamond')point=svg('path',{d:`M${cx},${cy-size*1.3}L${cx+size*1.3},${cy}L${cx},${cy+size*1.3}L${cx-size*1.3},${cy}Z`,...attrs});
      else if(style.shape==='triangle'||style.shape==='triangle-down'){const direction=style.shape==='triangle'?1:-1;point=svg('path',{d:`M${cx},${cy-size*1.25*direction}L${cx+size*1.2},${cy+size*direction}L${cx-size*1.2},${cy+size*direction}Z`,...attrs});}
      else if(style.shape==='cross')point=svg('path',{d:`M${cx-size},${cy}H${cx+size}M${cx},${cy-size}V${cy+size}`,fill:'none',stroke:style.color,'stroke-width':size*.55,...extra});
      else if(style.shape==='hexagon'){const points=Array.from({length:6},(_,i)=>`${cx+Math.cos(i*Math.PI/3)*size*1.15},${cy+Math.sin(i*Math.PI/3)*size*1.15}`).join(' ');point=svg('polygon',{points,...attrs});}
      else point=svg('circle',{cx,cy,r:size,...attrs});
      parent.append(point);return point;
    }
    const formatted=(value,overall=false)=>numeric(value)?(overall?(value>=0?'+':'')+value.toFixed(2)+'%':value.toFixed(4)):'N/A';
    const short=row=>(row.model||'').replace('DeepSeek V4 Flash','DS V4 Flash').replace('Claude Opus 4.8','Opus 4.8')+' · '+({'Claude Code':'CC','Terminus-2':'T2'}[row.harness]||row.harness);
    function tooltip(region){const box=html('div',undefined,'chart-tooltip');box.hidden=true;region.append(box);return box;}
    function showTip(box,region,event,row,items,note){
      box.replaceChildren(html('strong',row.model),html('span',row.harness,'tooltip-harness'));
      const list=html('dl');for(const [label,value]of items)list.append(html('dt',label),html('dd',value));box.append(list);if(note)box.append(html('p',note,'tooltip-note'));
      box.hidden=false;
      const rect=region.getBoundingClientRect(),anchor=event?.currentTarget?.getBoundingClientRect();
      box.style.maxWidth=Math.min(root.innerWidth<=600?240:280,rect.width,Math.max(1,root.innerWidth-32))+'px';
      const left=event?.clientX?event.clientX-rect.left:anchor?anchor.left+anchor.width/2-rect.left:rect.width/2;
      const top=event?.clientY?event.clientY-rect.top:anchor?anchor.top-rect.top:20;
      const minimum=Math.max(0,12-rect.left),maximum=Math.max(minimum,Math.min(rect.width-box.offsetWidth,root.innerWidth-12-rect.left-box.offsetWidth));
      box.style.left=Math.max(minimum,Math.min(maximum,left+12))+'px';box.style.top=Math.max(0,top-box.offsetHeight-13)+'px';
    }
    function rowTip(row){
      const overall=scope==='overall',metric=data?.scopes?.[scope]?.metric||'Score';
      const quality=formatted(row.score,overall)+(numeric(row.score_sd)?' ± '+row.score_sd.toFixed(4):'');
      return [['API cost / run',formatCost(row.cost_usd)],...(numeric(row.cost_sd)?[['Cost SD',formatCost(row.cost_sd)]]:[]),[overall?'Mean relative gain':metric,quality],['Paired cost records',`${row.recorded_runs}/${row.total_runs}`]];
    }
    function rowNote(row){return row.status==='partial'?'Partial cost coverage; both axes use only the matched runs.':scope==='overall'?'Task-balanced average across all six tasks; not an average of raw metrics.':'Both axes use the same recorded research runs.';}
    function costDataTable(rows){
      let table=$('paired-cost-data');
      if(!table){const wrapper=html('div',undefined,'sr-only paired-cost-wrapper');table=html('table');table.id='paired-cost-data';wrapper.append(table);host.querySelector('.insights').append(wrapper);}
      table.replaceChildren(html('caption',`Paired cost and quality data · ${data?.scopes?.[scope]?.label||scope}. Logged USD API estimates; GPU costs excluded.`));
      const head=html('thead'),header=html('tr');
      for(const name of ['Configuration','Mean API cost per run (USD)','Cost SD (USD)','Paired score mean','Paired score SD','Recorded / total runs','Coverage']){const cell=html('th',name);cell.scope='col';header.append(cell);}head.append(header);
      const body=html('tbody');
      for(const row of rows){const line=html('tr');for(const value of [row.model+' · '+row.harness,cost(row.cost_usd)?String(row.cost_usd):'N/A',numeric(row.cost_sd)?String(row.cost_sd):'Not estimated',numeric(row.score)?String(row.score):'N/A',numeric(row.score_sd)?String(row.score_sd):'Not estimated',`${row.recorded_runs}/${row.total_runs}`,row.status])line.append(html('td',value));body.append(line);}
      table.append(head,body);
    }
    function empty(region,title,note){region.replaceChildren();const box=html('div',undefined,'insight-empty');box.append(html('strong',title));if(note)box.append(html('p',note));region.append(box);}
    function scatter(rows){
      const region=$('quality-chart'),known=rows.filter(row=>row.available),legend=$('quality-legend');region.replaceChildren();legend.replaceChildren();
      const description=state.cohort==='community'?'No logged costs accompany reviewed community results yet.':'No paired cost records are available for this scope.';
      if(!known.length){empty(region,'No paired cost data',description);$('quality-selection').textContent='';return;}
      const log=known.every(row=>row.cost_usd>0),width=660,height=430,left=73,right=635,top=31,bottom=348;
      const rawX=known.map(row=>log?Math.log10(row.cost_usd):row.cost_usd),rawY=known.map(row=>row.score);
      let xmin=Math.min(...rawX),xmax=Math.max(...rawX);if(xmin===xmax){xmin-=.3;xmax+=.3;}else{const pad=(xmax-xmin)*.09;xmin-=pad;xmax+=pad;}
      if(!log)xmin=0;
      let ymin=Math.min(...rawY),ymax=Math.max(...rawY),delta=ymax-ymin;if(delta===0)delta=Math.max(Math.abs(ymax)*.15,.01);
      ymin-=delta*.18;ymax+=delta*.21;if(scope!=='overall')ymin=Math.max(0,ymin);
      const x=value=>left+((log?Math.log10(value):value)-xmin)/(xmax-xmin)*(right-left),y=value=>bottom-(value-ymin)/(ymax-ymin)*(bottom-top);
      const chart=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'group','aria-label':`Scatter plot of mean logged API cost versus ${data?.scopes?.[scope]?.quality_label||'score'} for ${known.length} configurations. See the cost ranking and original score table for values.`});
      region.append(chart);
      for(let i=0;i<=4;i++){const value=ymin+(ymax-ymin)*i/4,position=y(value);chart.append(svg('line',{x1:left,y1:position,x2:right,y2:position,class:'grid-line'}),svg('text',{x:left-11,y:position+4,'text-anchor':'end'},scope==='overall'?value.toFixed(1):value.toFixed(ymax<.15?3:2)));}
      const ticks=[];
      if(log){for(let exponent=Math.floor(xmin);exponent<=Math.ceil(xmax);exponent++)for(const multiplier of [1,2,5]){const value=multiplier*10**exponent;if(Math.log10(value)>=xmin&&Math.log10(value)<=xmax)ticks.push(value);}}
      else for(let i=0;i<=4;i++)ticks.push((xmax-xmin)*i/4+xmin);
      const narrow=region.clientWidth>0&&region.clientWidth<400;
      const minimumTickGap=narrow?65*width/region.clientWidth:50,labelTicks=[];
      for(const [index,value]of ticks.entries()){const position=x(value);chart.append(svg('line',{x1:position,y1:top,x2:position,y2:bottom,class:'grid-line'}));
        if(index===0||index===ticks.length-1||position-x(labelTicks[labelTicks.length-1])>=minimumTickGap&&x(ticks[ticks.length-1])-position>=minimumTickGap)labelTicks.push(value);}
      for(const value of labelTicks)chart.append(svg('text',{x:x(value),y:bottom+25,'text-anchor':'middle'},'$'+(value<1?Number(value.toPrecision(2)):Number(value.toPrecision(3))).toString()));
      chart.append(svg('line',{x1:left,y1:bottom,x2:right,y2:bottom,class:'axis-line'}));
      const xlabel='Mean recorded API cost per research run (USD) →';
      chart.append(svg('text',{x:right,y:top-13,'text-anchor':'end',class:'axis-title'},log?'Log₁₀ cost axis':'Linear cost axis'));
      chart.append(svg('text',{x:(left+right)/2,y:height-25,'text-anchor':'middle',class:'axis-title'},xlabel),svg('text',{transform:`translate(18 ${(top+bottom)/2}) rotate(-90)`,'text-anchor':'middle',class:'axis-title'},(scope==='overall'?'Mean relative gain (%)':'Score')+' ↑'));
      const chosen=known.find(row=>row.id===selectedPoint);
      if(chosen)chart.append(svg('rect',{x:x(chosen.cost_usd),y:y(chosen.score),width:right-x(chosen.cost_usd),height:bottom-y(chosen.score),fill:'#7486a0','fill-opacity':.07}));
      const frontier=paretoFrontier(known);chart.append(svg('polyline',{points:frontier.map(row=>`${x(row.cost_usd)},${y(row.score)}`).join(' '),class:'frontier'}));
      const box=tooltip(region),labelBoxes=[];
      for(const row of known){
        const style=styleFor(row.id),px=x(row.cost_usd),py=y(row.score),partial=row.status==='partial';
        const point=svg('g',{class:'chart-point'+(chosen&&dominatedBy(row,chosen)?' is-muted':''),tabindex:0,role:'button','data-config-id':row.id,'aria-pressed':String(row.id===selectedPoint),'aria-label':`${row.model}, ${row.harness}; ${formatCost(row.cost_usd)} per run; score ${formatted(row.score,scope==='overall')}; ${row.recorded_runs} of ${row.total_runs} matched runs. Click to highlight dominated configurations.`});
        point.append(svg('circle',{cx:px,cy:py,r:row.id===selectedPoint?12:10,class:'point-halo'}));
        marker(point,px,py,row.id===selectedPoint?8:7,style,partial?{fill:'#fff','stroke-width':2.5}:{});
        const show=event=>showTip(box,region,event,row,rowTip(row),rowNote(row));point.addEventListener('pointerenter',show);point.addEventListener('pointermove',show);point.addEventListener('pointerleave',()=>{box.hidden=true;});point.addEventListener('focus',show);point.addEventListener('blur',()=>{box.hidden=true;});
        const choose=()=>{selectedPoint=row.id===selectedPoint?null:row.id;renderCosts();const replacement=[...region.querySelectorAll('.chart-point')].find(node=>node.getAttribute('data-config-id')===row.id);replacement?.focus();};point.addEventListener('click',choose);point.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose();}});chart.append(point);
        if(!narrow&&frontier.includes(row)||row.id===selectedPoint){
          const text=short(row),labelWidth=text.length*(root.innerWidth<=600?11:7.5);
          const options=[[px+12,py-13],[px-labelWidth-12,py-13],[px+12,py+23],[px-labelWidth-12,py+23]];
          const position=options.find(([lx,ly])=>lx>left&&lx+labelWidth<right&&ly>top&&ly<bottom&&!labelBoxes.some(b=>Math.abs(b[1]-ly)<18&&lx<b[0]+b[2]&&lx+labelWidth>b[0]));
          if(position){labelBoxes.push([...position,labelWidth]);chart.append(svg('text',{x:position[0],y:position[1],class:'point-label'},text));}
        }
      }
      for(const row of known){const button=html('button',undefined,'legend-button'),icon=svg('svg',{viewBox:'0 0 16 16','aria-hidden':true});button.type='button';button.setAttribute('aria-pressed',String(row.id===selectedPoint));marker(icon,8,8,4.1,styleFor(row.id),row.status==='partial'?{fill:'#fff','stroke-width':2}:{});const identity=html('span',undefined,'legend-identity');identity.append(html('strong',row.model),html('span',row.harness+(row.status==='partial'?' · partial':''),'legend-harness'));button.append(icon,identity);button.addEventListener('click',()=>{selectedPoint=row.id===selectedPoint?null:row.id;renderCosts();});legend.append(button);}
      $('quality-selection').textContent=chosen?`${short(chosen)} selected · ${known.filter(row=>dominatedBy(row,chosen)).length} higher-cost, no-better-score alternatives. Click again to clear.`:'Select a point to highlight higher-cost alternatives with no better score.';
    }
    function rankingChart(rows){
      const region=$('cost-chart');region.replaceChildren();const {ranked,missing}=costRanking(rows);
      if(!ranked.length){empty(region,'No recorded cost ranking',state.cohort==='community'?'Reviewed community costs have not been published.':'Missing costs are not treated as free runs.');return;}
      const maximum=Math.max(...ranked.map(row=>row.cost_usd)),list=html('ol',undefined,'cost-list');region.append(list);const box=tooltip(region);
      for(const row of ranked){
        const item=html('li',undefined,'cost-row'),button=html('button',undefined,'cost-button');button.type='button';const style=styleFor(row.id),identity=html('span',undefined,'cost-identity'),dot=html('span',undefined,'cost-dot');dot.style.background=style.color;
        const text=html('span');text.append(html('span',row.model,'cost-name'),html('span',row.harness,'cost-harness'));identity.append(dot,text);
        const value=html('span',undefined,'cost-value');value.append(html('span',formatCost(row.cost_usd)),html('span',`${row.recorded_runs}/${row.total_runs} runs`+(row.status==='partial'?' · partial':''),'cost-n'));
        button.append(html('span',String(row.rank),'cost-rank'),identity,value);button.setAttribute('aria-label',`Cost rank ${row.rank}: ${row.model}, ${row.harness}, ${formatCost(row.cost_usd)} per run; ${row.recorded_runs}/${row.total_runs} matched cost records.`);
        const track=html('div',undefined,'cost-track'),fill=html('div',undefined,'cost-fill');fill.style.width=(maximum?100*row.cost_usd/maximum:0)+'%';fill.style.background=style.color;track.setAttribute('aria-hidden','true');track.append(fill);item.append(button,track);list.append(item);
        const show=event=>showTip(box,region,event,row,rowTip(row),rowNote(row));button.addEventListener('pointerenter',show);button.addEventListener('pointermove',show);button.addEventListener('pointerleave',()=>{box.hidden=true;});button.addEventListener('focus',show);button.addEventListener('blur',()=>{box.hidden=true;});button.addEventListener('click',event=>{show(event);});
      }
      if(missing.length){const missingBox=html('div',undefined,'cost-missing');missingBox.append(html('p',scope==='overall'?'N/A · costs do not cover all six tasks.':'N/A · no recorded cost for this task.'));for(const row of missing){const line=html('div',undefined,'cost-missing-row');line.append(html('span',short(row)),html('b',`${row.recorded_runs}/${row.total_runs} records`));missingBox.append(line);}region.append(missingBox);}
    }
    function renderCosts(){
      if(!state)return;const board=state.boards[state.cohort],rows=costRows(data,state.cohort,scope,board),available=rows.filter(row=>row.available),label=data?.scopes?.[scope]?.label||scope;
      $('quality-title').textContent='Quality vs. cost · '+label;$('cost-title').textContent='Cost, ranked · '+label;
      $('quality-note').textContent=scope==='overall'?'Task-balanced cost versus mean relative gain on matched runs. The dashed frontier joins observed nondominated means.':(data?.scopes?.[scope]?.metric||board.tasks.find(task=>task.name===scope)?.metric||'Score')+' versus mean logged API cost. The dashed frontier joins observed nondominated means.';
      $('quality-coverage').textContent=available.length?`${available.length}/${rows.length} configurations · ${available.reduce((sum,row)=>sum+row.recorded_runs,0)} paired runs`:'No paired costs in this cohort';
      $('insights-data-status').textContent=!data?'Cost records are unavailable; the task profile still shows the selected results cohort.':scope==='overall'&&state.cohort==='paper'?'Overall includes only configurations with cost records on all six tasks. Incomplete coverage is shown explicitly; the two GPT-5.5 configurations have recorded costs only for TIGER and RankMixer.':'';
      scatter(rows);rankingChart(rows);costDataTable(rows);lastChartWidth=$('quality-chart').clientWidth;resize();
    }
    function profile(){
      const content=$('profile-content'),board=state?.boards?.[state.cohort];content.replaceChildren();
      if(!board?.rows?.length){empty(content,'No reviewed community profile yet','The paper reference profile remains in its own results cohort.');return;}
      const ids=new Set(board.rows.map(row=>row.id));profileSelection=profileSelection.filter(id=>ids.has(id)).slice(0,3);
      if(profileSelection.length<Math.min(2,board.rows.length))profileSelection=[...board.rows].sort((a,b)=>(a.overall_rank||Infinity)-(b.overall_rank||Infinity)).slice(0,Math.min(2,board.rows.length)).map(row=>row.id);
      const model=profileData(board,profileSelection),layout=html('div',undefined,'profile-layout'),region=html('div',undefined,'chart-region profile-chart'),controls=html('div',undefined,'profile-controls');layout.append(region,controls);content.append(layout);
      const width=570,height=490,cx=285,cy=236,radius=172,chart=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'group','aria-label':'Radar chart of six task scores scaled to the maximum score in the complete selected cohort. Raw means, standard deviations and trial counts are available on every point and in the Scores table.'});region.append(chart);
      const xy=(index,value,extra=0)=>{const angle=-Math.PI/2+index*Math.PI/3,r=radius*value/100+extra;return [cx+Math.cos(angle)*r,cy+Math.sin(angle)*r];};
      for(const level of [25,50,75,100]){chart.append(svg('polygon',{points:model.tasks.map((_,i)=>xy(i,level).join(',')).join(' '),fill:'none',stroke:'#e1e7f2','stroke-width':1.3}));chart.append(svg('text',{x:cx+7,y:cy-radius*level/100+4,class:'radar-ring-label'},String(level)));}
      model.tasks.forEach((task,i)=>{const end=xy(i,100),label=xy(i,100,32);chart.append(svg('line',{x1:cx,y1:cy,x2:end[0],y2:end[1],stroke:'#e1e7f2','stroke-width':1.3}),svg('text',{x:label[0],y:label[1]+5,'text-anchor':i===0||i===3?'middle':i<3?'start':'end',class:'radar-axis-label'},task.name));});
      const box=tooltip(region);
      for(const series of model.series){const style=styleFor(series.id),complete=series.values.every(numeric),points=series.values.map((value,i)=>numeric(value)?xy(i,value):null);
        if(complete)chart.append(svg('polygon',{points:points.map(point=>point.join(',')).join(' '),fill:style.color,'fill-opacity':.1,stroke:style.color,'stroke-dasharray':style.dash,class:'radar-polygon'}));
        else for(let i=0;i<points.length;i++){const next=(i+1)%points.length;if(points[i]&&points[next])chart.append(svg('line',{x1:points[i][0],y1:points[i][1],x2:points[next][0],y2:points[next][1],stroke:style.color,'stroke-width':2.5,'stroke-dasharray':style.dash}));}
        points.forEach((point,i)=>{if(!point)return;const task=model.tasks[i],group=svg('g',{class:'chart-point',tabindex:0,role:'img','aria-label':`${series.model}, ${series.harness}, ${task.name}: ${formatted(series.raw[i])}${numeric(series.sd[i])?' plus or minus '+series.sd[i].toFixed(4):''}; ${series.trials[i]} trials; ${series.values[i].toFixed(1)} percent of this cohort's best mean.`});marker(group,point[0],point[1],4.6,style);const show=event=>showTip(box,region,event,series,[[task.name+' · '+task.metric,formatted(series.raw[i])+(numeric(series.sd[i])?' ± '+series.sd[i].toFixed(4):'')],['Trials',String(series.trials[i]??'N/A')],['% of cohort best',series.values[i].toFixed(1)+'%']],`100 × mean / ${formatted(task.reference)}. The reference uses the full cohort, not only the selected configurations.`);group.addEventListener('pointerenter',show);group.addEventListener('pointermove',show);group.addEventListener('pointerleave',()=>{box.hidden=true;});group.addEventListener('focus',show);group.addEventListener('blur',()=>{box.hidden=true;});chart.append(group);});
      }
      controls.append(html('h4','Compare configurations'));const chips=html('div',undefined,'profile-chips');controls.append(chips);
      for(const series of model.series){const chip=html('div',undefined,'profile-chip'),icon=svg('svg',{viewBox:'0 0 18 18',class:'chip-icon','aria-hidden':true});marker(icon,9,9,5,styleFor(series.id));const identity=html('div',undefined,'chip-identity');identity.append(html('div',series.model,'chip-model'),html('div',series.harness,'chip-harness'));const remove=html('button','×');remove.type='button';remove.disabled=profileSelection.length<=Math.min(2,board.rows.length);remove.setAttribute('aria-label','Remove '+series.model+' with '+series.harness);remove.addEventListener('click',()=>{profileSelection=profileSelection.filter(id=>id!==series.id);profile();resize();});chip.append(icon,identity,remove);chips.append(chip);}
      const add=html('select',undefined,'profile-add');add.setAttribute('aria-label','Add a configuration to the six-task profile');add.append(new Option(profileSelection.length>=3?'Three configurations selected':'+ Add configuration…',''));for(const row of [...board.rows].sort((a,b)=>(a.overall_rank||Infinity)-(b.overall_rank||Infinity)))if(!profileSelection.includes(row.id))add.append(new Option(row.model+' · '+row.harness,row.id));add.disabled=profileSelection.length>=3||profileSelection.length>=board.rows.length;add.addEventListener('change',()=>{if(add.value&&!profileSelection.includes(add.value)&&profileSelection.length<3){profileSelection.push(add.value);profile();resize();}});controls.append(add,html('p','Compare any 2–3 configurations. Values and uncertainty are preserved in the Scores table; gaps stay missing.','profile-hint'));
    }
    function update(next){state=next;if(activeCohort!==state.cohort){activeCohort=state.cohort;selectedPoint=null;profileSelection=[];}renderCosts();profile();}
    root.addEventListener('resize',()=>{
      for(const box of host.querySelectorAll('.chart-tooltip'))box.hidden=true;
      if(!host.hidden&&state&&!resizeQueued&&Math.abs($('quality-chart').clientWidth-lastChartWidth)>1){resizeQueued=true;root.requestAnimationFrame(()=>{resizeQueued=false;renderCosts();profile();});}
    });
    root.AutoRSEInsights={update};
    tab(activeTab,false);if(state)update(state);
    fetch('insights-data.json',{cache:'no-cache'}).then(response=>{if(!response.ok)throw Error();return response.json();}).then(next=>{if(next?.schema_version!==1||next.currency!=='USD'||!next.scopes)throw Error();data=next;if(state)renderCosts();}).catch(()=>{if(state)renderCosts();});
  }
  return {costRows,dominatedBy,paretoFrontier,costRanking,normalizationReferences,profileData,formatCost,mount};
});
