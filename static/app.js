const $=id=>document.getElementById(id), paths={folder:'M2 7V5a1 1 0 0 1 1-1h6l2 3h9a1 1 0 0 1 1 1v11H3a1 1 0 0 1-1-1z',switch:'M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4',clock:'M12 22a10 10 0 1 1 0-20 10 10 0 0 1 0 20zm0-16v6l4 2',book:'M12 6Q7 2 2 5v14q5-3 10 1 5-4 10-1V5q-5-3-10 1v14',wifi:'M2 8q10-9 20 0M5 12q7-7 14 0m-11 4q4-4 8 0m-4 3h.01',grid:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',laptop:'M4 4h16v13H4zM2 20h20',link:'m9 14 6-6m-4-2 2-2a5 5 0 0 1 7 7l-3 3m-4 4-2 2a5 5 0 0 1-7-7l3-3',copy:'M8 8h12v13H8zM16 5V3H4v14h1',arrow:'M3 12h17m-6-6 6 6-6 6',upload:'M12 16V3m-5 5 5-5 5 5M3 16v5h18v-5',file:'M5 2h9l5 5v15H5zM14 2v6h5'};
function icon(k){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="'+paths[k]+'"/></svg>'}document.querySelectorAll('[data-i]').forEach(i=>i.innerHTML=icon(i.dataset.i));
const name=/Windows/i.test(navigator.userAgent)?'Windows 电脑':/iPhone|iPad/.test(navigator.userAgent)?'iOS 设备':/Android/.test(navigator.userAgent)?'Android 设备':/Mac/.test(navigator.userAgent)?'Mac 电脑':'桌面设备';
const launchKey=new URLSearchParams(location.hash.slice(1)).get('desktop');
if(launchKey){sessionStorage.transferbayUI=launchKey;delete sessionStorage.feiduToken;history.replaceState(null,'',location.pathname)}
let token=sessionStorage.feiduToken||'',state={},busy=false,pollBusy=false,transferBusy=false,progress={},historyData=[],renderKey='',toastTimer,lastPending=false;
try{historyData=JSON.parse(localStorage.feiduLog||'[]')}catch{}
function tell(msg){$('toast').textContent=msg;$('toast').className='show';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').className='',3500)}
async function api(path,data){let r=await fetch('/api/'+path,{method:data?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined,cache:'no-store'});let j=await r.json();if(!r.ok){if(r.status===401){token='';delete sessionStorage.feiduToken}throw Error(j.error||'操作失败')}return j}
function node(tag,txt,cls){const n=document.createElement(tag);n.textContent=txt||'';if(cls)n.className=cls;return n}
function size(n){return n>=1048576?(n/1048576).toFixed(1)+' MB':n>=1024?(n/1024).toFixed(1)+' KB':n+' B'}
function timeLabel(x){
 if(!x.createdAt)return x.when||'';
 const d=new Date(x.createdAt),today=new Date();
 const day=d.toDateString()===today.toDateString()?'今天':d.toLocaleDateString('zh-CN');
 return day+' '+d.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}
function row(x,archived){const r=node('div','','row'),tile=node('b','','tile');r.dataset.id=x.id;tile.innerHTML=icon('file');let d=node('div'),status=x.status==='saved'?(x.out?'对方已接收':'已接收'):x.status==='ready'?(x.out?'等待接收':state.saveErrors?.[x.id]?'自动保存失败':state.autoReceive?'正在自动保存':'可保存'):(progress[x.id]||'传输中');d.append(node('strong',x.name),node('small',(x.out?'发送':'接收')+' · '+size(x.size)+' · '+status));r.append(tile,d,node('time',timeLabel(x)));if(!archived&&!x.out&&['ready','saved'].includes(x.status)&&(!state.autoReceive||state.saveErrors?.[x.id])){let b=node('button',state.autoReceive?'重试保存':'保存','secondary');b.disabled=saving.has(x.id);b.onclick=async()=>{if(saving.has(x.id))return;saving.add(x.id);b.disabled=true;try{if(state.autoReceive){await api('inbox/retry',{id:x.id});return}if(state.inboxPath){const j=await api('inbox/save',{id:x.id});tell('已保存到「'+j.category+'」：'+j.name);return}let {href}=await api('file/'+x.id,{});const a=document.createElement('a');a.href=href;a.download=x.name;document.body.append(a);a.click();a.remove()}catch(e){tell(e.message)}finally{saving.delete(x.id);b.disabled=false;renderKey='';await sync();const current=document.querySelector('#queue [data-id="'+x.id+'"] button');if(current)current.disabled=false}};r.append(b)}return r}
const saving=new Set();
let skipped=new Set();
try{skipped=new Set(JSON.parse(localStorage.feiduCleared||'[]'))}catch{}
function clearHistory(){
 const active=new Set((state.files||[]).map(f=>f.id));
 skipped=new Set([...skipped,...historyData.map(x=>x.id),...(state.files||[]).filter(x=>['ready','saved'].includes(x.status)).map(x=>x.id)].filter(id=>active.has(id)));
 localStorage.feiduCleared=JSON.stringify([...skipped]);historyData=[];localStorage.feiduLog='[]';
 renderKey='';renderFiles();tell('记录已清空，文件仍保留');
}
$('clearLog').onclick=clearHistory;
$('inboxSide').onclick=$('openInbox').onclick=async()=>{try{await api('inbox/open',{})}catch(e){tell(e.message)}};
let sortOrder=localStorage.feiduSort==='asc'?'asc':'desc';
function orderFiles(items){
 // A stable sort preserves the existing newest-first order for legacy rows without timestamps.
 const newest=items.slice().sort((a,b)=>(b.createdAt||0)-(a.createdAt||0));
 return sortOrder==='desc'?newest:newest.reverse();
}
function updateList(el,items,archived,empty){
 const top=el.scrollTop, edge=el.getBoundingClientRect().top;
 const anchor=top>0 && Array.from(el.children).find(r=>r.getBoundingClientRect().bottom>edge);
 const offset=anchor?anchor.getBoundingClientRect().top-edge:0;
 const old=new Map(Array.from(el.children).map(r=>[r.dataset.id,r]));
 const ordered=orderFiles(items);let idx=0;
 for(const x of ordered){
   const key=JSON.stringify([x,progress[x.id],state.autoReceive,state.saveErrors?.[x.id]]);let r=old.get(x.id);old.delete(x.id);
   if(!r||r._key!==key){const n=row(x,archived);n._key=key;if(r)r.replaceWith(n);r=n}
   if(el.children[idx]!==r)el.insertBefore(r,el.children[idx]||null);
   idx++;
 }
 for(const r of old.values())r.remove();
 if(!items.length&&empty)el.append(node('div',empty,'empty'));
 if(anchor){const r=Array.from(el.children).find(n=>n.dataset.id===anchor.dataset.id);if(r)el.scrollTop+=r.getBoundingClientRect().top-edge-offset}
}
function renderFiles(){
 const list=state.files||[],k=JSON.stringify([list,progress,sortOrder,!!state.peer,state.autoReceive,state.saveErrors]);if(renderKey===k)return;renderKey=k;
 $('queueHead').hidden=!state.peer;$('count').textContent=list.length;
 updateList($('queue'),list.slice().reverse(),false,state.peer?'本次连接还没有收发文件。':'');
 for(const x of list.filter(x=>!skipped.has(x.id)&&['ready','saved'].includes(x.status))){
   const prev=historyData.find(y=>y.id===x.id);
   if(prev)Object.assign(prev,x);else historyData.unshift({...x,createdAt:x.createdAt||Date.now()});
 }
 historyData.sort((a,b)=>(b.createdAt||0)-(a.createdAt||0));historyData=historyData.slice(0,80);
 const stored=JSON.stringify(historyData);if(stored!==localStorage.feiduLog)localStorage.feiduLog=stored;
 $('clearLog').disabled=!historyData.length;
 updateList($('logs'),historyData,true,'还没有传输记录。');
}
document.querySelectorAll('.sort').forEach(s=>{
 s.value=sortOrder;s.onchange=()=>{sortOrder=s.value;localStorage.feiduSort=sortOrder;document.querySelectorAll('.sort').forEach(x=>x.value=sortOrder);$('queue').scrollTop=$('logs').scrollTop=0;renderFiles()};
});
$('infoToggle').onclick=()=>{const show=$('miniInfo').hidden;$('miniInfo').hidden=!show;$('infoToggle').setAttribute('aria-expanded',String(show));$('infoToggle').textContent=show?'收起配对码':'查看配对码'};
$('disconnect').onclick=()=>$('connect').click();
function showProblem(text){$('problem').textContent=text;$('problem').hidden=!text}
function cleanCode(value){return value.normalize('NFKC').toUpperCase().replace(/[\s-]/g,'').replace(/O/g,'0').replace(/[IL]/g,'1')}
function formatted(s){
 const c=s.shortCode||s.pairingCode||s.code;
 return c.match(c.length===6?/.{1,3}/g:/.{1,4}/g).join(c.length===6?' ':'-');
}
function paint(){
 const s=state;
 $('settingsButton').hidden=$('inboxSide').hidden=$('openInbox').hidden=!s.inboxPath;$('inboxPath').textContent=s.inboxPath||'';
 $('home').classList.toggle('paired',!!s.peer);$('peerBar').hidden=!s.peer;
 $('peerName').textContent=s.peer?'已连接 · '+s.peer:'';
 $('miniInfo').textContent='本机配对码　'+formatted(s);
 if(!s.peer){$('miniInfo').hidden=true;$('infoToggle').textContent='查看配对码';$('infoToggle').setAttribute('aria-expanded','false')}
 $('disconnect').disabled=busy;
 $('online').textContent=s.peer?'设备已配对':s.addresses?.length?'局域网在线':'未获取局域网地址';
 $('online').className=s.addresses?.length||s.peer?'on':'';
 $('device').textContent=s.name;
 $('floatToggle').hidden=!(name==='Windows 电脑'&&sessionStorage.transferbayUI);
 $('mycode').textContent=formatted(s);
 $('mycode').classList.toggle('long',formatted(s).length>11);$('longCode').textContent=s.pairingCode||s.code;$('legacy').textContent='本机旧版六位码：'+s.code;
 $('lan').textContent=(s.addresses||[]).join(' / ')||'请检查网络连接';
 $('pairtitle').textContent=s.peer?'已连接 · '+s.peer:'连接其他设备';
 $('pairhint').textContent=s.peer?'可以向这台设备发送文件。':s.pending?(s.pendingWords?'请在对方屏幕上核对：'+s.pendingWords:'已发送请求，等待对方确认。'):'输入对方的六位数字。';
 $('digits').hidden=!!s.peer;$('manual').hidden=!!s.peer||s.pending;
 $('digits').disabled=busy||s.pending;
 $('connect').textContent=s.peer?'断开连接':s.pending?'等待确认':busy?'查找中…':'连接';
 $('connect').disabled=busy||s.pending;$('choose').disabled=false;
 $('dropnote').textContent=s.peer?'发送至 '+s.peer+' · 单个文件最大 2 GB':'也可拖到窗口任意位置，配对后自动发送';
 if(s.peer||s.pending)showProblem('');
 if(lastPending&&!s.pending&&!s.peer)showProblem('对方未接受或请求已过期，可以重新连接。');lastPending=s.pending;
updatePending();if(s.peer)drain();
if(s.ask){$('who').textContent=s.ask.name+' 想与你连接并收发文件。';$('wordCheck').hidden=!s.ask.words;$('words').textContent=s.ask.words||'';$('yes').textContent=s.ask.words?'词一致，允许连接':'允许连接';if(!$('invite').open)$('invite').showModal()}else if($('invite').open)$('invite').close();renderFiles()}
let join=new URLSearchParams(location.hash.slice(1)).get('join');if(join)window.history.replaceState(null,'',location.pathname);
async function sync(){
 if(pollBusy)return;pollBusy=true;
 try{
   if(!token){const j=await api('device',{name,supportsText:true,uiKey:sessionStorage.transferbayUI});sessionStorage.feiduToken=token=j.token}
   state=await api('state');paint();window.dispatchEvent(new Event('transfer-state'));
   if(join){const c=join;join=null;$('digits').value=c;try{await api('pair',{code:c});tell('配对请求已发送')}catch(e){showProblem(e.message)}}
 }catch(e){$('peerName').textContent='服务未连接';$('disconnect').disabled=true;$('online').textContent='服务未连接';$('online').className='';$('connect').disabled=true;$('choose').disabled=true}
 finally{pollBusy=false}
}
$('pair').onsubmit=async e=>{
 e.preventDefault();if(busy||!state.code)return;busy=true;showProblem('');paint();
 try{
   if(state.peer){
     if(confirm(state.autoReceive?'确定断开连接？未完成的传输会中止。':'断开前请保存收到的文件。确定断开连接？'))await api('disconnect',{});
   }else{
     const c=cleanCode($('digits').value);
     if(!/^[0-9A-HJKMNP-TV-Z]+$/.test(c)||![6,8,9,11,12,13,15].includes(c.length))throw Error('请输入对方窗口显示的完整配对码。');
     if(c===state.code||c===state.shortCode||c===state.pairingCode)throw Error('这是本机的码，请输入另一台设备的配对码。');
     const address=$('manual').open?$('address').value.trim():'';
     const result=await api('discover',{code:c,address,short:/^\d{6}$/.test(c)&&!!state.inboxPath,stayLocal:true});
     if(result.requested){tell('配对请求已发送');return}
     if(result.url){location.assign(result.url+'/#join='+(result.pin||c));return}
     if(!result.local){$('manual').open=true;throw Error('未发现对方设备。请确认两端都打开了 1.7 或更新版本；也可以输入对方的备用长码。')}
     await api('pair',{code:result.pin||c,short:!!result.short});tell('配对请求已发送');
   }
 }catch(e){if(/地址|防火墙/.test(e.message))$('manual').open=true;showProblem(e.message)}
 finally{busy=false;await sync();if(state.code&&$('online').textContent!=='服务未连接')paint()}
};
$('invite').oncancel=e=>{e.preventDefault();$('no').click()};for(const [id,accept] of [['yes',true],['no',false]])$(id).onclick=async()=>{try{await api('answer',{id:state.ask.id,accept});await sync()}catch(e){tell(e.message)}};
$('copy').onclick=async()=>{try{if(navigator.clipboard)await navigator.clipboard.writeText(formatted(state));else{let t=node('textarea',formatted(state));document.body.append(t);t.select();let ok=document.execCommand('copy');t.remove();if(!ok)throw Error()}tell('配对码已复制')}catch{tell('本机配对码：'+formatted(state))}};
function upload(id,file){return new Promise((res,rej)=>{let x=new XMLHttpRequest();x.open('PUT','/api/file/'+id);x.setRequestHeader('Authorization','Bearer '+token);x.upload.onprogress=e=>{progress[id]=Math.floor(100*e.loaded/(e.total||1))+'%';renderFiles()};x.onload=()=>x.status===200?res():rej(Error('发送失败，请重新选择文件'));x.onerror=()=>rej(Error('网络中断，发送失败'));x.send(file)})}
const pendingFiles=[];let activeFile='',queueMessage='';
function updatePending(){
 const count=pendingFiles.length+(state.nativeQueued||0);const n=$('pendingNote');
 n.textContent=[activeFile?'正在发送：'+activeFile:'',count?(state.peer?'队列中 ':'等待配对 · ')+count+' 个文件':'',queueMessage].filter(Boolean).join('　');
 n.hidden=!n.textContent;
}
function enqueue(files){
 queueMessage='';const pair=state.pairID||state.peer||null;
 for(const f of files){if(f.size>2147483648){queueMessage='已跳过超过 2 GB 的文件';continue}pendingFiles.push({f,pair})}
 updatePending();drain();
}
async function drain(){
 if(transferBusy||!state.peer||!pendingFiles.length)return;transferBusy=true;
 try{
   while(pendingFiles.length&&state.peer){
     const {f,pair}=pendingFiles.shift();
     if(pair&&pair!==(state.pairID||state.peer)){queueMessage='原连接已断开，请重新拖入文件。';continue}
     activeFile=f.name;updatePending();
     let {id}=await api('offer',{name:f.name,size:f.size,pairID:state.pairID});await sync();
     await upload(id,f);delete progress[id];await sync();
   }
 }catch(e){queueMessage='发送失败：'+e.message;tell(queueMessage)}
 finally{transferBusy=false;activeFile='';updatePending()}
}
$('choose').onclick=()=>$('pick').click();
$('pick').onchange=e=>{enqueue(Array.from(e.target.files));e.target.value=''};
const hasFiles=e=>Array.from(e.dataTransfer?.types||[]).includes('Files');let depth=0;
document.addEventListener('dragenter',e=>{if(hasFiles(e)){e.preventDefault();depth++;document.body.classList.add('receivingDrop')}});
document.addEventListener('dragover',e=>{if(hasFiles(e)){e.preventDefault();e.dataTransfer.dropEffect='copy'}});
document.addEventListener('dragleave',()=>{if(--depth<=0){depth=0;document.body.classList.remove('receivingDrop')}});
document.addEventListener('drop',e=>{
 if(!hasFiles(e))return;
 e.preventDefault();depth=0;document.body.classList.remove('receivingDrop');
 const items=Array.from(e.dataTransfer.items||[]);const dirs=items.filter(i=>i.webkitGetAsEntry?.()?.isDirectory);
 const files=items.length?items.filter(i=>i.kind==='file'&&!dirs.includes(i)).map(i=>i.getAsFile()).filter(Boolean):Array.from(e.dataTransfer.files);
 if(files.length){enqueue(files);if($('home').hidden)tell('已加入发送队列：'+files.length+' 个文件')};if(dirs.length)tell('文件夹请先压缩，文件已加入队列。')
});
document.querySelectorAll('nav button[data-view]').forEach(b=>b.onclick=()=>{for(let v of ['home','history','help'])$(v).hidden=v!==b.dataset.view;document.querySelector('nav .sel').classList.remove('sel');b.classList.add('sel');document.querySelectorAll('nav button[data-view]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','page')});sync();setInterval(sync,1200)

$('floatToggle').onclick=async()=>{try{const r=await api('float',{});tell(r.visible?'桌面悬浮窗已显示':'桌面悬浮窗已隐藏')}catch(e){tell(e.message)}};

$('settingsButton').onclick=async()=>{
 try{const j=await api('settings/port');$('portField').value=j.port===j.default?'':String(j.port);
 $('portHint').textContent='当前监听：'+j.active+'　·　默认：'+j.default;$('portError').textContent='';$('settings').showModal()}catch(e){tell(e.message)}
};
$('closeSettings').onclick=()=>$('settings').close();
$('portForm').onsubmit=async e=>{
 e.preventDefault();$('savePort').disabled=true;
 try{const j=await api('settings/port',{port:$('portField').value===''?8765:$('portField').valueAsNumber});
 $('settings').close();tell(j.port===j.active?'端口设置已保存':'设置已保存，重启后使用端口 '+j.port)}
 catch(e){$('portError').textContent=e.message}finally{$('savePort').disabled=false}
};
