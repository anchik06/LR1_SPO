from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from .forms import ReservationForm
from .models import Equipment, Reservation


@login_required
def reservation_list(request):
    items = Reservation.objects.filter(
        user=request.user
    )

    equipment_id = request.GET.get("equipment")

    if equipment_id:
        items = items.filter(
            equipment_id=equipment_id
        )

    items = items.select_related(
        "equipment"
    ).order_by("start")

    equipment_list = Equipment.objects.all()

    return render(
        request,
        "booking/list.html",
        {
            "items": items,
            "equipment_list": equipment_list,
            "selected_equipment": equipment_id,
        }
    )


def preview_availability(request, item=None):
    form = ReservationForm(initial=request.POST.dict(), instance=item)
    context = {"form": form}

    try:
        start = form.fields["start"].clean(request.POST.get("start"))
        end = form.fields["end"].clean(request.POST.get("end"))
    except ValidationError:
        context["availability_error"] = "Укажи дату и время начала и окончания."
    else:
        if start >= end:
            context["availability_error"] = "Конец должен быть позже начала."
        else:
            conflicts = Reservation.objects.filter(
                equipment_id=OuterRef("pk"),
                confirmed=True,
                start__lt=end,
                end__gt=start,
            )

            if item is not None:
                conflicts = conflicts.exclude(pk=item.pk)

            context["availability"] = (
                Equipment.objects.filter(is_active=True)
                .annotate(is_busy=Exists(conflicts))
                .order_by("name", "inventory_number")
            )

    return render(request, "booking/form.html", context)


@login_required
def reservation_create(request):
    if request.method == "POST" and "check_availability" in request.POST:
        return preview_availability(request)

    form = ReservationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.save()
        return redirect("reservation_list")

    return render(request, "booking/form.html", {"form": form})


@login_required
def reservation_edit(request, pk):
    item = get_object_or_404(Reservation, pk=pk, user=request.user)

    if request.method == "POST" and "check_availability" in request.POST:
        return preview_availability(request, item)

    form = ReservationForm(request.POST or None, instance=item)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("reservation_list")

    return render(request, "booking/form.html", {"form": form})


@login_required
@require_POST
def reservation_delete(request, pk):
    item = get_object_or_404(
        Reservation,
        pk=pk,
        user=request.user
    )

    item.delete()
    return redirect("reservation_list")

@login_required
@require_POST
def reservation_cancel(request, pk):
    item = get_object_or_404(
        Reservation,
        pk=pk,
        user=request.user
    )

    item.confirmed = False
    item.save(update_fields=["confirmed"])

    return redirect("reservation_list")
