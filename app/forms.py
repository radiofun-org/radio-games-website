from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django_altcha import AltchaField

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email", "").lower()
        password = cleaned_data.get("password")
        if email and password:
            self.user = authenticate(username=email, password=password)
            if self.user is None:
                raise forms.ValidationError("Invalid email or password.")
        return cleaned_data


class SignUpForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm password")
    captcha = AltchaField()

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        if password and password != cleaned_data.get("password_confirm"):
            self.add_error("password_confirm", "Passwords do not match.")
        if password:
            password_validation.validate_password(password)
        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password"]
        return User.objects.create_user(username=email, email=email, password=password)


ADIF_EXTENSIONS = (".adi", ".adif", ".adx")


class LogUploadForm(forms.Form):
    log_file = forms.FileField(label="ADIF log file")

    def clean_log_file(self):
        f = self.cleaned_data["log_file"]
        if not f.name.lower().endswith(ADIF_EXTENSIONS):
            raise forms.ValidationError("Only ADIF files (.adi, .adif, .adx) are accepted.")
        return f
