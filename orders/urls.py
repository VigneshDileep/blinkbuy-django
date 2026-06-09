from django.urls import include, path
from . import views

urlpatterns = [
    path('place_order/', views.place_order, name='place_order'),
    path('payments/<int:order_id>/', views.payments, name='payments'),
    path('payment_successful/', views.payment_successful, name='payment_success'),
    path('payments_failed/', views.payment_failed, name='payment_failed'),
    path('create-paypal-order/<int:order_id>/', views.create_paypal_order, name='create_paypal_order'),
    path('capture-paypal-order/<int:order_id>/', views.capture_paypal_order, name='capture_paypal_order'),

]