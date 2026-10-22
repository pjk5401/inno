(() => {
  const form=document.getElementById('checkin-form'),canvas=document.getElementById('signature');
  const pad=new SignaturePad(canvas,{minWidth:1,maxWidth:2.5,penColor:'#172e29'});
  const key='attendance-draft-'+form.dataset.storage;
  const csrf=form.querySelector('[name=csrfmiddlewaretoken]').value;
  const error=document.getElementById('form-error'),button=document.getElementById('submit-button');
  let remaining=Number(form.dataset.remaining),lastTick=Date.now(),busy=false;
  function notice(msg){error.textContent=msg;error.hidden=false;}
  function save(){try{sessionStorage.setItem(key,JSON.stringify({identity:form.dataset.identity,generation:form.dataset.generation,course:form.course.value,student_id:form.student_id.value,name:form.elements.name.value,signature:pad.toData(),saved:Date.now()}));}catch{}}
  function resize(){const data=pad.toData(),ratio=Math.max(window.devicePixelRatio||1,1);canvas.width=canvas.offsetWidth*ratio;canvas.height=canvas.offsetHeight*ratio;canvas.getContext('2d').scale(ratio,ratio);pad.clear();pad.fromData(data);}
  resize();window.addEventListener('resize',resize);
  try{const old=JSON.parse(sessionStorage.getItem(key)||'null');if(old&&old.identity===form.dataset.identity&&String(old.generation)===form.dataset.generation&&Date.now()-old.saved<3600000){form.course.value=old.course;form.student_id.value=old.student_id;form.elements.name.value=old.name;if(old.signature)pad.fromData(old.signature);}else sessionStorage.removeItem(key);}catch{}
  if(form.dataset.boundId){form.student_id.value=form.dataset.boundId;form.student_id.readOnly=true;}
  form.addEventListener('input',save);pad.addEventListener('endStroke',save);
  document.getElementById('clear-signature').onclick=()=>{pad.clear();save();};
  setInterval(()=>{remaining=Math.max(0,remaining-(Date.now()-lastTick)/1000);lastTick=Date.now();document.getElementById('timer').textContent=String(Math.floor(remaining/60)).padStart(2,'0')+':'+String(Math.floor(remaining%60)).padStart(2,'0');if(!remaining&&!busy)notice('작성 시간이 만료되었습니다. 같은 브라우저에서 최신 QR을 다시 스캔해주세요.');},500);
  setInterval(async()=>{if(busy)return;try{const r=await fetch(form.dataset.status,{cache:'no-store'});const d=await r.json();remaining=d.remaining;lastTick=Date.now();if(!d.valid){sessionStorage.removeItem(key);notice('접속 또는 학번 정보가 변경되었습니다. 새 QR을 스캔해주세요.');}}catch{}},10000);
  function position(){return new Promise((resolve,reject)=>{if(!navigator.geolocation)return reject(new Error('이 브라우저에서는 위치 확인을 사용할 수 없습니다.'));navigator.geolocation.getCurrentPosition(p=>resolve({latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy,location_timestamp:p.timestamp}),e=>reject(new Error(e.code===1?'위치 권한을 허용해주세요. 브라우저 설정에서 위치 권한을 변경한 뒤 다시 제출할 수 있습니다.':'위치를 확인하지 못했습니다. 다시 시도하거나 조교에게 문의해주세요.')),{enableHighAccuracy:true,maximumAge:0,timeout:20000});});}
  form.addEventListener('submit',async event=>{event.preventDefault();if(busy)return;error.hidden=true;if(pad.isEmpty())return notice('서명을 작성해주세요.');save();busy=true;button.disabled=true;button.textContent='위치와 출석을 확인하고 있습니다…';try{const location=form.dataset.mock==='1'?{}:await position();const payload={course:form.course.value,student_id:form.student_id.value,name:form.elements.name.value,signature:pad.toDataURL('image/png'),...location};const response=await fetch(form.dataset.submit,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(payload)});let data;try{data=await response.json();}catch{throw new Error('서버 응답을 확인할 수 없습니다. 입력은 유지됩니다. 잠시 후 다시 제출해주세요.');}if(!response.ok||!data.ok)throw new Error(data.error||'출석을 저장하지 못했습니다.');sessionStorage.removeItem(key);window.location.assign(data.redirect);}catch(e){notice(e.message||'통신에 실패했습니다. 다시 시도해주세요.');}finally{busy=false;button.disabled=false;button.textContent='출석 제출';}});
})();
