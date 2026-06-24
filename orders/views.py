from django.core.mail import EmailMessage
import json
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.conf import settings
from django.urls import reverse
from django.conf import settings
from orders.models import Order, Payment
from store.models import Product
from .form import OrderForm
import datetime
import requests
from carts.models import CartItem
from paypal.standard.forms import PayPalPaymentsForm
from .models import OrderProduct
from django.template.loader import render_to_string
# 
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .form import OrderForm
from .paypal_client import client
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.exceptions.error_exception import ErrorException
from paypalserversdk.exceptions.api_exception import ApiException
# 
# Create your views here.
def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count() 
    if cart_count <= 0:
        return redirect('store')

    grand_total = 0
    tax = 0
    for item in cart_items:
        total += (item.product.price * item.quantity)
        quantity += item.quantity
    tax = (total * 0.02)
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()

            # Generate order number
            current_date = datetime.date.today().strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()
            

            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)
            # context for using django-paypal
            # context = {
            #     'order': order,
            #     'cart_items': cart_items,
            #     'total': total,
            #     'tax': tax,
            #     'grand_total': grand_total,
            #     'paypal_client_id': settings.PAYPAL_CLIENT_ID,
            # }
            return redirect('payments', order.id)        
        
    else:
        return redirect('checkout')


# django-paypal 

# def payments(request, order_id):
#     cart_items = CartItem.objects.filter(user=request.user)
#     order = Order.objects.get(user=request.user, id=order_id)
#     host = request.get_host()
#     paypal_checkout={
#                 "business": "blinkbuybusiness@gmail.com",
#                 "amount": order.order_total,
#                 "item_name": "Products",
#                 "invoice": order.order_number,
#                 "notify_url": f"http://{host}{reverse('paypal-ipn')}",
#                 "return": f"http://{host}{reverse('payment_success')}",
#                 "cancel_return": f"http://{host}{reverse('payment_failed')}",
#                 # change button text and size
#                 'cmd': '_xclick',
#                 'bn': 'PP-BuyNowBF:btn_buynowCC_LG.gif:NonHostedGuest',  # LG = large button
#             }
#     total = int(order.order_total) - int(order.tax)
#     paypal_payment = PayPalPaymentsForm(initial=paypal_checkout)
    
#     context = {
#         'paypal_payment': paypal_payment,
#         'order': order,
#         'cart_items': cart_items,
#         'total': total,
#         'tax': order.tax,
#         'grand_total': order.order_total,
#     }

#     return render(request, 'orders/payments.html', context)

def payment_successful(request,):
    order_number = request.GET.get('order_number')
    transaction_id = request.GET.get('payment_id')
    try:
        order = Order.objects.get(order_number=order_number, is_ordered =True)
        ordered_products = OrderProduct.objects.filter(order=order)
        payment = Payment.objects.get(payment_id=transaction_id)
        subtotal = int(order.order_total)- int(order.tax)
        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order_number,
            'transaction_id': transaction_id,
            'payment': payment,
            'subtotal':subtotal,
        }
        return render(request, 'orders/payment-success.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')

def payment_failed(request,):
    return render(request, 'orders/payment-failed.html')

# SDK
def payments(request, order_id):
    cart_items = CartItem.objects.filter(user=request.user)
    order = Order.objects.get(user=request.user, id=order_id)
    total = round(float(order.order_total) - float(order.tax), 2)
    
    context = {
        'order': order,
        'cart_items': cart_items,
        'total': total,
        'tax': order.tax,
        'grand_total': order.order_total,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID,
    }

    return render(request, 'orders/payments.html', context)


@csrf_exempt
def create_paypal_order(request, order_id):
    order = Order.objects.get(id=order_id, user=request.user)
    orders_controller = client.orders
    collect = {
        'body': OrderRequest(
            intent=CheckoutPaymentIntent.CAPTURE,
            purchase_units=[
                PurchaseUnitRequest(
                    amount=AmountWithBreakdown(
                        currency_code='USD',
                        value=str(order.order_total)
                    )
                )
            ]
        )
    }
    try:
        result = orders_controller.create_order(collect) 
        return JsonResponse({'id': result.body.id})
    except (ErrorException, ApiException) as e:
        return JsonResponse({'error': str(e)}, status=500)


# called by JavaScript after user approves payment
@csrf_exempt
def capture_paypal_order(request, order_id):
    order = Order.objects.get(id=order_id, user=request.user)
    data = json.loads(request.body)
    paypal_order_id = data.get('paypal_order_id')
    order_number = order.order_number

    orders_controller = client.orders
    try:
        result = orders_controller.capture_order({'id': paypal_order_id})

        # save payment to database
        payment = Payment.objects.create(
            user=request.user,
            payment_id=paypal_order_id,
            payment_method='PayPal',
            amount_paid=order.order_total,
            status='COMPLETED'
        )
        order.payment = payment
        order.is_ordered = True
        order.save()
        # Move the cart item to Order Product table 
        cart_items = CartItem.objects.filter(user=request.user)
        for item in cart_items:
            orderproduct = OrderProduct()
            orderproduct.order_id = order.id
            orderproduct.payment = payment
            orderproduct.user = request.user
            orderproduct.product_id = item.product_id
            orderproduct.quantity = item.quantity
            orderproduct.product_price = item.product.price
            orderproduct.ordered = True
            orderproduct.save()

            cart_item = CartItem.objects.get(id=item.id)
            product_variation = cart_item.variations.all()
            orderproduct.variations.set(product_variation)
            orderproduct.save()

            # reduce the quantity of sold products
            product = Product.objects.get(id=item.product_id)
            product.stock -= item.quantity
            product.save()

        # clear cart
        CartItem.objects.filter(user=request.user).delete()
        # CONFIRMATION EMAIL 
        ordered_products = OrderProduct.objects.filter(order=order)           
        mail_subject = 'Thank you for your order!'
        message = render_to_string('orders/order_recieved_email.html',{
            'user': request.user,
            'order': order,
            'paypal_order_id': paypal_order_id,
            'ordered_products': ordered_products
        })
        to_email = request.user.email
        send_email = EmailMessage(mail_subject, message, to=[to_email])
        send_email.content_subtype = 'html'
        send_email.send()

        data = {
            'order_number': order_number,
            'transaction_id': paypal_order_id,
        }
        return JsonResponse(data)
        
    except (ErrorException, ApiException) as e:
        return JsonResponse({
            "details": [
                {
                    "issue": "PAYPAL_API_ERROR",
                    "description": str(e)
                }
            ],
            "debug_id": getattr(e, "request_id", None)
        }, status=500)




