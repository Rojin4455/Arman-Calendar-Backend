from django.urls import path
from .views import UpdateUserCalendarView, CalendarStatsView

urlpatterns = [
    path('users/<str:user_id>/update-calendar/', UpdateUserCalendarView.as_view(), name='update-calendar'),
    path('calendar-stats/', CalendarStatsView.as_view(), name='calendar-stats'),
    path('calendar-stats/<str:location_id>/', CalendarStatsView.as_view(), name='calendar-stats-by-location'),
]
