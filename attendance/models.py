import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

class Policy(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    latitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    radius = models.PositiveIntegerField(default=200, validators=[MinValueValidator(1), MaxValueValidator(10000)])
    max_accuracy = models.PositiveIntegerField(default=150, validators=[MinValueValidator(1), MaxValueValidator(10000)])
    before_minutes = models.PositiveIntegerField(default=10, validators=[MaxValueValidator(180)])
    late_minutes = models.PositiveIntegerField(default=15, validators=[MaxValueValidator(180)])
    qr_seconds = models.PositiveIntegerField(default=60, validators=[MinValueValidator(15), MaxValueValidator(300)])
    writing_seconds = models.PositiveIntegerField(default=300, validators=[MinValueValidator(30), MaxValueValidator(1800)])
    generation = models.PositiveIntegerField(default=1)
    test_time = models.DateTimeField(null=True, blank=True)
    test_reference = models.DateTimeField(null=True, blank=True)
    location_mode = models.CharField(max_length=20, default='real', choices=[('real','실제 위치'),('inside','모의: 구역 안'),('outside','모의: 구역 밖'),('inaccurate','모의: 정확도 부족'),('unavailable','모의: 측정 실패')])

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

class Course(models.Model):
    title = models.CharField('수업명', max_length=120)
    section = models.CharField('분반', max_length=40, blank=True)
    starts_at = models.DateTimeField('시작 시각')
    ends_at = models.DateTimeField('종료 시각')
    active = models.BooleanField('접수 사용', default=True)
    class Meta:
        ordering = ['starts_at', 'title', 'section']
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='course_end_after_start')]
    def __str__(self):
        return f'{self.title} {self.section}'.strip()

class Enrollment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='enrollments')
    department = models.CharField('학과', max_length=100, blank=True)
    student_id = models.CharField('학번', max_length=40)
    name = models.CharField('이름', max_length=80)
    class Meta:
        ordering = ['student_id']
        constraints = [models.UniqueConstraint(fields=['course','student_id'], name='unique_course_student')]

class Attempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation = models.PositiveIntegerField()
    opened_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    completed = models.ForeignKey('Attendance', null=True, blank=True, on_delete=models.SET_NULL)

class Attendance(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.PROTECT, related_name='attendance')
    status = models.CharField(max_length=10, choices=[('present','출석'),('late','지각'),('absent','결석')])
    attended_at = models.DateTimeField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=10, default='self', choices=[('self','학생 제출'),('manual','수동 처리')])
    signed_name = models.CharField(max_length=80, blank=True)
    signature = models.FileField(upload_to='signatures/%Y/%m/', blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    location_source = models.CharField(max_length=20, blank=True)
    policy_snapshot = models.JSONField(default=dict)
    reason = models.TextField(blank=True)

class Audit(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=160, blank=True)
    details = models.JSONField(default=dict)
    class Meta:
        ordering = ['-created_at', '-id']

class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window = models.BigIntegerField()
    count = models.PositiveIntegerField(default=0)
