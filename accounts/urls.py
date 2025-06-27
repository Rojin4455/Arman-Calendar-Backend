from django.urls import path
from accounts.views import (UpdateUserCalendarView,
                    CalendarStatsView,
                    AppointmentBookingView,
                    AppointmentUpdateView,
                    AppointmentDeleteView,
                    AppointmentListView,
                    AppointmentDetailView,
                    ContactSearchView,
                    GHLUserSearchView,
                    RecurringAppointmentGroupListView,
                    RecurringGroupAppointmentsView,
                    delete_recurring_group,
                    delete_single_appointment,
                    NonRecurringAppointmentsView
                    )

urlpatterns = [
    path('users/<str:user_id>/update-calendar/', UpdateUserCalendarView.as_view(), name='update-calendar'),
    path('calendar-stats/', CalendarStatsView.as_view(), name='calendar-stats'),
    path('calendar-stats/<str:location_id>/', CalendarStatsView.as_view(), name='calendar-stats-by-location'),
    path('appointments/', AppointmentListView.as_view(), name='appointment-list'),
    path('appointments/book/', AppointmentBookingView.as_view(), name='appointment-book'),
    # path('appointments/<int:appointment_id>/', AppointmentDetailView.as_view(), name='appointment-detail'),
    # path('appointments/<int:appointment_id>/update/', AppointmentUpdateView.as_view(), name='appointment-update'),
    # path('appointments/<int:appointment_id>/delete/', AppointmentDeleteView.as_view(), name='appointment-delete'),
    path('search/contacts/', ContactSearchView.as_view(), name='search-contacts'),
    path('search/users/', GHLUserSearchView.as_view(), name='search-users'),
    path('recurring-groups/',RecurringAppointmentGroupListView.as_view(),name='recurring-groups-list'),
    
    # Get all appointments under a specific recurring group
    path(
        'recurring-groups/<uuid:group_id>/appointments/',
        RecurringGroupAppointmentsView.as_view(),
        name='recurring-group-appointments'
    ),
    
    # Delete a recurring group (bulk delete)
    path(
        'recurring-groups/<uuid:group_id>/delete/',
        delete_recurring_group,
        name='delete-recurring-group'
    ),
    
    # Delete a single appointment
    path(
        'appointments/<int:appointment_id>/delete/',
        delete_single_appointment,
        name='delete-single-appointment'
    ),
    path('appointments/non-recurring/', NonRecurringAppointmentsView.as_view(), name='non_recurring_appointments'),

]