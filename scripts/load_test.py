"""Authenticated operator launches HTTP traffic exclusively against /test/.

Uses fictional seeded identities; never initializes/deletes data implicitly.
Run after resetting sandbox. Re-running against the same records detects duplicates.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import getpass
from html.parser import HTMLParser
import http.cookiejar
import io
import json
import statistics
import time
import urllib.request
import urllib.parse
import urllib.error
from PIL import Image, ImageDraw

class Fields(HTMLParser):
    def __init__(self):
        super().__init__();self.csrf=None;self.courses=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and a.get('name')=='csrfmiddlewaretoken':self.csrf=a.get('value')
        if tag=='option' and a.get('value') and 'disabled' not in a:self.courses.append(a['value'])

def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def request(opener,url,data=None,origin=None):
    headers={}
    if origin:headers['Origin']=origin
    if data is not None:data=urllib.parse.urlencode(data).encode()
    return opener.open(urllib.request.Request(url,data=data,headers=headers),timeout=100)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin',required=True)
    parser.add_argument('--users',type=int,default=200)
    parser.add_argument('--workers',type=int,default=24)
    args=parser.parse_args()
    origin=args.origin.rstrip('/')
    parsed=urllib.parse.urlsplit(origin)
    if parsed.path or parsed.query or parsed.username or parsed.scheme not in ('http','https'):
        parser.error('origin must be an HTTP(S) origin without a path')
    if not 1<=args.users<=210 or not 1<=args.workers<=32:parser.error('users 1..210, workers 1..32')
    base=origin+'/test/'
    print('대상:',base,'가상 제출:',args.users,'동시 작업:',args.workers)
    print('먼저 테스트 관리 화면에서 전체 초기화하세요. 운영 데이터는 접근하지 않습니다.')
    if input('테스트 출석 기록을 생성할까요? TEST 입력: ')!='TEST':return
    admin=client();page=request(admin,base+'staff/login/').read().decode()
    if '테스트 환경' not in page:raise RuntimeError('테스트 환경 표시를 확인하지 못했습니다.')
    fields=Fields();fields.feed(page)
    username=input('테스트 관리자/조교 아이디: ')
    password=getpass.getpass('비밀번호: ')
    response=request(admin,base+'staff/login/',{'csrfmiddlewaretoken':fields.csrf,'username':username,'password':password},origin)
    password=None
    if '/login/' in response.url:raise RuntimeError('로그인 실패')
    page=request(admin,base+'staff/test-control/').read().decode();fields=Fields();fields.feed(page)
    request(admin,base+'staff/test-control/',{'csrfmiddlewaretoken':fields.csrf,'action':'normal'},origin).read()
    qr=json.load(request(admin,base+'staff/qr/data/'))
    probe=client();page=request(probe,qr['url']).read().decode();fields=Fields();fields.feed(page)
    courses=fields.courses
    if len(courses)<3:raise RuntimeError('기본 가상수업 3개를 먼저 준비해주세요.')
    im=Image.new('RGB',(300,100),'white');ImageDraw.Draw(im).line([(10,80),(60,20),(140,70),(250,30)],fill='black',width=3)
    stream=io.BytesIO();im.save(stream,format='PNG')
    sig='data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()
    def student(index):
        started=time.perf_counter();opener=client()
        try:
            page=request(opener,qr['url']).read().decode();f=Fields();f.feed(page)
            sid=index%70+1
            payload={'course':courses[index//70],'student_id':f'2026{sid:04}','name':f'가상학생{sid:02}','signature':sig}
            req=urllib.request.Request(base+'checkin/submit/',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-CSRFToken':f.csrf,'Origin':origin})
            data=json.load(opener.open(req,timeout=100))
            return bool(data.get('ok')),time.perf_counter()-started,''
        except urllib.error.HTTPError as e:
            return False,time.perf_counter()-started,e.read(1000).decode(errors='replace')
        except Exception as e:return False,time.perf_counter()-started,str(e)
    start=time.perf_counter();results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for task in as_completed([pool.submit(student,i) for i in range(args.users)]):results.append(task.result())
    times=sorted(r[1] for r in results);success=sum(r[0] for r in results)
    print(json.dumps({'users':args.users,'success':success,'failed':args.users-success,'total_seconds':round(time.perf_counter()-start,2),'mean_seconds':round(statistics.mean(times),2),'p95_seconds':round(times[min(len(times)-1,int(len(times)*.95))],2)},ensure_ascii=False,indent=2))
    for r in [r for r in results if not r[0]][:5]:print('오류:',r[2])
    if success!=args.users:raise SystemExit(1)
    print('HTTP 제출 성공. 테스트 출석부에서 인원·중복·서명도 확인하세요.')

if __name__=='__main__':main()
