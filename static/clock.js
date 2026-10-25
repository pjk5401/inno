(() => {
  const root=document.getElementById('server-clock');
  if(!root)return;
  let server=Date.parse(root.dataset.server),attendance=Date.parse(root.dataset.attendance),synced=performance.now();
  const format=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  function draw(){const elapsed=performance.now()-synced;document.getElementById('server-time').textContent=format.format(new Date(server+elapsed));const demo=document.getElementById('attendance-time');if(demo)demo.textContent=format.format(new Date(attendance+elapsed));}
  window.addEventListener('attendance-clock',e=>{server=Date.parse(e.detail.server_time);attendance=Date.parse(e.detail.attendance_time);synced=performance.now();draw();});
  async function sync(){try{const r=await fetch(root.dataset.url,{cache:'no-store'});if(!r.ok)return;window.dispatchEvent(new CustomEvent('attendance-clock',{detail:await r.json()}));}catch{}}
  draw();setInterval(draw,1000);setInterval(sync,30000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync();});
})();
