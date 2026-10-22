import base64
import binascii
import hashlib
import hmac
import io
import math
import time
import uuid
from datetime import timedelta
from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import Policy, Course, Enrollment, Attendance, Attempt, Audit, RateBucket

class Rejected(ValueError):
    pass

def now(policy=None):
    actual = timezone.now()
    p = policy or Policy.current()
    if settings.SANDBOX and p.test_time and p.test_reference:
        return p.test_time + (actual - p.test_reference)
    return actual

def snapshot(p):
    return {k: getattr(p, k) for k in ['latitude','longitude','radius','max_accuracy',
        'before_minutes','late_minutes','qr_seconds','writing_seconds','generation']}

def audit(user, action, target='', **details):
    Audit.objects.create(actor=user if user and user.is_authenticated else None,
                         action=action, target=str(target), details=details)

def throttle(key, limit, seconds=60):
    digest = hmac.new(settings.SECRET_KEY.encode(), key.encode(), hashlib.sha256).hexdigest()
    window = int(time.time()) // seconds
    with transaction.atomic():
        bucket, _ = RateBucket.objects.get_or_create(key=digest, defaults={'window':window})
        bucket = RateBucket.objects.select_for_update().get(pk=digest)
        if bucket.window != window:
            bucket.window, bucket.count = window, 0
        bucket.count += 1
        bucket.save()
        allowed = bucket.count <= limit
    if not allowed:
        raise Rejected('요청이 너무 많습니다. 잠시 후 다시 시도해주세요.')

def qr_token(p=None, expired=False):
    p = p or Policy.current()
    stamp = int(now(p).timestamp())
    slot = stamp // p.qr_seconds * p.qr_seconds
    if expired:
        slot -= p.qr_seconds
    return signing.dumps({'env': settings.SANDBOX, 'generation': p.generation,
                          'start': slot, 'end': slot + p.qr_seconds}, salt='attendance-qr')

def exchange_qr(token):
    with transaction.atomic():
        p = Policy.objects.select_for_update().get(pk=Policy.current().pk)
        try:
            data = signing.loads(token, salt='attendance-qr')
        except (signing.BadSignature, ValueError, TypeError):
            raise Rejected('올바른 QR이 아닙니다. 현장의 최신 QR을 스캔해주세요.')
        stamp = now(p).timestamp()
        if (data.get('env') != settings.SANDBOX or data.get('generation') != p.generation
            or not data.get('start', math.inf) <= stamp < data.get('end', -math.inf)):
            raise Rejected('QR이 만료되었거나 테스트가 초기화되었습니다. 최신 QR을 스캔해주세요.')
        return Attempt.objects.create(generation=p.generation, opened_at=now(p),
                                      expires_at=now(p)+timedelta(seconds=p.writing_seconds))

def valid_attempt(attempt, p):
    if not attempt or attempt.generation != p.generation:
        raise Rejected('접속이 초기화되었습니다. 현장의 새 QR을 스캔해주세요.')
    if now(p) >= attempt.expires_at:
        raise Rejected('작성 시간이 만료되었습니다. 입력을 유지한 채 새 QR을 스캔해주세요.')

def course_status(course, p=None, at=None):
    p = p or Policy.current()
    at = at or now(p)
    if not course.active:
        raise Rejected('접수가 중지된 수업입니다.')
    if at < course.starts_at - timedelta(minutes=p.before_minutes):
        raise Rejected('아직 출석 접수 전입니다.')
    if at >= course.ends_at:
        raise Rejected('수업이 종료되어 접수가 마감되었습니다. 필요한 경우 조교에게 문의해주세요.')
    return 'present' if at <= course.starts_at + timedelta(minutes=p.late_minutes) else 'late'

def distance_m(lat1, lon1, lat2, lon2):
    a,b = math.radians(lat1), math.radians(lat2)
    dlat,dlon = b-a, math.radians(lon2-lon1)
    h = math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlon/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))

def location_check(p, payload):
    if settings.SANDBOX and p.location_mode != 'real':
        if p.location_mode == 'outside':
            raise Rejected('[모의 위치] 인정 구역 밖입니다.')
        if p.location_mode == 'inaccurate':
            raise Rejected('[모의 위치] 위치 정확도가 부족합니다. 다시 측정하거나 조교에게 문의해주세요.')
        if p.location_mode == 'unavailable':
            raise Rejected('[모의 위치] 위치를 측정할 수 없습니다. 조교에게 문의해주세요.')
        return {'latitude':None,'longitude':None,'accuracy':None,'location_source':'mock-inside'}
    if p.latitude is None or p.longitude is None:
        raise Rejected('출석 인정 구역이 설정되지 않았습니다. 조교에게 문의해주세요.')
    try:
        lat, lon, acc, stamp = [float(payload[k]) for k in ['latitude','longitude','accuracy','location_timestamp']]
        if not all(math.isfinite(v) for v in [lat,lon,acc,stamp]):
            raise ValueError()
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and acc > 0):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise Rejected('위치 정보가 없습니다. 위치 권한을 허용한 뒤 다시 제출해주세요.')
    # Browser position timestamps refer to actual time, not the sandbox clock.
    age = timezone.now().timestamp() - stamp/1000
    if age > 60 or age < -15:
        raise Rejected('위치 정보가 오래되었거나 휴대폰 시각이 맞지 않습니다. 다시 측정해주세요.')
    if acc > p.max_accuracy:
        raise Rejected(f'위치 오차가 큽니다(약 {round(acc)}m). 다시 측정하거나 조교에게 문의해주세요.')
    if distance_m(lat,lon,p.latitude,p.longitude) > p.radius:
        raise Rejected('출석 인정 구역 밖입니다. 현장에서 다시 측정해주세요.')
    return {'latitude':lat,'longitude':lon,'accuracy':acc,'location_source':'device'}

def signature_image(data):
    if not isinstance(data, str) or len(data)>1500000 or not data.startswith('data:image/png;base64,'):
        raise Rejected('서명을 작성해주세요.')
    try:
        raw = base64.b64decode(data.split(',',1)[1], validate=True)
        im = Image.open(io.BytesIO(raw))
        if im.format != 'PNG' or im.width > 2000 or im.height > 1000 or im.width < 20 or im.height < 20:
            raise ValueError()
        im.load()
        rgba = im.convert('RGBA')
        white = Image.new('RGBA', rgba.size, 'white')
        white.alpha_composite(rgba)
        rgb = white.convert('RGB')
        extrema = rgb.convert('L').getextrema()
        if extrema[0] > 240 or extrema[1]-extrema[0] < 20:
            raise ValueError()
        buf = io.BytesIO()
        rgb.save(buf, format='PNG', optimize=True)
        return buf.getvalue()
    except (ValueError, binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise Rejected('서명 이미지가 올바르지 않습니다. 다시 서명해주세요.')

def submit(attempt_id, payload):
    saved_file = None
    try:
        with transaction.atomic():
            p = Policy.objects.select_for_update().get(pk=Policy.current().pk)
            attempt = Attempt.objects.select_for_update().filter(pk=attempt_id).first()
            if attempt and attempt.generation == p.generation and attempt.completed_id:
                return attempt.completed
            valid_attempt(attempt,p)
            at = now(p)
            try:
                course = Course.objects.get(pk=int(payload.get('course',0)))
            except (Course.DoesNotExist,ValueError,TypeError):
                raise Rejected('수업을 선택해주세요.')
            state = course_status(course,p,at)
            sid = str(payload.get('student_id','')).strip()
            name = str(payload.get('name','')).strip()
            enrollment = Enrollment.objects.select_for_update().filter(course=course,student_id=sid,name=name).first()
            if not enrollment:
                raise Rejected('수업 명단과 학번·이름이 일치하지 않습니다. 입력을 확인하거나 조교에게 문의해주세요.')
            location = location_check(p,payload)
            existing = Attendance.objects.filter(enrollment=enrollment).first()
            if existing:
                # Do not expose somebody else's record based only on a known name/ID.
                raise Rejected('이미 처리된 출석입니다. 중복 제출은 반영하지 않습니다. 확인이 필요하면 조교에게 문의해주세요.')
            image = signature_image(payload.get('signature'))
            record = Attendance(enrollment=enrollment,status=state,attended_at=at,
                                signed_name=name,policy_snapshot=snapshot(p),**location)
            record.signature.save(f'{uuid.uuid4().hex}.png',ContentFile(image),save=False)
            saved_file = record.signature
            record.save()
            attempt.completed = record
            attempt.save(update_fields=['completed'])
            return record
    except Exception:
        if saved_file:
            saved_file.storage.delete(saved_file.name)
        raise

def display_status(enrollment, p=None):
    try:
        return enrollment.attendance.get_status_display()
    except Attendance.DoesNotExist:
        return '결석' if now(p) >= enrollment.course.ends_at else '미출석'

def set_test_time(p, value):
    if not settings.SANDBOX:
        raise Rejected('운영 환경에서는 테스트 시간을 설정할 수 없습니다.')
    p.test_time = value
    p.test_reference = timezone.now()
    p.save()

def reset_sandbox(user=None):
    if not settings.SANDBOX:
        raise Rejected('운영 환경에서는 초기화할 수 없습니다.')
    with transaction.atomic():
        p = Policy.objects.select_for_update().get(pk=Policy.current().pk)
        files = list(Attendance.objects.exclude(signature='').values_list('signature',flat=True))
        storage = Attendance._meta.get_field('signature').storage
        Attempt.objects.all().delete()
        Attendance.objects.all().delete()
        Enrollment.objects.all().delete()
        Course.objects.all().delete()
        Audit.objects.all().delete()
        p.generation += 1
        p.before_minutes,p.late_minutes,p.qr_seconds,p.writing_seconds = 10,15,60,300
        p.location_mode = 'inside'
        base = timezone.localtime().replace(hour=10,minute=0,second=0,microsecond=0)
        set_test_time(p,base)
        for i in range(1,4):
            c = Course.objects.create(title=f'가상수업 {i}',section=f'{i}분반',starts_at=base,ends_at=base+timedelta(hours=1))
            Enrollment.objects.bulk_create([Enrollment(course=c,department='가상학과',student_id=f'2026{n:04}',name=f'가상학생{n:02}') for n in range(1,71)])
        audit(user,'테스트 초기화','sandbox',generation=p.generation)
        transaction.on_commit(lambda: [storage.delete(f) for f in files])
    return p
