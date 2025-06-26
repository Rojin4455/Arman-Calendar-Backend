from django.shortcuts import render
from decouple import config
import requests
from django.http import JsonResponse
import json
from django.shortcuts import redirect, render
from ghl_auth.models import GHLAuthCredentials
from django.views.decorators.csrf import csrf_exempt
from ghl_auth.services import get_location_name
from urllib.parse import urlencode
from accounts.tasks import async_fetch_all_contacts

from django.views import View
from django.utils.decorators import method_decorator
from accounts.models import GHLUser
from ghl_auth.services import create_or_update_contact, delete_contact


# Create your views here.

GHL_CLIENT_ID = config("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = config("GHL_CLIENT_SECRET")
GHL_REDIRECTED_URI = config("GHL_REDIRECTED_URI")
FRONTEND_URL = config("FRONTEND_URL")
TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"
SCOPE = config("SCOPE")
BASE_URL = config("BASE_URI")


def auth_connect(request):
    auth_url = ("https://marketplace.gohighlevel.com/oauth/chooselocation?response_type=code&"
                f"redirect_uri={GHL_REDIRECTED_URI}&"
                f"client_id={GHL_CLIENT_ID}&"
                f"scope={SCOPE}"
                )
    return redirect(auth_url)



def callback(request):
    
    code = request.GET.get('code')

    if not code:
        return JsonResponse({"error": "Authorization code not received from OAuth"}, status=400)

    return redirect(f'{BASE_URL}/api/access/auth/tokens?code={code}')


def tokens(request):
    authorization_code = request.GET.get("code")

    if not authorization_code:
        return JsonResponse({"error": "Authorization code not found"}, status=400)

    data = {
        "grant_type": "authorization_code",
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
        "redirect_uri": GHL_REDIRECTED_URI,
        "code": authorization_code,
    }

    response = requests.post(TOKEN_URL, data=data)

    try:
        response_data = response.json()
        if not response_data:
            return
        print("response.data: ", response_data)
        if not response_data.get('access_token'):
            return render(request, 'onboard.html', context={
                "message": "Invalid JSON response from API",
                "status_code": response.status_code,
                "response_text": response.text[:400]
            }, status=400)
        

        location_name, timezone = get_location_name(location_id=response_data.get("locationId"), access_token=response_data.get('access_token'))
        

        obj, created = GHLAuthCredentials.objects.update_or_create(
            location_id= response_data.get("locationId"),
            defaults={
                "access_token": response_data.get("access_token"),
                "refresh_token": response_data.get("refresh_token"),
                "expires_in": response_data.get("expires_in"),
                "scope": response_data.get("scope"),
                "user_type": response_data.get("userType"),
                "company_id": response_data.get("companyId"),
                "user_id":response_data.get("userId"),
                "location_name":location_name,
                "timezone": timezone
            }
        )

        async_fetch_all_contacts.delay(
            location_id=response_data.get("locationId"),
            access_token=response_data.get("access_token")
        )
        query_params = urlencode({
            "locationId":response_data.get("locationId"),
        })

        frontend_url = f"{FRONTEND_URL}/admin/settings/sms-groups?{query_params}"
        
        return redirect(frontend_url)
        
    except requests.exceptions.JSONDecodeError:
        frontend_url = f"{FRONTEND_URL}/admin/error-onboard"
        return redirect(frontend_url)
    







@method_decorator(csrf_exempt, name='dispatch')
class GhlWebhookView(View):
    def post(self, request):
        try:
            webhook_data = json.loads(request.body)
            event_type = webhook_data.get("type")
            token = GHLAuthCredentials.objects.get(location_id = webhook_data.get("locationId"))



            if event_type == "UserCreate":
                self.handle_user_create(webhook_data, token)

            if event_type in ["ContactCreate", "ContactUpdate"]:
                create_or_update_contact(webhook_data)
            elif event_type == "ContactDelete":
                delete_contact(webhook_data)

            return JsonResponse({"message": "Handled"}, status=200)
        
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    

    

    def handle_user_create(self, data, token):

        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {token.access_token}',
        'Version': '2021-07-28'  # or '2021-04-15' for calendars endpoint
        }

        user_response = requests.get(
        f"https://services.leadconnectorhq.com/users/{data["id"]}",
        headers=headers
        )

        user = user_response.json()
        user_id = user["id"]
        GHLUser.objects.update_or_create(
            user_id=user_id,
            defaults={
                "first_name": user.get("firstName", ""),
                "last_name": user.get("lastName", ""),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "phone": user.get("phone", ""),
                "location_id": token.location_id,
            }
        )

    