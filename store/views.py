from django.shortcuts import render, get_object_or_404, redirect
from carts.models import CartItem
from django.db.models import Q
from carts.views import _cart_id
from .models import Product, ReviewRating, ProductGallery
from category.models import Category
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from .forms import ReviewForm
from django.contrib import messages
from orders.models import OrderProduct

# Create your views here.

def store(request, category_slug=None):
    categories = None
    products = None
    
    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True) 
        product_count = products.count()
    else:
        products = Product.objects.all().filter(is_available=True).order_by('id')
        product_count = products.count()
 
    # add paginator here
    paginator = Paginator(products, 3)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)


    context = {
        'products': paged_products,
        'product_count': product_count,
    }
    return render(request, 'store/store.html', context)

def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
    except Exception as e:
        raise e
    
    if request.user.is_authenticated:
        try:
            orderproduct = OrderProduct.objects.filter(user=request.user, product_id=single_product.id).exists()
        except OrderProduct.DoesNotExist:
            orderproduct = None
    else:
        orderproduct = None

    # get the reviews
    reviews = ReviewRating.objects.filter(product=single_product, status=True)

    #   get the gallery images
    product_gallery = ProductGallery.objects.filter(product=single_product)

    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews' : reviews,
        'product_gallery': product_gallery
    }
    
    return render(request, 'store/product_detail.html', context)

def search(request):
    keyword = request.GET.get('keyword')
    if keyword:
        products = Product.objects.order_by('-created_date').filter(Q(product_name__icontains=keyword) | Q(description__icontains=keyword))
    else:
        products = Product.objects.none()
    product_count = products.count()
    context = {
        'products': products,
        'product_count': product_count
    }
    return render(request, 'store/store.html', context)

def submit_review(request, product_id):
    print("view reached")
    print(request.method)
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        rating = request.POST.get('rating')
        if not rating:
            messages.error(request, 'Please select a star rating.')
            return redirect(url)
        try:
            review = ReviewRating.objects.get(user=request.user, product_id=product_id)
            form = ReviewForm(request.POST, instance=review)
            form.save()
            messages.success(request, 'Thank you')
            return redirect(url)
        except ReviewRating.DoesNotExist:
            form=ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user = request.user
                data.save()
                messages.success(request, 'Thank you! Your review has been submitted.')
                return redirect(url)