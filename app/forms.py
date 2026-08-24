from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django_altcha import AltchaField

from .models import AuthUser, CallsignAssociation


class EmailAuthenticationForm(AuthenticationForm):
    def clean_username(self):
        return self.cleaned_data["username"].lower()


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        super().clean()
        email = self.cleaned_data.get("email", "").lower()
        password = self.cleaned_data.get("password")
        if email and password:
            self.user = authenticate(username=email, password=password)
            if self.user is None:
                raise forms.ValidationError("Invalid email or password.")
        return self.cleaned_data


class SignUpForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm password")
    captcha = AltchaField()

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if AuthUser.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        super().clean()
        password = self.cleaned_data.get("password")
        if password and password != self.cleaned_data.get("password_confirm"):
            self.add_error("password_confirm", "Passwords do not match.")
        if password:
            password_validation.validate_password(password)
        return self.cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password"]
        return AuthUser.objects.create_user(username=email, email=email, password=password)


ADIF_EXTENSIONS = (".adi", ".adif", ".adx")


class LogUploadForm(forms.Form):
    callsign = forms.ChoiceField(label="Your callsign")
    log_file = forms.FileField(label="ADIF log file")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            choices = CallsignAssociation.objects.filter(user=user).values_list(
                "callsign", "callsign"
            )
            callsign_field = self.fields["callsign"]
            assert isinstance(callsign_field, forms.ChoiceField)
            callsign_field.choices = [("", "Select callsign")] + list(choices)

    def clean_log_file(self):
        f = self.cleaned_data["log_file"]
        if not f.name.lower().endswith(ADIF_EXTENSIONS):
            raise forms.ValidationError("Only ADIF files (.adi, .adif, .adx) are accepted.")
        return f
