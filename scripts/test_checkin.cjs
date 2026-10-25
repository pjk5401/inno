// Isolated JavaScript tests: no browser permissions, network, or real location used.
const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');
const assert=require('node:assert/strict');
const source=readFileSync(require('node:path').join(__dirname,'../static/checkin.js'),'utf8');

function screen(mock='0') {
  const elements=new Map();
  function el(id){if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,textContent:'',value:'',addEventListener(){}});return elements.get(id);}
  const form=el('checkin-form');
  const handlers={};
  form.dataset={remaining:'300',generation:'1',storage:'test',identity:'test-id',boundId:'',mock,submit:'/submit',status:'/status'};
  form.querySelector=()=>({value:'csrf'});
  form.elements={kind:{value:'course'},name:{value:'테스트학생'}};
  form.course={value:'1',options:[{},{}]};form.student_id={value:'001'};form.department={value:'테스트학과'};
  form.addEventListener=(type,fn)=>handlers[type]=fn;
  const canvas=el('signature');canvas.offsetWidth=300;canvas.offsetHeight=100;canvas.getContext=()=>({scale(){}});
  const geo={denied:false,calls:0};
  let requests=[];
  const permission={state:'granted'};
  const context={
    document:{getElementById:el,addEventListener(){}},
    window:{devicePixelRatio:1,addEventListener(){},location:{assign(url){context.redirect=url;}}},
    performance:{now:()=>0},Date,Promise,JSON,Number,Math,String,
    sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},setInterval(){},
    SignaturePad:class {toData(){return [];}fromData(){}clear(){}addEventListener(){}isEmpty(){return false;}toDataURL(){return 'test-signature';}},
    navigator:{geolocation:{getCurrentPosition(ok,fail){geo.calls++;if(geo.denied)fail({code:1});else ok({coords:{latitude:35.123456,longitude:129.123456,accuracy:10},timestamp:Date.now()});}},permissions:{query:async()=>permission}},
    fetch:async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({ok:true,redirect:'/complete'})};},
  };
  runInNewContext(source,context);
  return {el,form,handlers,geo,permission,requests,context};
}

(async()=>{
  const s=screen('1'); // Sandbox must not bypass the Geolocation API.
  assert.equal(s.el('submit-button').disabled,true);
  s.form.elements.kind.value='guest';s.handlers.change();
  assert.equal(s.el('course-field').hidden,true);
  assert.equal(s.form.course.disabled,true);
  assert.equal(s.form.department.required,true);
  s.geo.denied=true;await s.el('check-location').onclick();
  assert.equal(s.el('submit-button').disabled,true);
  assert.match(s.el('location-status').textContent,/위치 권한/);
  await s.handlers.submit({preventDefault(){}});
  assert.equal(s.requests.length,0);
  s.geo.denied=false;await s.el('check-location').onclick();
  assert.equal(s.el('submit-button').disabled,false);
  assert.match(s.el('location-status').textContent,/위도 35\.1 · 경도 129\.1/);
  s.geo.denied=true;await s.handlers.submit({preventDefault(){}});
  assert.equal(s.requests.length,0); // Recheck at submission, even after prior success.
  s.geo.denied=false;await s.el('check-location').onclick();
  const calls=s.geo.calls;
  await s.handlers.submit({preventDefault(){}});
  assert.equal(s.geo.calls,calls+1);
  assert.equal(s.requests[0].body.latitude,35.123456); // Display rounding must not affect validation.
  assert.equal(s.requests[0].body.kind,'guest');
  assert.equal(s.requests[0].body.department,'테스트학과');
  assert.equal(s.context.redirect,'/complete');
  s.permission.state='denied';s.permission.onchange();
  assert.equal(s.el('submit-button').disabled,true);
  console.log('PASS: location gating, denial, revocation, submit recheck, full precision, sandbox parity, guest fields');
})().catch(e=>{console.error(e);process.exitCode=1;});
