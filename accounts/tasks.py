import requests
from celery import shared_task
from ghl_auth.models import GHLAuthCredentials
from decouple import config
from accounts.services import fetch_all_contacts

@shared_task
def make_api_call():
    tokens = GHLAuthCredentials.objects.all()

    for credentials in tokens:
    
        print("credentials tokenL", credentials)
        refresh_token = credentials.refresh_token

        
        response = requests.post('https://services.leadconnectorhq.com/oauth/token', data={
            'grant_type': 'refresh_token',
            'client_id': config("GHL_CLIENT_ID"),
            'client_secret': config("GHL_CLIENT_SECRET"),
            'refresh_token': refresh_token
        })
        
        new_tokens = response.json()
        obj, created = GHLAuthCredentials.objects.update_or_create(
                location_id= new_tokens.get("locationId"),
                defaults={
                    "access_token": new_tokens.get("access_token"),
                    "refresh_token": new_tokens.get("refresh_token"),
                    "expires_in": new_tokens.get("expires_in"),
                    "scope": new_tokens.get("scope"),
                    "user_type": new_tokens.get("userType"),
                    "company_id": new_tokens.get("companyId"),
                    "user_id":new_tokens.get("userId"),

                }
            )
        print("refreshed: ", obj)


@shared_task
def async_fetch_all_contacts(location_id, access_token):
    fetch_all_contacts(location_id, access_token)



from accounts.models import RecurringAppointmentGroup
@shared_task
def deletion_task():

    r = RecurringAppointmentGroup.objects.all()

    for j in r:
        res = requests.delete(f"http://localhost:8000/api/accounts/recurring-groups/{j.group_id}/delete/")
        print(res.status_code, res.text)