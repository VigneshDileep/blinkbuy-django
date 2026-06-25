from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.core.mail import EmailMessage
import requests
import resend
from carts.models import Cart, CartItem
from django.contrib.sites.shortcuts import get_current_site
from accounts.models import Account
from carts.views import _cart_id
from .forms import RegistrationForm, UserForm, UserProfileform
from orders.models import Order
from .models import UserProfile
from orders.models import OrderProduct
from django.shortcuts import get_object_or_404
from django.conf import settings
# Create your views here.

def register(request):
    if request.method == 'POST':
        form =RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            password = form.cleaned_data['password']
            username = email.split('@')[0]

            user = Account.objects.create_user(first_name=first_name, last_name=last_name, email=email, password=password, username=username)
            user.phone_number = phone_number
            user.save()
            # create userprofile
            profile = UserProfile()
            profile.user = user
            profile.profile_picture = "default/default-user.avif"
            profile.save()
            # User Activation Email         
            current_site = get_current_site(request)
            mail_subject = 'Please activate your account'
            message = render_to_string('accounts/account_verification_email.html',{
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user)
            })
            resend.api_key = settings.RESEND_API_KEY
            # google smptp 
            # to_email = email
            # send_email = EmailMessage(mail_subject, message, to=[to_email])
            # send_email.content_subtype = 'html'
            # send_email.send()
            # resend
            r = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": [email],
                "subject": mail_subject,
                "html": message
            })
            print("Email sent:", r)
            url = reverse('login')
            return redirect(f'{url}?command=verification&email={email}')
            
    else:
        form = RegistrationForm()
    context = {
        'form' : form
    }
    return render(request, "accounts/register.html", context)

def login(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']

        user = auth.authenticate(email=email, password=password)
        if user is not None:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                is_cart_item_exists = CartItem.objects.filter(cart=cart).exists()
                if is_cart_item_exists:
                    cart_item = CartItem.objects.filter(cart=cart)

                    product_variation = []
                    for item  in cart_item:
                        variation = item.variations.all()
                        product_variation.append(list(variation))

                    cart_item = CartItem.objects.filter(user=user)
                    ex_var_list = []
                    id = []
                    for item in cart_item:
                        existing_variation = item.variations.all()
                        ex_var_list.append(list(existing_variation))
                        id.append(item.id)

                    for pr in product_variation:
                        if pr in ex_var_list:
                            index = ex_var_list.index(pr)
                            item_id = id[index]
                            item = CartItem.objects.get(id=item_id)
                            item.quantity += 1
                            item.user = user
                            item.save()
                        else:
                            cart_item = CartItem.objects.filter(cart=cart)
                            for item in cart_item:
                                item.user = user
                                item.save()
                    
            except:
                pass
            auth.login(request, user)
            messages.success(request, "Login Successful!")
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    return redirect(nextPage)
            except:
                pass
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid Login Credentials!")
            return redirect('login')



    return render(request, "accounts/login.html")

@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    messages.success(request, "You are logged out.")
    return redirect('login')


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Congratulations! Your account is activated.")
        return redirect('login')
    else:
        messages.error(request, "Invalid activation link!")
        return redirect('register')
    
@login_required(login_url='login')
def dashboard(request):
    orders = Order.objects.order_by('-created_at').filter(user=request.user, is_ordered=True)
    order_count = orders.count()
    userprofile = get_object_or_404(UserProfile, user=request.user)
    context ={
        'orders': orders,
        'order_count': order_count,
        'userprofile': userprofile,
    }
    return render(request, "accounts/dashboard.html", context)

def forgotPassword(request):
    if request.method == 'POST':
        email = request.POST['email']
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)
            # Email Reset Password
            current_site = get_current_site(request)
            mail_subject = 'Reset Your Password'
            message = render_to_string('accounts/forgotPassword_email.html',{
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user)
            })
            # to_email = email
            # send_email = EmailMessage(mail_subject, message, to=[to_email])
            # send_email.content_subtype = 'html'
            # send_email.send()
            resend.api_key = settings.RESEND_API_KEY
            r = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": [email],
                "subject": mail_subject,
                "html": message
            })
            print("Email sent:", r)
            messages.success(request, "Password reset email has been sent to your email address.")
            return redirect('login')
        else:
            messages.error(request, "Account does not exist!")
            return redirect('forgotPassword')
    return render(request, "accounts/forgotPassword.html")

def resetPassword_validate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, "Please reset your password.")
        return redirect('resetPassword')
    else:
        messages.error(request, "This link has been expired!")
        return redirect('login')
    
def resetPassword(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        if password == confirm_password:
            uid = request.session.get('uid')
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, "Password reset successful!")
            return redirect('login')
        else:
            messages.error(request, "Password do not match!")
            return redirect('resetPassword')
    return render(request, "accounts/resetPassword.html")

def my_orders(request):
    orders = Order.objects.order_by("-created_at").filter(user=request.user, is_ordered=True)
    context = {
        'orders': orders
    }
    return render(request, "accounts/my_orders.html", context)

def edit_profile(request):
    userprofile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileform(request.POST, request.FILES, instance=userprofile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your Profile has been updated')
            return redirect('edit_profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileform(instance=userprofile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'userprofile': userprofile
    }
    
    return render(request, 'accounts/edit_profile.html', context)

@login_required(login_url='login')
def change_password(request):
    if request.method == "POST":
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        user = request.user

        if not user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")

        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")

        else:
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)

            messages.success(request, "Password updated successfully!")
            return redirect('change_password')

    return render(request, "accounts/change_password.html")

@login_required(login_url='login')
def order_detail(request, order_id):
    order = Order.objects.get(order_number=order_id)
    order_detail = OrderProduct.objects.filter(order=order)
    subtotal = 0
    for i in order_detail:
        subtotal += i.product_price * i.quantity
    context = {
        'order': order,
        'order_detail': order_detail,
        'subtotal': subtotal,
    }
    return render(request, "accounts/order_detail.html", context)
