from django.contrib import admin
from accounts.models import GHLAppointment, GHLUser

admin.site.register(GHLUser)
admin.site.register(GHLAppointment)

# Register your models here.
