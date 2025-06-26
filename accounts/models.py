from django.db import models
import uuid


class Contact(models.Model):
    contact_id = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    dnd = models.BooleanField(default=False)
    country = models.CharField(max_length=50, blank=True, null=True)
    date_added = models.DateTimeField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=list, blank=True)
    location_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    

class GHLUser(models.Model):
    user_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    calendar_id = models.CharField(max_length=50, null=True, blank=True)
    location_id = models.CharField(max_length=50, null=True, blank=True, default="")

    def __str__(self):
        return self.name
    

class RecurringAppointmentGroup(models.Model):
    """Model to group recurring appointments together"""
    group_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    interval = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ])
    total_count = models.PositiveIntegerField()
    original_start_time = models.DateTimeField()
    original_end_time = models.DateTimeField()
    contact_id = models.CharField(max_length=255)
    location_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'recurring_appointment_groups'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.interval} ({self.total_count} occurrences)"
    

class GHLAppointment(models.Model):
    ghl_appointment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    contact_id = models.CharField(max_length=100)
    recurring_group = models.ForeignKey(
        RecurringAppointmentGroup, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='appointments'
    )
    occurrence_number = models.PositiveIntegerField(null=True, blank=True)
    assigned_to = models.CharField(max_length=100)
    calendar_id = models.CharField(max_length=100)
    location_id = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    status = models.CharField(max_length=50, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'ghl_appointments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recurring_group', 'occurrence_number']),
            models.Index(fields=['contact_id']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['start_time']),
        ]


    def __str__(self):
        return self.title