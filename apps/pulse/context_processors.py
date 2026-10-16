def navigation(request):
    return {'can_upload': request.user.is_authenticated and request.user.has_perm('pulse.add_surveyuploadpermission')}
