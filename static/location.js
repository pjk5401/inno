(() => {const lat=document.getElementById('id_latitude'),lon=document.getElementById('id_longitude'),radius=document.getElementById('id_radius');const map=L.map('map').setView([Number(lat.value)||35.116,Number(lon.value)||128.968],16);
// OSM requires a Referer. Send only our origin, never paths or QR tokens.
// All other requests retain the application's same-origin policy.
const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
  maxZoom:19,
  referrerPolicy:'strict-origin-when-cross-origin',
  attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
});
const tileStatus=document.getElementById('map-status');let tileFailed=false;
tiles.on('loading',()=>{tileFailed=false;});
tiles.on('tileerror',()=>{tileFailed=true;tileStatus.textContent='지도를 불러오지 못했습니다. 잠시 후 새로고침해주세요. 현재 위치 또는 좌표 입력으로 인정 구역을 저장할 수 있습니다.';});
tiles.on('load',()=>{if(!tileFailed)tileStatus.textContent='';});
tiles.addTo(map);let circle;
function draw(){if(lat.value===''||lon.value==='')return;const point=[Number(lat.value),Number(lon.value)];if(!point.every(Number.isFinite))return;if(circle)map.removeLayer(circle);circle=L.circle(point,{radius:Number(radius.value)||200,color:'#176a53',fillOpacity:.15}).addTo(map);map.fitBounds(circle.getBounds(),{maxZoom:17});}
map.on('click',e=>{lat.value=e.latlng.lat.toFixed(7);lon.value=e.latlng.lng.toFixed(7);draw();});[lat,lon,radius].forEach(x=>x.addEventListener('change',draw));document.getElementById('my-location').onclick=()=>{if(!navigator.geolocation){document.getElementById('map-error').textContent='위치를 지원하는 HTTPS 브라우저에서 사용해주세요.';return;}navigator.geolocation.getCurrentPosition(p=>{lat.value=p.coords.latitude;lon.value=p.coords.longitude;draw();},()=>document.getElementById('map-error').textContent='위치를 확인하지 못했습니다. 좌표를 직접 입력할 수 있습니다.',{enableHighAccuracy:true,timeout:20000});};draw();})();
