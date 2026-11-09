from django import forms
from django.contrib.auth.password_validation import validate_password

from .service import canonical_email


class EmailForm(forms.Form):
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))

    def clean_email(self):
        return canonical_email(self.cleaned_data['email'])


class PasswordFields(forms.Form):
    password = forms.CharField(max_length=256, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password_confirm = forms.CharField(label='Confirm password', max_length=256, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('password_confirm'):
            raise forms.ValidationError('Passwords do not match.')
        if data.get('password'):
            validate_password(data['password'])
        return data


class SignupForm(EmailForm, PasswordFields):
    name = forms.CharField(label='Full name', max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    field_order = ['name', 'email', 'password', 'password_confirm']

    def clean(self):
        data = super().clean()
        if data.get('password'):
            from django.contrib.auth import get_user_model
            user = get_user_model()(first_name=data.get('name', ''), email=data.get('email', ''))
            validate_password(data['password'], user)
        return data


class ExistingEmailForm(forms.Form):
    username = forms.CharField(label='Username or email', max_length=254, widget=forms.TextInput(attrs={'autocomplete': 'username'}))
    password = forms.CharField(max_length=256, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


class CodeForm(forms.Form):
    code = forms.RegexField(r'^[0-9]{6}$', min_length=6, max_length=6, label='Email code',
                           widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'pattern': '[0-9]{6}'}),
                           help_text='Enter the six-digit code from your email. Codes expire after ten minutes.')


class ResetForm(CodeForm, PasswordFields):
    field_order = ['code', 'password', 'password_confirm']
