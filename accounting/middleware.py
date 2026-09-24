from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseForbidden
from .models import Company

class MultiCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow static files and Django Admin bypass
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return self.get_response(request)

        exempt_paths = [reverse('login'), reverse('logout')]
        if request.path in exempt_paths:
            return self.get_response(request)

        # 1. Require authentication
        if not request.user.is_authenticated:
            return redirect('login')

        # 2. Resolve company based on credentials
        if request.user.is_superuser:
            active_id = request.session.get('active_company_id')
            current_company = Company.objects.filter(id=active_id).first() if active_id else Company.objects.first()
            request.company = current_company
        else:
            profile = getattr(request.user, 'profile', None)
            request.company = profile.company if profile else None

        # 3. Guard against unassigned users
        if not request.company:
            return HttpResponseForbidden("Access Denied: Your account is not assigned to an active company. Please contact the administrator via the Django Admin panel.")

        return self.get_response(request)