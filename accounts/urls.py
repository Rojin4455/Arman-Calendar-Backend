from django.urls import path
from .views import (UpdateUserCalendarView,
                    CalendarStatsView,
                    AppointmentBookingView,
                    AppointmentUpdateView,
                    AppointmentDeleteView,
                    AppointmentListView,
                    AppointmentDetailView,
                    ContactSearchView,
                    GHLUserSearchView
                    )

urlpatterns = [
    path('users/<str:user_id>/update-calendar/', UpdateUserCalendarView.as_view(), name='update-calendar'),
    path('calendar-stats/', CalendarStatsView.as_view(), name='calendar-stats'),
    path('calendar-stats/<str:location_id>/', CalendarStatsView.as_view(), name='calendar-stats-by-location'),
    path('appointments/', AppointmentListView.as_view(), name='appointment-list'),
    path('appointments/book/', AppointmentBookingView.as_view(), name='appointment-book'),
    path('appointments/<int:appointment_id>/', AppointmentDetailView.as_view(), name='appointment-detail'),
    path('appointments/<int:appointment_id>/update/', AppointmentUpdateView.as_view(), name='appointment-update'),
    path('appointments/<int:appointment_id>/delete/', AppointmentDeleteView.as_view(), name='appointment-delete'),
    path('search/contacts/', ContactSearchView.as_view(), name='search-contacts'),
    path('search/users/', GHLUserSearchView.as_view(), name='search-users'),
]