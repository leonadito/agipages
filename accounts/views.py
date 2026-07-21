from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import SignupForm


class SignupView(FormView):
    template_name = "registration/signup.html"
    form_class = SignupForm
    success_url = reverse_lazy("core:dashboard")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
