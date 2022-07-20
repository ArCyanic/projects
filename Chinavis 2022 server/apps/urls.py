from django.contrib import admin
from django.urls import path
from apps.views import *

urlpatterns = [

path('getnodebyid', getnodebyid),
path('getnodebyid1', getnodebyid1),
path('getedgebyid', getedgebyid),
path('getedgebyid1', getedgebyid1),
path('getnodecountlist', getnodecountlist),
path('getedgecountlist', getedgecountlist),
path('getcorebyid', getcorebyid),
path('getroadbyid', getroadbyid),
path('getgroupsinfo', getgroupsinfo),

]