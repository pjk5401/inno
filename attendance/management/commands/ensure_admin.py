import getpass
import json
import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from attendance.services import audit

class Command(BaseCommand):
    help='Create or reset a staff account. Secrets are read interactively or from stdin only.'
    def add_arguments(self, parser):
        parser.add_argument('--json-stdin',action='store_true')
    def handle(self,*args,**options):
        if options['json_stdin']:
            data=json.load(sys.stdin);username=data['username'];password=data['password'];admin=data.get('admin',True)
        else:
            username=input('아이디: ').strip()
            password=getpass.getpass('새 비밀번호 (10자 이상): ')
            if password!=getpass.getpass('비밀번호 확인: '):
                raise CommandError('비밀번호가 일치하지 않습니다.')
            admin=True
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_.@+-]{1,150}',username):
            raise CommandError('아이디 형식이 올바르지 않습니다.')
        User=get_user_model()
        user,_=User.objects.get_or_create(username=username)
        try:
            validate_password(password,user)
        except ValidationError as e:
            raise CommandError(' '.join(e.messages))
        user.is_active=True;user.is_staff=True;user.is_superuser=admin;user.set_password(password);user.save()
        audit(None,'서버 계정 설정',username,admin=admin)
        self.stdout.write(self.style.SUCCESS('계정을 설정했습니다.'))
