// Isolated JavaScript tests: no browser permissions, network, or real location used.
const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');
const assert=require('node:assert/strict');
const source=readFileSync(require('node:path').join(__dirname,'../static/checkin.js'),'utf8');

function screen(mock='0',guestEnabled='1',draft=null) {
  const elements=new Map();
  function el(id){if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,textContent:'',value:'',addEventListener(){}});return elements.get(id);}
  const form=el('checkin-form');
  const handlers={},timers=[];
  let elapsed=0;
  form.dataset={guestEnabled,remaining:'300',generation:'1',storage:'test',identity:'test-id',boundId:'',mock,submit:'/submit',status:'/status'};
  form.querySelector=()=>({value:'csrf'});
  form.elements={kind:{value:'course'},name:{value:'테스트학생'}};
  form.course={value:'1',options:[{},{}]};form.student_id={value:'001'};form.department={value:'테스트학과'};
  form.addEventListener=(type,fn)=>handlers[type]=fn;
  const canvas=el('signature');canvas.offsetWidth=300;canvas.offsetHeight=100;canvas.getContext=()=>({scale(){}});
  const geo={denied:false,calls:0};
  let requests=[];
  const context={
    document:{getElementById:el,addEventListener(){}},
    window:{devicePixelRatio:1,addEventListener(){},location:{assign(url){context.redirect=url;}}},
    performance:{now:()=>elapsed},Date,Promise,JSON,Number,Math,String,
    sessionStorage:{getItem:()=>draft?JSON.stringify(draft):null,setItem(){},removeItem(){}},setInterval(fn){timers.push(fn);},
    SignaturePad:class {toData(){return [];}fromData(){}clear(){}addEventListener(){}isEmpty(){return false;}toDataURL(){return 'test-signature';}},
    navigator:{geolocation:{getCurrentPosition(ok,fail){geo.calls++;if(geo.denied)fail({code:1});else ok({coords:{latitude:35.123456,longitude:129.123456,accuracy:10},timestamp:Date.now()});}}},
    fetch:async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({ok:true,redirect:'/complete'})};},
  };
  runInNewContext(source,context);
  return {el,form,handlers,geo,requests,context,expire(){elapsed=301000;timers[0]();}};
}

(async()=>{
  for(const mock of ['0','1']) {
    const s=screen(mock);
    assert.equal(s.geo.calls,0); // Opening the page must not request location.
    assert.equal(s.el('submit-button').disabled,false);
    s.form.elements.kind.value='guest';s.handlers.change();
    assert.equal(s.el('course-field').hidden,true);
    assert.equal(s.form.course.disabled,true);
    assert.equal(s.form.department.required,true);
    s.geo.denied=true;
    await s.handlers.submit({preventDefault(){}});
    assert.equal(s.geo.calls,1);
    assert.equal(s.requests.length,0);
    assert.match(s.el('form-error').textContent,/위치 권한/);
    assert.equal(s.el('submit-button').disabled,false); // Allow retry after changing permission.
    s.geo.denied=false;
    await s.handlers.submit({preventDefault(){}});
    assert.equal(s.geo.calls,2);
    assert.equal(s.requests[0].body.latitude,35.123456);
    assert.equal(s.requests[0].body.kind,'guest');
    assert.equal(s.requests[0].body.department,'테스트학과');
    assert.equal(s.context.redirect,'/complete');
    s.geo.denied=true;
    await s.handlers.submit({preventDefault(){}});
    assert.equal(s.geo.calls,3);
    assert.equal(s.requests.length,1); // No reuse of a previous location grant/coordinate.
    s.expire();
    assert.equal(s.el('submit-button').disabled,true);
    await s.handlers.submit({preventDefault(){}});
    assert.equal(s.geo.calls,3);
    assert.equal(s.requests.length,1);
  }
  const hidden=screen('0','0',{identity:'test-id',generation:'1',kind:'guest',department:'이전학과',student_id:'001',name:'학생',course:'1',saved:Date.now()});
  assert.equal(hidden.form.elements.kind.value,'course');
  hidden.form.elements.kind.value='guest';hidden.handlers.change();
  assert.equal(hidden.el('course-field').hidden,false);
  assert.equal(hidden.form.course.required,true);
  assert.equal(hidden.form.department.required,false);
  await hidden.handlers.submit({preventDefault(){}});
  assert.equal(hidden.requests[0].body.kind,'course');
  console.log('PASS: location requested only on submit, denial/retry/revocation, full precision, sandbox parity, hidden expiry');
})().catch(e=>{console.error(e);process.exitCode=1;});
