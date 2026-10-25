from django import forms
from .models import Course, Policy, Enrollment

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title','section','starts_at','ends_at','active']
        widgets = {k: forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local'}) for k in ['starts_at','ends_at']}
    def clean(self):
        data = super().clean()
        if data.get('starts_at') and data.get('ends_at') and data['ends_at'] <= data['starts_at']:
            raise forms.ValidationError('종료 시각은 시작 시각보다 늦어야 합니다.')
        return data

class LocationForm(forms.ModelForm):
    class Meta:
        model = Policy
        fields = ['latitude','longitude','radius','max_accuracy']
        labels = {'latitude':'중심 위도','longitude':'중심 경도','radius':'인정 반경 (m)','max_accuracy':'최대 위치 오차 (m)'}
    def clean(self):
        data = super().clean()
        if data.get('latitude') is None or data.get('longitude') is None:
            raise forms.ValidationError('중심 위도와 경도를 모두 입력해주세요.')
        return data

class PolicyForm(forms.ModelForm):
    class Meta:
        model = Policy
        fields = ['before_minutes','late_minutes','writing_seconds']
        labels = {'before_minutes':'시작 전 접수 (분)','late_minutes':'시작 후 출석 인정 (분)',
                  'writing_seconds':'작성 시간 (초)'}

class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['department','student_id','name']

class CorrectionForm(forms.Form):
    status = forms.ChoiceField(label='처리 결과',choices=[('present','출석'),('late','지각'),('absent','결석')])
    attended_at = forms.DateTimeField(label='인정 시각',required=False,widget=forms.DateTimeInput(attrs={'type':'datetime-local'},format='%Y-%m-%dT%H:%M'))
    reason = forms.CharField(label='처리 사유',min_length=3,max_length=2000,widget=forms.Textarea(attrs={'rows':3}))
    revision = forms.CharField(widget=forms.HiddenInput,required=False)
    def clean(self):
        data=super().clean()
        if data.get('status') != 'absent' and not data.get('attended_at'):
            self.add_error('attended_at','출석·지각은 인정 시각이 필요합니다.')
        if data.get('status')=='absent':
            data['attended_at']=None
        return data


class GuestCorrectionForm(CorrectionForm):
    department = forms.CharField(label='학과',max_length=100)
    student_id = forms.CharField(label='학번',max_length=40)
    name = forms.CharField(label='이름',max_length=80)
    guest_date = forms.DateField(label='출석 일자',widget=forms.DateInput(attrs={'type':'date'}))
    status = forms.ChoiceField(label='처리 결과',choices=[('present','출석'),('absent','결석')])

    def clean(self):
        data = super().clean()
        from django.utils import timezone
        at = data.get('attended_at')
        if at and data.get('guest_date') != timezone.localtime(at).date():
            self.add_error('attended_at','인정 시각과 출석 일자가 일치해야 합니다.')
        return data
