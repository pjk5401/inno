from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from attendance.services import reset_sandbox

class Command(BaseCommand):
    help='Reset only the isolated sandbox database and seed fictional students.'
    def add_arguments(self,parser):
        parser.add_argument('--confirm',required=True)
    def handle(self,*args,**options):
        if not settings.SANDBOX or options['confirm']!='RESET':
            raise CommandError('테스트 환경과 RESET 확인이 필요합니다.')
        reset_sandbox();self.stdout.write('테스트 초기화 완료. 운영 데이터에는 접근하지 않았습니다.')
