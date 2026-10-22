import base64
import io
import json
import tempfile
from datetime import timedelta
from unittest.mock import patch
from PIL import Image, ImageDraw
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Policy, Course, Enrollment, Attendance, Attempt, Audit, BrowserIdentity
from . import services as svc

def signature():
    im=Image.new('RGB',(300,100),'white');draw=ImageDraw.Draw(im);draw.line([(15,70),(80,20),(130,70),(220,30)],fill='black',width=3)
    b=io.BytesIO();im.save(b,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AttendanceTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.settings_override=override_settings(MEDIA_ROOT=self.tmp.name)
        self.settings_override.enable();self.addCleanup(self.settings_override.disable)
        self.p=Policy.current();self.p.latitude=35.1;self.p.longitude=129.0;self.p.save()
        self.at=timezone.now().replace(microsecond=0)
        self.c=Course.objects.create(title='수업',section='A',starts_at=self.at,ends_at=self.at+timedelta(hours=1))
        self.e=Enrollment.objects.create(course=self.c,department='학과',student_id='001234',name='홍길동')
        self.admin=get_user_model().objects.create_user('admin',password='Long-password-2026!',is_staff=True,is_superuser=True)
        self.staff=get_user_model().objects.create_user('assistant',password='Long-password-2026!',is_staff=True)

    def payload(self):
        return {'course':self.c.pk,'student_id':self.e.student_id,'name':self.e.name,'signature':signature(),
                'latitude':35.1,'longitude':129.0,'accuracy':20,'location_timestamp':timezone.now().timestamp()*1000}
    def attempt(self):
        return svc.exchange_qr(svc.qr_token())
    def attach_attempt(self,attempt):
        session=self.client.session;session['attempt']=str(attempt.pk);session.save()
        from django.http import HttpResponse
        response=HttpResponse()
        response.set_signed_cookie(settings.BROWSER_COOKIE_NAME,str(attempt.browser_id),salt='browser-identity')
        self.client.cookies[settings.BROWSER_COOKIE_NAME]=response.cookies[settings.BROWSER_COOKIE_NAME]

    def enter_browser(self,client):
        response=client.get(reverse('enter'),{'q':svc.qr_token()})
        self.assertEqual(response.status_code,302)
        return Attempt.objects.get(pk=client.session['attempt'])

    def browser_submit(self,client,payload=None):
        return client.post(reverse('submit'),json.dumps(payload or self.payload()),content_type='application/json')

    def test_browser_binding_blocks_other_student_but_allows_other_course(self):
        a=self.enter_browser(self.client)
        self.assertTrue(self.client.cookies[settings.BROWSER_COOKIE_NAME]['httponly'])
        self.assertEqual(self.browser_submit(self.client).status_code,200)
        a.browser.refresh_from_db();self.assertEqual(a.browser.student_id,self.e.student_id)
        Enrollment.objects.create(course=self.c,student_id='999',name='다른학생')
        second=Course.objects.create(title='다음 수업',starts_at=self.c.starts_at,ends_at=self.c.ends_at)
        Enrollment.objects.create(course=second,student_id=self.e.student_id,name=self.e.name)
        b=self.enter_browser(self.client);self.assertEqual(b.browser_id,a.browser_id)
        response=self.client.get(reverse('checkin'));self.assertContains(response,'readonly')
        payload=self.payload();payload.update(student_id='999',name='다른학생')
        rejected=self.browser_submit(self.client,payload)
        self.assertEqual(rejected.status_code,400)
        self.assertIn('브라우저',rejected.json()['error'])
        self.assertEqual(Attendance.objects.count(),1)
        payload=self.payload();payload['course']=second.pk
        self.assertEqual(self.browser_submit(self.client,payload).status_code,200)
        self.assertEqual(Attendance.objects.count(),2)

    def test_failed_submit_does_not_bind_and_cookie_required(self):
        a=self.enter_browser(self.client)
        payload=self.payload();payload['signature']=''
        self.assertEqual(self.browser_submit(self.client,payload).status_code,400)
        a.browser.refresh_from_db();self.assertEqual(a.browser.student_id,'')
        cookie=self.client.cookies[settings.BROWSER_COOKIE_NAME].value
        self.client.cookies[settings.BROWSER_COOKIE_NAME]=cookie+'tampered'
        self.assertEqual(self.browser_submit(self.client).status_code,400)
        del self.client.cookies[settings.BROWSER_COOKIE_NAME]
        self.assertEqual(self.browser_submit(self.client).status_code,400)
        self.assertFalse(Attendance.objects.exists())

    def test_preopened_attempt_uses_latest_binding_and_other_browser_is_independent(self):
        first=self.enter_browser(self.client)
        preopened=self.enter_browser(self.client)
        svc.submit(first.pk,self.payload())
        Enrollment.objects.create(course=self.c,student_id='999',name='다른학생')
        payload=self.payload();payload.update(student_id='999',name='다른학생')
        with self.assertRaisesMessage(svc.Rejected,'브라우저'):
            svc.submit(preopened.pk,payload)
        other=Client();other_attempt=self.enter_browser(other)
        self.assertNotEqual(other_attempt.browser_id,first.browser_id)
        self.assertEqual(self.browser_submit(other,payload).status_code,200)

    def test_binding_survives_staff_logout_and_new_session(self):
        first=self.enter_browser(self.client)
        self.assertEqual(self.browser_submit(self.client).status_code,200)
        self.client.force_login(self.staff)
        self.client.post(reverse('logout'))
        second=self.enter_browser(self.client)
        self.assertEqual(first.browser_id,second.browser_id)
        self.assertEqual(second.browser.student_id,self.e.student_id)

    def test_staff_changes_browser_identity_and_revokes_old_attempts(self):
        a=self.enter_browser(self.client)
        self.browser_submit(self.client)
        b=self.enter_browser(self.client)
        Enrollment.objects.create(course=self.c,student_id='999',name='다른학생')
        staff=Client();staff.force_login(self.staff)
        url=reverse('browser_identity')
        data={'code':a.browser.support_code,'revision':'1','student_id':'999','name':'다른학생','reason':'본인 확인 후 오입력 정정'}
        self.assertEqual(staff.post(url,data).status_code,302)
        a.browser.refresh_from_db();self.assertEqual(a.browser.student_id,'999')
        self.assertFalse(self.client.get(reverse('attempt_status')).json()['valid'])
        self.assertEqual(self.browser_submit(self.client).status_code,400)
        self.assertEqual(self.client.get(reverse('checkin')).status_code,400)
        self.assertEqual(Attendance.objects.get().enrollment.student_id,self.e.student_id)
        self.assertTrue(Audit.objects.filter(actor=self.staff,action='브라우저 학번 변경',details__reason=data['reason']).exists())
        self.assertContains(staff.post(url,data),'다른 담당자가 변경')
        self.enter_browser(self.client)
        payload=self.payload();payload.update(student_id='999',name='다른학생')
        self.assertEqual(self.browser_submit(self.client,payload).status_code,200)

    def test_browser_identity_change_requires_staff_valid_roster_reason_and_csrf(self):
        a=self.enter_browser(self.client)
        url=reverse('browser_identity')
        data={'code':a.browser.support_code,'revision':'1','student_id':self.e.student_id,'name':self.e.name,'reason':'확인'}
        self.assertEqual(self.client.post(url,data).status_code,302)
        staff=Client();staff.force_login(self.staff)
        self.assertContains(staff.post(url,{**data,'reason':''}),'변경 사유')
        self.assertContains(staff.post(url,{**data,'name':'없는학생'}),'명단에 등록된')
        a.browser.refresh_from_db();self.assertEqual(a.browser.student_id,'')
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.staff)
        self.assertEqual(strict.post(url,data).status_code,403)

    def test_sandbox_reset_removes_bindings_but_scenario_changes_keep_them(self):
        with override_settings(SANDBOX=True):
            a=self.enter_browser(self.client);self.browser_submit(self.client)
            staff=Client();staff.force_login(self.staff)
            staff.post(reverse('sandbox'),{'action':'normal'})
            self.assertEqual(BrowserIdentity.objects.get(pk=a.browser_id).student_id,self.e.student_id)
            self.assertEqual(self.enter_browser(self.client).browser_id,a.browser_id)
            svc.reset_sandbox(self.admin)
            self.assertFalse(BrowserIdentity.objects.exists())
            fresh=self.enter_browser(self.client)
            self.assertNotEqual(fresh.browser_id,a.browser_id)
            self.assertEqual(fresh.browser.student_id,'')

    def test_time_boundaries(self):
        cases=[(-601,None),(-600,'present'),(900,'present'),(901,'late'),(3599,'late'),(3600,None)]
        for seconds,expected in cases:
            with self.subTest(seconds=seconds):
                if expected is None:
                    with self.assertRaises(svc.Rejected):svc.course_status(self.c,self.p,self.at+timedelta(seconds=seconds))
                else:self.assertEqual(svc.course_status(self.c,self.p,self.at+timedelta(seconds=seconds)),expected)

    def test_valid_submit_and_idempotent_retry(self):
        a=self.attempt();record=svc.submit(a.pk,self.payload())
        same=svc.submit(a.pk,self.payload())
        self.assertEqual(record.pk,same.pk);self.assertEqual(Attendance.objects.count(),1)
        self.assertTrue(record.signature.storage.exists(record.signature.name))
        self.assertEqual(record.status,'present')

    def test_different_session_cannot_disclose_or_overwrite_existing_record(self):
        record=svc.submit(self.attempt().pk,self.payload())
        with self.assertRaisesMessage(svc.Rejected,'이미 처리된'):svc.submit(self.attempt().pk,self.payload())
        record.refresh_from_db();self.assertEqual(record.status,'present')

    def test_expired_and_tampered_qr(self):
        for token in [svc.qr_token(expired=True),svc.qr_token()+'x','bad']:
            with self.assertRaises(svc.Rejected):svc.exchange_qr(token)

    def test_cross_environment_qr_rejected(self):
        token=svc.qr_token()
        with override_settings(SANDBOX=not settings.SANDBOX):
            with self.assertRaises(svc.Rejected):svc.exchange_qr(token)

    def test_writing_expired(self):
        a=self.attempt();a.expires_at=svc.now()-timedelta(seconds=1);a.save()
        with self.assertRaises(svc.Rejected):svc.submit(a.pk,self.payload())
        self.assertFalse(Attendance.objects.exists())

    def test_submission_after_class_end_even_with_valid_attempt(self):
        a=self.attempt();self.c.ends_at=self.at-timedelta(seconds=1);self.c.starts_at=self.at-timedelta(hours=1);self.c.save()
        with self.assertRaises(svc.Rejected):svc.submit(a.pk,self.payload())

    def test_wrong_name_and_course_rejected(self):
        payload=self.payload();payload['name']='다른학생'
        with self.assertRaises(svc.Rejected):svc.submit(self.attempt().pk,payload)

    def test_location_rejections(self):
        for change in [{'latitude':36.1},{'accuracy':900},{'latitude':float('nan')},{'longitude':190},{'accuracy':-1},{'location_timestamp':0}]:
            with self.subTest(change=change):
                payload=self.payload();payload.update(change)
                with self.assertRaises(svc.Rejected):svc.location_check(self.p,payload)

    def test_live_ignores_mock_location_and_test_clock(self):
        with override_settings(SANDBOX=False):
            self.p.location_mode='inside';self.p.test_time=self.at-timedelta(days=5);self.p.test_reference=timezone.now();self.p.save()
            self.assertLess(abs((svc.now(self.p)-timezone.now()).total_seconds()),2)
            with self.assertRaises(svc.Rejected):svc.location_check(self.p,{})
            with self.assertRaises(svc.Rejected):svc.reset_sandbox()

    def test_blank_or_invalid_signature(self):
        for data in ['', 'data:image/svg+xml;base64,AAAA','data:image/png;base64,???']:
            with self.assertRaises(svc.Rejected):svc.signature_image(data)
        im=Image.new('RGB',(300,100),'white');out=io.BytesIO();im.save(out,format='PNG')
        with self.assertRaises(svc.Rejected):svc.signature_image('data:image/png;base64,'+base64.b64encode(out.getvalue()).decode())

    def test_sandbox_reset_revokes_sessions_and_preserves_accounts(self):
        with override_settings(SANDBOX=True):
            record=svc.submit(self.attempt().pk,self.payload());path=record.signature.name;storage=record.signature.storage
            old=svc.qr_token()
            with self.captureOnCommitCallbacks(execute=True):svc.reset_sandbox(self.admin)
            self.assertEqual(Course.objects.count(),3);self.assertEqual(Enrollment.objects.count(),210)
            self.assertFalse(Attendance.objects.exists());self.assertFalse(Attempt.objects.exists())
            self.assertFalse(storage.exists(path));self.assertTrue(get_user_model().objects.filter(pk=self.admin.pk).exists())
            with self.assertRaises(svc.Rejected):svc.exchange_qr(old)

    def test_mock_location_is_explicit_in_record(self):
        with override_settings(SANDBOX=True):
            self.p.location_mode='inside';self.p.save()
            payload=self.payload();payload.pop('latitude')
            record=svc.submit(self.attempt().pk,payload)
            self.assertEqual(record.location_source,'mock-inside');self.assertIsNone(record.latitude)

    def test_student_cannot_read_private_pages_or_signature(self):
        record=svc.submit(self.attempt().pk,self.payload())
        for name,args in [('dashboard',[]),('accounts',[]),('export',[]),('signature',[record.pk]),('course',[self.c.pk])]:
            self.assertEqual(self.client.get(reverse(name,args=args)).status_code,302)

    def test_staff_cannot_administer_system(self):
        self.client.force_login(self.staff)
        for name in ['accounts','system']:
            self.assertEqual(self.client.get(reverse(name)).status_code,403)
            self.assertEqual(self.client.post(reverse(name),{}).status_code,403)

    def test_all_staff_screens_render(self):
        self.client.force_login(self.admin)
        for name,args in [('dashboard',[]),('courses',[]),('course_new',[]),('course_edit',[self.c.pk]),('course',[self.c.pk]),('record',[self.e.pk]),('import',[self.c.pk]),('location',[]),('qr',[]),('qr_data',[]),('accounts',[]),('system',[]),('audit',[])]:
            with self.subTest(name=name):self.assertEqual(self.client.get(reverse(name,args=args)).status_code,200)
        if settings.SANDBOX:self.assertEqual(self.client.get(reverse('sandbox')).status_code,200)
        else:self.assertEqual(self.client.get(reverse('sandbox')).status_code,404)

    def test_checkin_and_completed_flow(self):
        self.attach_attempt(self.attempt())
        response=self.client.get(reverse('checkin'));self.assertEqual(response.status_code,200)
        response=self.client.post(reverse('submit'),data=json.dumps(self.payload()),content_type='application/json')
        self.assertEqual(response.status_code,200)
        response=self.client.get(reverse('complete'));self.assertContains(response,'출석 완료')

    def test_submission_requires_csrf(self):
        client=Client(enforce_csrf_checks=True)
        response=client.post(reverse('submit'),data=json.dumps(self.payload()),content_type='application/json')
        self.assertEqual(response.status_code,403)

    def test_login_csrf_origin_and_referrer_policy(self):
        client=Client(enforce_csrf_checks=True)
        response=client.get(reverse('login'))
        self.assertEqual(response['Referrer-Policy'],'same-origin')
        csrf=client.cookies[settings.CSRF_COOKIE_NAME].value
        response=client.post(reverse('login'),{'username':'assistant','password':'Long-password-2026!','csrfmiddlewaretoken':csrf},HTTP_ORIGIN='http://testserver')
        self.assertEqual(response.status_code,302)
        self.assertEqual(client.get(reverse('dashboard')).status_code,200)

    def test_export_keeps_leading_zero_and_embeds_signature(self):
        svc.submit(self.attempt().pk,self.payload());self.client.force_login(self.staff)
        import openpyxl
        for with_signature in [False,True]:
            response=self.client.get(reverse('export'),{'signatures':'1' if with_signature else '0'})
            workbook=openpyxl.load_workbook(io.BytesIO(b''.join(response.streaming_content)))
            sheet=workbook.active
            self.assertEqual(sheet['E2'].value,'001234');self.assertEqual(len(sheet._images),1 if with_signature else 0)

    def test_roster_import_preview_and_preserve_existing(self):
        import openpyxl
        book=openpyxl.Workbook();book.active.append(['학과','학번','이름']);book.active.append(['테스트','000001','학생1'])
        out=io.BytesIO();book.save(out);self.client.force_login(self.staff)
        url=reverse('import',args=[self.c.pk])
        r=self.client.post(url,{'action':'upload','file':SimpleUploadedFile('roster.xlsx',out.getvalue())});self.assertEqual(r.status_code,200)
        r=self.client.post(url,{'action':'map','department':'0','student_id':'1','name':'2'});self.assertContains(r,'000001')
        self.assertFalse(Enrollment.objects.filter(student_id='000001').exists())
        r=self.client.post(url,{'action':'confirm'});self.assertEqual(r.status_code,302)
        self.assertTrue(Enrollment.objects.filter(pk=self.e.pk).exists());self.assertTrue(Enrollment.objects.filter(student_id='000001').exists())

    def test_formula_roster_rejected(self):
        import openpyxl
        from .views import read_xlsx
        book=openpyxl.Workbook();book.active.append(['학과','학번','이름']);book.active.append(['a','=1+1','b'])
        out=io.BytesIO();book.save(out)
        with self.assertRaises(svc.Rejected):read_xlsx(SimpleUploadedFile('bad.xlsx',out.getvalue()))

    def test_manual_correction_audit_and_stale_write(self):
        from .views import revision
        self.client.force_login(self.staff)
        url=reverse('record',args=[self.e.pk])
        payload={'status':'late','attended_at':timezone.localtime(self.at).strftime('%Y-%m-%dT%H:%M'),'reason':'위치 오류 현장 확인','revision':'new'}
        self.assertEqual(self.client.post(url,payload).status_code,302)
        record=Attendance.objects.get(enrollment=self.e);self.assertEqual(record.method,'manual');self.assertFalse(record.signature)
        payload['status']='absent'
        self.assertContains(self.client.post(url,payload),'다른 작업에서 기록이 변경')
        record.refresh_from_db();self.assertEqual(record.status,'late');self.assertTrue(Audit.objects.filter(action='출석 정정').exists())

    def test_test_buttons_and_expiration(self):
        with override_settings(SANDBOX=True):
            self.client.force_login(self.staff)
            r=self.client.post(reverse('sandbox'),{'action':'late'});self.assertEqual(r.status_code,302)
            self.p.refresh_from_db();self.assertEqual(svc.course_status(self.c,self.p),'late')
            attempt=self.attempt()
            self.client.post(reverse('sandbox'),{'action':'expire'})
            attempt.refresh_from_db()
            with self.assertRaises(svc.Rejected):svc.valid_attempt(attempt,self.p)

    def test_unsafe_spreadsheet_cells_are_neutralized(self):
        from .views import safe_cell
        self.assertEqual(safe_cell('=HYPERLINK("bad")'),'\'=HYPERLINK("bad")')
        self.assertEqual(safe_cell('0012'),'0012')

    def test_anonymous_status_never_returns_roster(self):
        response=self.client.get(reverse('attempt_status'))
        self.assertNotIn('name',response.json());self.assertNotIn('student_id',response.json())
