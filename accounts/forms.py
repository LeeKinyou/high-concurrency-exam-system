from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(
        label="用户名/学号",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "请输入用户名或学号", "autofocus": True}),
    )
    password = forms.CharField(
        label="密码",
        widget=forms.PasswordInput(attrs={"placeholder": "请输入密码"}),
    )


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        label="原密码",
        widget=forms.PasswordInput(attrs={"placeholder": "请输入原密码"}),
    )
    new_password = forms.CharField(
        label="新密码",
        widget=forms.PasswordInput(attrs={"placeholder": "请输入新密码（至少8位，含大小写字母、数字、特殊字符）"}),
    )
    confirm_password = forms.CharField(
        label="确认新密码",
        widget=forms.PasswordInput(attrs={"placeholder": "请再次输入新密码"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("两次输入的密码不一致")
        return cleaned_data
