from django.urls import path
from . import views as v

urlpatterns=[
    path('',v.home,name='home'),path('enter/',v.enter,name='enter'),
    path('checkin/',v.checkin,name='checkin'),path('checkin/submit/',v.submit,name='submit'),
    path('checkin/status/',v.attempt_status,name='attempt_status'),path('complete/',v.complete,name='complete'),
    path('health/',v.health,name='health'),path('staff/login/',v.staff_login,name='login'),
    path('staff/logout/',v.staff_logout,name='logout'),path('staff/',v.dashboard,name='dashboard'),
    path('staff/courses/',v.courses,name='courses'),path('staff/courses/new/',v.course_edit,name='course_new'),
    path('staff/courses/<int:pk>/',v.course_detail,name='course'),path('staff/courses/<int:pk>/edit/',v.course_edit,name='course_edit'),
    path('staff/courses/<int:pk>/import/',v.roster_import,name='import'),
    path('staff/courses/<int:course_id>/students/new/',v.enrollment_edit,name='enrollment_new'),
    path('staff/courses/<int:course_id>/students/<int:pk>/',v.enrollment_edit,name='enrollment_edit'),
    path('staff/records/<int:pk>/',v.record_detail,name='record'),path('staff/signatures/<int:pk>/',v.signature,name='signature'),
    path('staff/export/',v.export,name='export'),path('staff/location/',v.location,name='location'),
    path('staff/qr/',v.qr_display,name='qr'),path('staff/qr/data/',v.qr_data,name='qr_data'),
    path('staff/audit/',v.audit_log,name='audit'),path('staff/system/',v.system,name='system'),
    path('staff/accounts/',v.accounts,name='accounts'),path('staff/test-control/',v.sandbox,name='sandbox'),
]
