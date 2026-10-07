from django.urls import path
from .views import AuthViewSet, UserViewSet

urlpatterns = [
    path('login/', AuthViewSet.as_view({'post': 'login'}), name='login'),
    path('logout/', AuthViewSet.as_view({'post': 'logout'}), name='logout'),
    path('me/', AuthViewSet.as_view({'get': 'me'}), name='me'),
    path('change-password/', AuthViewSet.as_view({'post': 'change_password'}), name='change-password'),

    # User management
    path('users/', UserViewSet.as_view({'get': 'list', 'post': 'create'}), name='user-list'),
    path('users/<int:pk>/', UserViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name='user-detail'),
    path('users/doctors/', UserViewSet.as_view({'get': 'doctors'}), name='user-doctors'),
    # F1: one pattern handling both GET and PUT. Previously two patterns shared
    # the same path; Django matches the first, so PUT returned 405.
    path('users/permissions/<int:pk>/', UserViewSet.as_view({
        'get': 'permissions',
        'put': 'update_permissions',
    }), name='user-permissions'),
]