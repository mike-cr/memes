from django import forms


class MemeCreateForm(forms.Form):
    title = forms.CharField(max_length=160, required=False)
    image = forms.ImageField(required=False)
    image_url = forms.URLField(max_length=2048, required=False)
    tags = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        image = cleaned.get('image')
        image_url = cleaned.get('image_url')
        if bool(image) == bool(image_url):
            raise forms.ValidationError('Provide either an image upload or an image URL.')
        return cleaned


class MemeUpdateForm(forms.Form):
    title = forms.CharField(max_length=160, required=False)
    tags = forms.CharField(required=False, widget=forms.HiddenInput)
