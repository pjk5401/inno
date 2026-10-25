(() => {
  const root=document.getElementById('qr-screen'),img=document.getElementById('qr-image'),err=document.getElementById('qr-error'),link=document.getElementById('qr-link'),print=document.getElementById('print-qr');
  print.onclick=()=>window.print();
  async function load(){try{const response=await fetch(root.dataset.url,{cache:'no-store'});if(!response.ok)throw new Error();const d=await response.json();img.src=d.image;await img.decode();img.hidden=false;err.hidden=true;link.href=d.url;link.hidden=false;print.disabled=false;}catch{err.textContent='QR을 불러오지 못했습니다. 로그인과 연결 상태를 확인하고 새로고침해주세요.';}}
  load();
})();
