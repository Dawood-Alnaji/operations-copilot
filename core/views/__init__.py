from django.shortcuts import render

def dashboard_view(request):
    return render(request, 'core/dashboard.html')

__all__ = ['dashboard_view']
