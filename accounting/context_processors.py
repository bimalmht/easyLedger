def company_context(request):
    return {
        'current_company': getattr(request, 'company', None),
    }